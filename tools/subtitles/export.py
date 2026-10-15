"""cache.json -> build/text/subtitles.txt + build/review.txt, and packing. Shared by transcribe.py and review_server.py."""
import zipfile
from pathlib import Path

HERE = Path(__file__).parent


def junk(key, r):  # grunts and prompt leaks are not subtitles (manual edits are never junk)
	t = r["text"]
	if r.get("manual"):
		return False
	return "/pain/" in key or "/death/" in key or t.startswith("B.J. Blazkowicz") or len([c for c in t if c.isalpha()]) <= 3


def export(cache, out):
	lines, review = [], []
	(out / "text").mkdir(parents=True, exist_ok=True)
	for key, r in sorted(cache.items()):
		if r["text"] and junk(key, r):
			continue
		if not r["text"]:
			review.append(f"NOSPEECH {key} ({r['dur']}s)"); continue
		if r.get("recovered") or r["prob"] < 0.8 or r["lang"] != "en" or r["dur"] < 1.0:
			review.append(f"{'RECOVERED' if r.get('recovered') else 'CHECK'} {key} [{r['lang']} {r['prob']} {r['dur']}s] {r['text']}" + (f"  | orig: {r['orig']}" if r["lang"] != "en" else ""))
		lines.append(f'{key} {r["dur"]} "{r["text"].replace(chr(34), chr(39)).replace(chr(10), " ")}"')
	(out / "text" / "subtitles.txt").write_text("\n".join(lines) + "\n")
	(out / "review.txt").write_text("\n".join(review) + "\n")
	print(len(lines), "subtitles,", len(review), "to review")
	return len(lines)


def pack(out=HERE / "build"):
	src = out / "text" / "subtitles.txt"
	dst = HERE.parent.parent / "run" / "codmod" / "codmod_subtitles.pk3"
	with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
		z.write(src, "text/subtitles.txt")
	print("wrote", dst)
	return dst
