"""Review and fix subtitles in the browser: uv run python review_server.py [port]  ->  http://127.0.0.1:8765

Serves the clips (read straight from the Steam paks), shows each transcript in an editable field, and saves edits
to build/cache.json. "Rebuild + pack" regenerates subtitles.txt and run/codmod/codmod_subtitles.pk3.
Bound to localhost only. Edited lines are marked "manual" and are never dropped by the junk filter; saving an
empty text removes the subtitle.
"""
import json, sys, tempfile, zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from export import export, pack

HERE = Path(__file__).parent
BUILD = HERE / "build"
CACHE = BUILD / "cache.json"
PAKS = Path.home() / ".local/share/Steam/steamapps/common/Return to Castle Wolfenstein/Main"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765

cache = json.loads(CACHE.read_text())
index = {}  # lowercase path -> (pak, name)
for pak in sorted(PAKS.glob("*.pk3")):
	if pak.name.startswith("mp_"): continue
	with zipfile.ZipFile(pak) as z:
		for n in z.namelist():
			if n.lower() in cache: index[n.lower()] = (pak, n)


def save_cache():
	tmp = Path(tempfile.mkstemp(dir=BUILD, suffix=".tmp")[1])
	tmp.write_text(json.dumps(cache, indent=0, ensure_ascii=False))
	tmp.replace(CACHE)


def rows():
	out = []
	for k, r in sorted(cache.items()):
		kind = ("edited" if r.get("manual") else "recovered" if r.get("recovered")
			else "missing" if not r["text"] else "check" if (r["prob"] < 0.8 or r["lang"] != "en" or r["dur"] < 1.0) else "ok")
		out.append(dict(key=k, kind=kind, text=r["text"], orig=r.get("orig", ""), lang=r["lang"], prob=r["prob"], dur=r["dur"]))
	return out


class H(BaseHTTPRequestHandler):
	def log_message(self, *a): pass

	def send(self, code, body, ctype="application/json"):
		b = body if isinstance(body, bytes) else body.encode()
		self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b))); self.end_headers()
		self.wfile.write(b)

	def do_GET(self):
		if self.path == "/":
			self.send(200, PAGE, "text/html; charset=utf-8")
		elif self.path == "/api/lines":
			self.send(200, json.dumps(rows()))
		elif self.path.startswith("/audio/"):
			pak, name = index.get(self.path[7:].lower(), (None, None))
			if not pak: return self.send(404, "{}")
			with zipfile.ZipFile(pak) as z: self.send(200, z.read(name), "audio/wav")
		else:
			self.send(404, "{}")

	def do_POST(self):
		data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
		if self.path == "/api/save":           # {key, text}
			r = cache.get(data.get("key"))
			if r is None: return self.send(404, '{"error":"unknown key"}')
			text = " ".join(str(data.get("text", "")).split())
			if text != r["text"]:
				r.update(text=text, manual=True, retried=True, recovered=False)
				save_cache()
			self.send(200, json.dumps(dict(ok=True, kind="edited")))
		elif self.path == "/api/rebuild":      # regenerate subtitles.txt and the pk3
			n = export(cache, BUILD); pack(BUILD)
			self.send(200, json.dumps(dict(ok=True, lines=n)))
		else:
			self.send(404, "{}")


PAGE = r"""<!doctype html><meta charset=utf-8><title>Subtitle review</title>
<style>
:root{--bg:#fff;--fg:#1c1c1c;--mut:#6b6b6b;--line:#ddd;--acc:#2b6cb0;--ok:#2f855a}
@media(prefers-color-scheme:dark){:root{--bg:#161616;--fg:#e8e8e8;--mut:#9a9a9a;--line:#333;--acc:#63a4e8;--ok:#5fc08a}}
body{background:var(--bg);color:var(--fg);font:15px system-ui,sans-serif;margin:0 auto;max-width:1000px;padding:16px}
header{position:sticky;top:0;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line);display:flex;gap:8px;flex-wrap:wrap;align-items:center}
input,select,button,textarea{font:inherit;color:inherit;background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:5px 8px}
button{cursor:pointer}button.p{background:var(--acc);color:#fff;border-color:var(--acc)}
.row{display:grid;grid-template-columns:230px 1fr auto;gap:8px 12px;align-items:start;padding:10px 0;border-bottom:1px solid var(--line)}
.key{font-size:12px;color:var(--mut);word-break:break-all}audio{width:100%;height:32px;margin-top:4px}
textarea{width:100%;box-sizing:border-box;resize:vertical;min-height:34px}
.orig{font-size:12px;color:var(--mut);margin-top:3px}.st{font-size:12px;min-width:48px}.ok{color:var(--ok)}
@media(max-width:700px){.row{grid-template-columns:1fr}}
</style>
<header>
<select id=f><option value=review>Needs review</option><option value=missing>Missing text</option><option value=edited>Edited</option><option value=all>All</option></select>
<input id=q placeholder="search path or text" size=24>
<span id=n style="color:var(--mut)"></span>
<button class=p id=rb style="margin-left:auto">Rebuild + pack</button><span id=rs class=st></span>
</header>
<div id=list></div>
<script>
let all=[];
const $=s=>document.querySelector(s);
const show=r=>{const f=$('#f').value,q=$('#q').value.toLowerCase();
 if(q&&!(r.key+' '+r.text+' '+r.orig).toLowerCase().includes(q))return false;
 return f=='all'||(f=='review'&&['check','recovered'].includes(r.kind))||f==r.kind};
function render(){const l=$('#list');l.textContent='';const rs=all.filter(show);$('#n').textContent=rs.length+' of '+all.length;
 for(const r of rs.slice(0,300)){const d=document.createElement('div');d.className='row';
  const a=document.createElement('div');const k=document.createElement('div');k.className='key';k.textContent=r.key.replace('sound/','')+'  ['+r.lang+' '+r.prob+' '+r.dur+'s]';
  const au=document.createElement('audio');au.controls=true;au.preload='none';au.src='/audio/'+r.key;a.append(k,au);
  const m=document.createElement('div');const t=document.createElement('textarea');t.value=r.text;t.rows=Math.max(1,Math.ceil(r.text.length/70));m.append(t);
  if(r.orig&&r.orig!==r.text){const o=document.createElement('div');o.className='orig';o.textContent='orig: '+r.orig;m.append(o)}
  const s=document.createElement('div');s.className='st';const b=document.createElement('button');b.textContent='Save';
  const save=async()=>{const res=await fetch('/api/save',{method:'POST',body:JSON.stringify({key:r.key,text:t.value})});
   if(res.ok){r.text=t.value;r.kind='edited';s.textContent='saved';s.className='st ok'}else{s.textContent='error'}};
  b.onclick=save;t.onkeydown=e=>{if(e.key=='Enter'&&!e.shiftKey){e.preventDefault();save()}};
  const c=document.createElement('div');c.append(b,s);d.append(a,m,c);l.append(d)}
 if(rs.length>300){const p=document.createElement('p');p.textContent='Showing the first 300, narrow the filter.';l.append(p)}}
$('#f').onchange=$('#q').oninput=render;
$('#rb').onclick=async()=>{$('#rs').textContent='...';const r=await(await fetch('/api/rebuild',{method:'POST',body:'{}'})).json();$('#rs').textContent=r.lines+' lines packed';$('#rs').className='st ok'};
fetch('/api/lines').then(r=>r.json()).then(j=>{all=j;render()});
</script>"""

if __name__ == "__main__":
	print(f"http://127.0.0.1:{PORT}  (Ctrl+C to stop)")
	ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
