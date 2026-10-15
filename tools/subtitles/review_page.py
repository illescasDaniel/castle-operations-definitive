"""Build build/review/index.html: audio + transcript for every CHECK/RECOVERED line in build/review.txt."""
import html, re, zipfile
from pathlib import Path

here = Path(__file__).parent
pak_dir = Path.home() / ".local/share/Steam/steamapps/common/Return to Castle Wolfenstein/Main"
out = here / "build" / "review"; out.mkdir(exist_ok=True)
rows = []
for l in (here / "build" / "review.txt").read_text().splitlines():
	m = re.match(r"(CHECK|RECOVERED) (\S+) \[(.*?)\] (.*)", l)
	if m: rows.append(m.groups())
want = {r[1] for r in rows}
for pak in sorted(pak_dir.glob("*.pk3")):
	if pak.name.startswith("mp_"): continue
	with zipfile.ZipFile(pak) as z:
		for n in z.namelist():
			if n.lower() in want:
				(out / n.lower().replace("/", "__")).write_bytes(z.read(n))
body = "".join(f"<tr><td>{k}<br><small>{html.escape(info)}</small></td><td><audio controls preload=none src='{html.escape(p.lower().replace('/', '__'))}'></audio></td><td>{html.escape(t)}</td></tr>" for k, p, info, t in rows)
(out / "index.html").write_text("<meta charset=utf-8><title>Subtitle review</title><style>body{font:15px sans-serif;margin:2em}td{padding:6px;border-bottom:1px solid #ccc;vertical-align:top}</style><table>" + body + "</table>")
print(len(rows), "rows")
