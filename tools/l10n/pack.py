"""Pack language packs: mod/codmod/lang/<code>/ -> run/codmod/codmod_lang_<code>.pk3 (paths lang/<code>/...).

  python3 tools/l10n/pack.py            pack every language
  python3 tools/l10n/pack.py --lang de  pack one
"""
import argparse, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "mod" / "codmod" / "lang"
OUT = ROOT / "run" / "codmod"
JUNK_NAMES = {".DS_Store", "Thumbs.db"}
JUNK_SUFFIX = (".swp", ".swo", ".bak", ".orig", ".tmp", "~")


def junk(p):
	return p.name in JUNK_NAMES or p.name.startswith((".", "#")) or p.name.endswith(JUNK_SUFFIX)


def pack(code):
	d = SRC / code
	files = sorted(p for p in d.rglob("*") if p.is_file() and not junk(p)
	               and not any(part.startswith(".") for part in p.relative_to(d).parts))
	if not (d / "lang.info").is_file():
		sys.exit(f"pack.py: {d}/lang.info missing")
	OUT.mkdir(parents=True, exist_ok=True)
	dst = OUT / f"codmod_lang_{code}.pk3"
	with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
		for p in files:
			z.write(p, f"lang/{code}/{p.relative_to(d).as_posix()}")
	print(f"wrote {dst} ({len(files)} files)")


if __name__ == "__main__":
	ap = argparse.ArgumentParser()
	ap.add_argument("--lang", help="pack only this language code")
	a = ap.parse_args()
	codes = [a.lang] if a.lang else sorted(p.name for p in SRC.iterdir() if p.is_dir() and not p.name.startswith("."))
	for c in codes:
		pack(c)
