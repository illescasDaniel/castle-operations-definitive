"""Tiny parser for RTCW .menu files (just enough for tools/l10n/fit.py).

parse_menu(path, defines) -> list of menus; menu = {"name", "rect", "items": [item]}; item = dict of
lowercased key -> list of values (numbers as float, strings as str). Blocks ({ ... }) are stored as raw token
lists. "line" is the source line of the itemDef keyword.
"""
import re
from pathlib import Path

ARITY = {"name": 1, "text": 1, "type": 1, "rect": 4, "textscale": 1, "textalign": 1, "textalignx": 1,
         "textaligny": 1, "textfont": 1, "cvar": 1, "style": 1, "ownerdraw": 1, "textfile": 1, "group": 1,
         "background": 1, "maxchars": 1, "maxpaintchars": 1, "border": 1, "bordersize": 1, "visible": 1,
         "feeder": 1, "elementwidth": 1, "elementheight": 1, "elementtype": 1, "special": 1, "align": 1,
         "textstyle": 1, "cvartest": 1, "ownerdrawflag": 1}
TOK = re.compile(r'"((?:[^"\\]|\\.)*)"|([{}])|([^\s{}"]+)')


def load_defines(path):
	d = {}
	for ln in Path(path).read_text(errors="replace").splitlines():
		m = re.match(r"#define\s+(\w+)\s+(\S+)", ln)
		if m:
			d[m.group(1)] = m.group(2)
	return d


def tokenize(text):
	text = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
	out = []
	for lineno, ln in enumerate(text.splitlines(), 1):
		if ln.lstrip().startswith("#"):
			continue
		# strip // comments outside of quotes
		res, inq, i = [], False, 0
		while i < len(ln):
			c = ln[i]
			if c == '"':
				inq = not inq
			if not inq and ln.startswith("//", i):
				break
			res.append(c)
			i += 1
		ln = "".join(res)
		for m in TOK.finditer(ln):
			if m.group(1) is not None:
				out.append(("s", m.group(1), lineno))
			elif m.group(2):
				out.append((m.group(2), m.group(2), lineno))
			else:
				out.append(("w", m.group(3), lineno))
	return out


def num(tok, defines):
	t = defines.get(tok, tok)
	try:
		return float(int(t, 0)) if re.fullmatch(r"-?0[xX][0-9a-fA-F]+|-?\d+", t) else float(t)
	except ValueError:
		return None


def skip_block(toks, i):
	"""toks[i] is '{'; returns (inner tokens, index after matching '}')."""
	depth, j = 0, i
	while j < len(toks):
		if toks[j][0] == "{":
			depth += 1
		elif toks[j][0] == "}":
			depth -= 1
			if depth == 0:
				return toks[i + 1:j], j + 1
		j += 1
	return toks[i + 1:], j


def parse_body(toks, defines):
	d, i = {}, 0
	while i < len(toks):
		k, v, ln = toks[i]
		i += 1
		if k not in ("w",):
			continue
		key = v.lower()
		vals = []
		if i < len(toks) and toks[i][0] == "{":
			blk, i = skip_block(toks, i)
			d.setdefault(key, []).append(blk)
			continue
		ar = ARITY.get(key)
		if ar is not None:
			n = 0
			while n < ar and i < len(toks) and toks[i][0] in ("s", "w"):
				kk, vv, _ = toks[i]
				vals.append(vv if kk == "s" else (num(vv, defines) if num(vv, defines) is not None else vv))
				i += 1
				n += 1
			if key == "rect":      # optional alignment words
				while i < len(toks) and toks[i][0] == "w" and num(toks[i][1], defines) is not None:
					i += 1
		else:
			while i < len(toks) and toks[i][0] in ("s", "w"):
				kk, vv, _ = toks[i]
				n_ = num(vv, defines) if kk == "w" else None
				if kk == "w" and n_ is None:
					break
				vals.append(vv if kk == "s" else n_)
				i += 1
		d[key] = vals
		d["_line_" + key] = ln
	return d


def parse_menu(path, defines):
	toks = tokenize(Path(path).read_text(errors="replace"))
	menus, i = [], 0
	while i < len(toks):
		if toks[i][0] == "w" and toks[i][1].lower() == "menudef" and toks[i + 1][0] == "{":
			body, i = skip_block(toks, i + 1)
			menu = {"name": None, "rect": [0, 0, 640, 480], "items": [], "file": Path(path).name}
			# split top-level: itemDef blocks vs. menu properties
			props, j = [], 0
			while j < len(body):
				if body[j][0] == "w" and body[j][1].lower() == "itemdef" and j + 1 < len(body) and body[j + 1][0] == "{":
					line = body[j][2]
					blk, j = skip_block(body, j + 1)
					it = parse_body(blk, defines)
					it["line"] = line
					menu["items"].append(it)
				else:
					if body[j][0] == "{":
						_, j = skip_block(body, j)
						continue
					props.append(body[j])
					j += 1
			p = parse_body(props, defines)
			menu["name"] = (p.get("name") or [None])[0]
			if "rect" in p and len(p["rect"]) >= 4:
				menu["rect"] = p["rect"][:4]
			menu["props"] = p
			menus.append(menu)
		else:
			i += 1
	return menus
