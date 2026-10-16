#!/usr/bin/env python3
"""Measure whether translated menu strings and text pages fit, with the engine's own text-width formula.

  python3 tools/l10n/fit.py                 check de and es, print every failure
  python3 tools/l10n/fit.py --lang es -v    one language, also list items that fit
  python3 tools/l10n/fit.py --no-pages      skip the text-page (briefing/notebook/clipboard) height check
  python3 tools/l10n/fit.py --width TEXT FONT SCALE   print the pixel width of a candidate string

Besides the fit check it verifies that the quoted control names in the training pages ('attack', 'reload', ...) are the
same words as the translated Controls menu labels (CONTROL_MAP below), and that strings.txt has every English key once.

Width (iortcw/SP/code/ui/ui_main.c Text_Width): sum of glyph xSkip over the Latin-1 bytes (colour codes ^x skipped)
* scale * font glyphScale, truncated to int. Font choice: textfont UI_FONT_NORMAL/BIG/SMALL/HANDWRITING -> 16/24/12/17
pt; UI_FONT_DEFAULT (no textfont) -> small (12) when scale <= ui_smallFont (0.25), big (24) when scale > ui_bigFont
(0.4), else normal (16). Glyph metrics come from the fontImage_<pt>.dat files in the RTCW paks (tools/l10n/fonts.py).

Layout (ui_shared.c): item text is placed at rect.x + textalignx (left), minus its width (right aligned) or half of it
(centred). Rows with a value (YESNO / MULTI / SLIDER / BIND / EDITFIELD) draw the value 8 px after the label's end.
Text is neither wrapped nor clipped, so a string "fits" when
  left aligned : start .. min(rect right edge, 640)
  centred      : symmetric around the anchor, within the rect and the screen
  right aligned: anchor - width >= rect left edge (>= 0 for the screen)
and, for rows, the value (widest label of the list / yes / no / maxPaintChars digits / slider bar) still ends inside
the rect. A translation that is wider than the space is tolerated only when it is not wider than the English text
(English already overflows by the same amount); anything else is reported as FAIL.

Text pages (autowrapped textfile items, Item_Text_AutoWrapped_Paint) are wrapped by the engine; the check simulates the
exact greedy algorithm and compares the last baseline (aligny + (lines-1) * (height+5)) with the rect height.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import extract as ex          # noqa: E402  (Paks, menu lists)
import fonts as fontmod       # noqa: E402
import menuparse as mp        # noqa: E402

ROOT = HERE.parents[1]
LANG_DIR = ROOT / "mod" / "codmod" / "lang"
UI_DIR = ROOT / "mod" / "codmod" / "ui"
SMALL_T, BIG_T = 0.25, 0.4          # ui_smallFont / ui_bigFont defaults (ui_main.c)
FONT_PT = {1: 16, 2: 24, 3: 12, 4: 17}
SCREEN_W = 640
SLIDER_W = 96                       # SLIDER_WIDTH in ui_shared.h
LOOSE = {"credit.menu"}            # scrolling credits: not a layout problem
MAX_PAGE_BYTES = 4000
EDIT_CHARS = 16                    # edit-field value width assumed for the room check


# --------------------------------------------------------------------------------------------- fonts / widths
class Metrics:
	def __init__(self):
		files = fontmod.load_files(fontmod.find_main())
		self.fonts = {}
		for pt in (12, 16, 17, 24):
			g, scale = fontmod.parse_dat(files[f"fonts/fontImage_{pt}.dat"])
			self.fonts[pt] = ([e[4] for e in g], [e[0] for e in g], scale)

	@staticmethod
	def pt(font, scale):
		font = int(font or 0)
		if font == 0:
			return 12 if scale <= SMALL_T else (24 if scale > BIG_T else 16)
		return FONT_PT.get(font, 16)

	def width(self, s, font, scale):
		xs, _, gs = self.fonts[self.pt(font, scale)]
		b = to_latin1(s)
		out, i = 0, 0
		while i < len(b):
			if b[i] == 0x5E and i + 1 < len(b) and b[i + 1] != 0x5E:      # Q_IsColorString
				i += 2
				continue
			out += xs[b[i]]
			i += 1
		return int(out * scale * gs)

	def height(self, s, font, scale):
		_, hs, gs = self.fonts[self.pt(font, scale)]
		b = to_latin1(s)
		m, i = 0, 0
		while i < len(b):
			if b[i] == 0x5E and i + 1 < len(b) and b[i + 1] != 0x5E:
				i += 2
				continue
			m = max(m, hs[b[i]])
			i += 1
		return int(m * scale * gs)


def to_latin1(s):
	"""Lang_Utf8ToLatin1: what the engine ends up drawing for a UTF-8 string."""
	if isinstance(s, bytes):
		return s
	out = bytearray()
	for ch in s:
		cp = ord(ch)
		if cp <= 0xFF:
			out.append(cp)
		elif cp in (0x2018, 0x2019, 0x201A):
			out += b"'"
		elif cp in (0x201C, 0x201D, 0x201E):
			out += b'"'
		elif cp in (0x2013, 0x2014, 0x2212):
			out += b"-"
		elif cp == 0x2026:
			out += b"..."
		elif cp == 0x20AC:
			out += b"EUR"
		else:
			out += b"?"
	return bytes(out)


# --------------------------------------------------------------------------------------------- strings.txt
def parse_quoted(s, i):
	"""s[i] == '"'. Returns (text, next index) with the engine's escapes (Lang_ParseQuoted)."""
	i += 1
	out = []
	while i < len(s) and s[i] not in '"\n':
		if s[i] == "\\" and i + 1 < len(s):
			i += 1
			out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(s[i], "\\" + s[i]))
		else:
			out.append(s[i])
		i += 1
	if i < len(s) and s[i] == '"':
		i += 1
	return "".join(out), i


def parse_strings(path):
	"""[(key, value, lineno)] in file order."""
	rows = []
	text = Path(path).read_text(encoding="utf-8")
	for n, line in enumerate(text.split("\n"), 1):
		line = line.lstrip(" \t\r")
		if not line.startswith('"'):
			continue
		k, i = parse_quoted(line, 0)
		while i < len(line) and line[i] in " \t":
			i += 1
		if i >= len(line) or line[i] != '"':
			continue
		v, i = parse_quoted(line, i)
		rows.append((k, v, n))
	return rows


# --------------------------------------------------------------------------------------------- menus
def load_all_menus():
	"""Same menu set the catalog uses: the three menu lists plus unlisted mod menus; mod copy wins over the paks."""
	paks = ex.Paks(ex.DEFAULT_RTCW)
	defines = mp.load_defines(UI_DIR / "menudef.h")
	listed = []
	for lst in ("menus.txt", "ingame.txt", "hud.txt"):
		listed += ex.parse_menu_list(lst, ex.UI_DIR, paks)
	extra = [f"ui/{p.name}" for p in sorted(UI_DIR.glob("*.menu")) if f"ui/{p.name}" not in listed]
	menus, seen = [], set()
	tmp = Path("/tmp") / "fit_menu_cache"
	for rel in listed + extra:
		base = Path(rel).name
		if base in seen:
			continue
		seen.add(base)
		text, src = ex.load_menu_text(rel, paks)
		if text is None:
			continue
		path = UI_DIR / base
		if not path.exists():           # pak menu: parse from a temp copy
			tmp.mkdir(exist_ok=True)
			path = tmp / base
			path.write_text(text, encoding="utf-8")
		for m in mp.parse_menu(path, defines):
			m["file"] = base
			menus.append(m)
	return menus, paks


def num(v, d=0.0):
	return v[0] if v and isinstance(v[0], (int, float)) else d


def menu_frame(m):
	"""(x, y, w, h, border offset, popup) of the menu as the engine places it (Menu_PostParse)."""
	pr = m["props"]
	full = bool(num(pr.get("fullscreen"), 0))
	x, y, w, h = ((0, 0, 640, 480) if full else m["rect"])
	mb = (num(pr.get("bordersize"), 1.0) if num(pr.get("border"), 0) else 0)
	return x, y, w, h, mb, (not full and (w < 640 or h < 480))


def item_geom(m, it):
	"""Absolute rect of an item (Item_SetScreenCoords) plus the item's own border offset used for text."""
	mx, my, _, _, mb, _ = menu_frame(m)
	r = it.get("rect") or [0, 0, 0, 0]
	ib = num(it.get("bordersize"), 1.0) if num(it.get("border"), 0) else 0
	x, y, w, h = r[:4]
	return {"x": x + mx + mb + ib, "y": y + my + mb + ib, "w": w, "h": h, "ib": ib}


def is_boxed(it):
	"""A visible hit box / highlight: the rect is a real boundary for the text."""
	bc = it.get("backcolor") or [0, 0, 0, 0]
	alpha = bc[3] if len(bc) >= 4 else 0
	return int(num(it.get("type"), 0)) in (1, 2, 3) and (int(num(it.get("style"), 0)) == 1 and alpha > 0 or bool(num(it.get("border"), 0)))


POP_PAD = 8     # padding inside a popup panel (its border + a little air)


def span(it, g, width):
	"""(start, end) of text of `width` for the item's alignment."""
	al = int(num(it.get("textalign"), 0))
	anchor = g["x"] + g["ib"] + num(it.get("textalignx"), 0)
	if al == 2:
		return anchor - width, anchor
	if al == 1:
		return anchor - width / 2.0, anchor + width / 2.0
	return anchor, anchor + width


def room(al, anchor, lo, hi, width, label_end_extra=0):
	"""Space available to text of a given alignment between lo and hi."""
	if al == 2:
		return anchor - lo
	if al == 1:
		return 2 * min(anchor - lo, hi - anchor)
	return hi - anchor


META = {}      # where -> (font, scale) of the menu item, for the candidate helper


class Finding:
	def __init__(self, **kw):
		self.__dict__.update(kw)
		self.soft = False
		self.font, self.scale = META.get(kw.get("where"), (0, 0.2))

	def status(self):
		if self.tr_w <= self.have:
			return "ok"
		return "tolerated" if self.tr_w <= self.en_w else "FAIL"


def list_labels(block):
	"""Labels of a cvarStrList/cvarFloatList block ("label" value pairs)."""
	out, i = [], 0
	while i < len(block):
		if block[i][0] == "s":
			out.append(block[i][1])
			i += 2
		else:
			i += 1
	return out


def bounds(m, it, g, en_w_for_fit):
	"""(rect_lo, rect_hi, cont_lo, cont_hi): the item's own rect and the container (popup panel or screen)."""
	mx, my, mw, mh, mb, popup = menu_frame(m)
	lo = g["x"]
	hi = g["x"] + g["w"] if g["w"] > 0 else SCREEN_W
	if popup:
		clo, chi = mx + mb + POP_PAD, mx + mw - mb - POP_PAD
	else:
		clo, chi = 0, SCREEN_W
	return lo, hi, clo, chi


def check_menu_items(met, menus, tr, lang):
	"""Findings for every translated label/value of every menu item."""
	res = []

	def T(s):
		return tr.get(s, s)

	for m in menus:
		if m["file"] in LOOSE:
			continue
		for it in m["items"]:
			text = (it.get("text") or [None])[0]
			ty = int(num(it.get("type"), 0))
			if not it.get("textscale"):
				continue
			scale = num(it.get("textscale"), 0.2)
			font = num(it.get("textfont"), 0)
			g = item_geom(m, it)
			where = f"{m['file']}:{it.get('line')} ({(it.get('name') or [''])[0]})"
			META[where] = (font, scale)
			if "autowrapped" in it and text:
				res += wrapped_item(met, m, it, g, text, T(text), font, scale, where, lang)
				continue
			vals = []
			if ty == 11:
				vals = ["yes", "no"]
			elif ty == 12:
				for key in ("cvarstrlist", "cvarfloatlist"):
					for blk in it.get(key, []):
						vals += [s for s in list_labels(blk) if s]
			if not (text and text.strip()):
				continue
			al = int(num(it.get("textalign"), 0))
			ew, tw = met.width(text, font, scale), met.width(T(text), font, scale)
			lo = g["x"]
			hi = g["x"] + g["w"]
			if g["w"] <= 0:                 # zero-width rect: only the menu panel (popup) or the screen limits the text
				mx, _, mw, _, _, popup = menu_frame(m)
				lo, hi = (mx, mx + mw) if popup else (0, SCREEN_W)
			anchor = g["x"] + g["ib"] + num(it.get("textalignx"), 0)
			row = ty in (4, 9, 10, 11, 12, 13, 15)
			if not row:
				have = room(al, anchor, lo, hi, tw)
				res.append(Finding(lang=lang, where=where, role="label", en=text, tr=T(text), en_w=ew, tr_w=tw, have=have,
				                   note=f"align {al}, anchor {anchor:.0f}, rect {lo:.0f}..{hi:.0f}"))
				continue
			# ---- rows: label (+ value drawn 8 px after the label end)
			if ty in (4, 9, 15):
				# typical value, not the worst case: at most EDIT_CHARS digits wide (names are rarely full length)
				vw = lambda f: int(min(EDIT_CHARS, num(it.get("maxpaintchars"), num(it.get("maxchars"), 4))) * met.width("0", font, scale))
			elif ty == 10:
				vw = lambda f: SLIDER_W
			elif ty == 13:
				vw = lambda f: met.width("MWHEELDOWN", font, scale)
			else:
				vw = lambda f: max([met.width(f(s), font, scale) for s in vals] or [0])
			s_e, e_e = span(it, g, ew)
			s_t, e_t = span(it, g, tw)
			if al == 2:
				res.append(Finding(lang=lang, where=where, role="label", en=text, tr=T(text), en_w=ew, tr_w=tw,
				                   have=anchor - lo, note=f"right-aligned at {anchor:.0f}, left limit {lo:.0f}"))
				for s in vals:
					res.append(Finding(lang=lang, where=where, role="value", en=s, tr=T(s), en_w=met.width(s, font, scale),
					                   tr_w=met.width(T(s), font, scale), have=hi - (e_t + 8),
					                   note=f"value starts at {e_t + 8:.0f}, right limit {hi:.0f}"))
				if ty in (4, 9, 10, 13, 15):
					v = vw(T)
					res.append(Finding(lang=lang, where=where, role="value", en="<value>", tr="<value>", en_w=v, tr_w=v,
					                   have=hi - (e_t + 8), note="edit/slider/bind value area"))
			else:
				ve, vt = vw(lambda s: s), vw(T)
				full_e = (e_e + 8 + ve) - s_e
				full_t = (e_t + 8 + vt) - s_t
				res.append(Finding(lang=lang, where=where, role="label+value", en=text, tr=T(text), en_w=full_e, tr_w=full_t,
				                   have=hi - s_t, note=f"label {tw}px + 8 + value {vt}px (en {ew} + {ve}), right limit {hi:.0f}"))
	return res


def width_center(start, w):
	return start + w / 2


def wrapped_item(met, m, it, g, text, ttext, font, scale, where, lang):
	"""autowrapped menu label: lines and height."""
	al = int(num(it.get("textalign"), 0))
	res = []
	for tag, s in (("en", text), ("tr", ttext)):
		pass
	ln_e = wrap_lines(met, text, font, scale, g["w"])
	ln_t = wrap_lines(met, ttext, font, scale, g["w"])
	h_e = met.height(text, font, scale)
	h_t = met.height(ttext, font, scale)
	ay = num(it.get("textaligny"), 0)
	last_e = ay + (len(ln_e) - 1) * (h_e + 5)
	last_t = ay + (len(ln_t) - 1) * (h_t + 5)
	res.append(Finding(lang=lang, where=where, role="wrapped", en=text, tr=ttext, en_w=last_e, tr_w=last_t, have=g["h"],
	                   note=f"{len(ln_e)} -> {len(ln_t)} lines, last baseline {last_e:.0f} -> {last_t:.0f} of {g['h']:.0f}"))
	return res


def wrap_lines(met, text, font, scale, width):
	"""Item_Text_AutoWrapped_Paint, line by line (returns the drawn lines)."""
	text = text.replace("\r", " ")
	lines, buf = [], ""
	p = 0
	newline = 0
	n = len(text)
	while True:
		c = text[p] if p < n else "\0"
		if c in " \t\n\0":
			newline = len(buf)
			newptr = p + 1
		tw = met.width(buf, font, scale)
		if (newline and tw > width) or c in "\n\0":
			if buf:
				lines.append(buf[:newline] if newline else buf)
			if c == "\0":
				break
			p = newptr
			buf = ""
			newline = 0
			continue
		buf += c
		p += 1
	return lines


# --------------------------------------------------------------------------------------------- text pages
def page_meta():
	pages = json.loads((ROOT / "tools/l10n/build/text_files.json").read_text())
	out = {}
	for f in pages:
		out[f["file"]] = f
	return out


def textaligny_lookup(menus):
	d = {}
	for m in menus:
		for it in m["items"]:
			if it.get("textfile"):
				d[(m["file"], (it.get("name") or [""])[0], it.get("line"))] = (num(it.get("textaligny"), 0),
				                                                              num(it.get("textalignx"), 0))
	return d


def check_pages(met, menus, lang, verbose=False):
	meta = page_meta()
	ay = textaligny_lookup(menus)
	res = []
	d = LANG_DIR / lang / "text"
	for f in sorted(d.glob("*.txt")):
		info = meta.get(f.name)
		raw = f.read_bytes()
		try:
			txt = raw.decode("utf-8")
		except UnicodeDecodeError:
			res.append(Finding(lang=lang, where=f.name, role="page", en="", tr="", en_w=0, tr_w=1, have=0, note="NOT UTF-8"))
			continue
		lat = to_latin1(txt)
		if len(lat) > MAX_PAGE_BYTES:
			res.append(Finding(lang=lang, where=f.name, role="page", en="", tr="", en_w=0, tr_w=len(lat), have=MAX_PAGE_BYTES,
			                   note=f"{len(lat)} Latin-1 bytes"))
		if b"?" in lat and "?" not in txt:
			res.append(Finding(lang=lang, where=f.name, role="page", en="", tr="", en_w=0, tr_w=1, have=0,
			                   note="characters not in Latin-1 become '?'"))
		if not info:
			continue
		en_path = ROOT / "tools/l10n/build/en/text" / f.name
		en = en_path.read_text(encoding="utf-8", errors="replace") if en_path.exists() else ""
		seen = set()
		for item in info["items"]:
			key = (item["menu"], item["item"], tuple(item["rect"]), item.get("font"), item["textscale"])
			if key in seen:
				continue
			seen.add(key)
			font = {"UI_FONT_NORMAL": 1, "UI_FONT_BIG": 2, "UI_FONT_SMALL": 3, "UI_FONT_HANDWRITING": 4}.get(item.get("font"), 0)
			sc = item["textscale"]
			x, y, w, h = item["rect"]
			aly, alx = ay.get((item["menu"], item["item"], item["line"]), (0, 0))
			le = wrap_lines(met, to_latin1(en).decode("latin-1"), font, sc, w)
			lt = wrap_lines(met, txt, font, sc, w)
			he, ht = met.height(en, font, sc), met.height(txt, font, sc)
			last_e = aly + (len(le) - 1) * (he + 5)
			last_t = aly + (len(lt) - 1) * (ht + 5)
			# longest unbreakable overflow: a single word wider than the rect can not be wrapped
			over_line = max(lt, key=lambda l: met.width(l, font, sc), default="")
			over = met.width(over_line, font, sc)
			res.append(Finding(lang=lang, where=f"{f.name} in {item['menu']}:{item['item']}", role="page",
			                   en="", tr="", en_w=last_e, tr_w=last_t, have=h - aly,
			                   note=f"{len(le)} -> {len(lt)} lines (rect {w:.0f}x{h:.0f}, font {Metrics.pt(font, sc)}pt)"
			                        + (f", widest line {over}px > {w:.0f}" if over > w else "")))
			# The engine's wrap lets the last glyph of a line spill over (the width test runs one character late), so
			# up to one wide glyph past the rect is normal English behaviour; more means one word is too long to wrap.
			if over > w + met.width("W", font, sc):
				res.append(Finding(lang=lang, where=f"{f.name} in {item['menu']}:{item['item']}", role="pageword", en="", tr=over_line,
				                   en_w=max((met.width(l, font, sc) for l in le), default=0), tr_w=over, have=w,
				                   note="a single word wider than the rect (cannot wrap)"))
	return res


# --------------------------------------------------------------------------------------------- special strings
def check_special(met, tr, lang):
	"""Strings drawn by the engine/cgame outside menu items; widths vs hand-derived room."""
	res = []

	def T(s):
		return tr.get(s, s)

	# key binding status line: UI_KEYBINDSTATUS ownerdraw at x=40, scale .2 (default font -> small), screen edge 640
	for key in ("Waiting for new key... Press ESCAPE to cancel", "Press ENTER or CLICK to change, Press BACKSPACE to clear"):
		res.append(Finding(lang=lang, where="controls*.menu keyBindStatus", role="status", en=key, tr=T(key),
		                   en_w=met.width(key, 0, 0.2), tr_w=met.width(T(key), 0, 0.2), have=SCREEN_W - 40,
		                   note="drawn from x=40, scale .2"))
	# savegame list date column: x = listbox + 4 + 142, listbox 300 wide minus 16 scroll bar; scale .23 default font
	months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
	digit = max(range(10), key=lambda d: met.width(str(d), 0, 0.23))
	tail = f" 30, 2026   {digit}{digit}:{digit}{digit}"
	worst_e = max(months, key=lambda s: met.width(s + tail, 0, 0.23))
	worst_t = max((T(s) for s in months), key=lambda s: met.width(s + tail, 0, 0.23))
	res.append(Finding(lang=lang, where="ingame_load/save lists: date column", role="date", en=worst_e + tail, tr=worst_t + tail,
	                   en_w=met.width(worst_e + tail, 0, 0.23), tr_w=met.width(worst_t + tail, 0, 0.23), have=300 - 16 - 146,
	                   note="widest month; column 2 starts at 146"))
	for key in ("(old save ver: %d)", "(old savegame ver: %d)", "(old savegame)"):
		s = key.replace("%d", "99")
		res.append(Finding(lang=lang, where="savegame list/info text", role="status", en=s, tr=T(key).replace("%d", "99"),
		                   en_w=met.width(s, 0, 0.23), tr_w=met.width(T(key).replace("%d", "99"), 0, 0.23),
		                   have=300 - 16 - 146 if "ver" in key else 148,
		                   note="date column (158 wide) / info panel (148 wide, wraps)" if "ver" not in key else "date column"))
	return res


def check_maxlen(tr, lang):
	"""Catalog strings with a rough character limit (HUD hints, centerprints)."""
	cat = json.loads((ROOT / "tools/l10n/build/catalog.json").read_text())
	res = []
	for e in cat:
		ml = e.get("maxlen")
		if not ml or any(w.endswith(")") and ".menu:" in w for w in e["where"]):
			continue
		if not any(w.split(":")[0].endswith((".c",)) for w in e["where"]):
			continue
		t = tr.get(e["key"], e["key"])
		res.append(Finding(lang=lang, where=e["where"][0], role="chars", en=e["key"], tr=t, en_w=len(e["key"]), tr_w=len(t),
		                   have=ml, note="character limit from catalog"))
	return res


# --------------------------------------------------------------------------------------------- consistency
CONTROL_MAP = {"attack": "Attack:  ", "activate": "Activate:  ", "jump": "Jump:  ", "crouch": "Crouch:  ",
               "kick": "Kick:  ", "reload": "Reload Weapon:  ", "auto pick-up": "Auto Item Pickup:  ",
               "zoom in": "Zoom In:  ", "zoom out": "Zoom Out:  ", "alternate fire": "Switch to Alternate:  ",
               "secondary fire": "Switch to Alternate:  ", "run": "Run / Walk:  ", "auto run": "Always Run:  "}
EXTRA_QUOTED = {"hand", "mano", "ladder", "leiter", "escalera", "zerstörbar", "rompible", "x"}


def check_controls(tr, lang):
	"""Quoted terms in training*.txt that are neither a translated Controls label nor a known HUD word."""
	ok = {tr.get(v, "").strip().rstrip(":").strip().lower() for v in CONTROL_MAP.values()} | EXTRA_QUOTED
	n = 0
	for f in sorted((LANG_DIR / lang / "text").glob("training*.txt")):
		for q in re.findall(r"'([^'\n]{2,32})'", f.read_text(encoding="utf-8")):
			if q.lower() not in ok:
				print(f"CONTROL   {lang} {f.name}: '{q}' is not a translated Controls label")
				n += 1
	return n


# --------------------------------------------------------------------------------------------- main
def report(findings, verbose):
	bad = [f for f in findings if f.status() == "FAIL"]
	tol = [f for f in findings if f.status() == "tolerated"]
	for f in findings:
		st = f.status()
		if st == "ok" and not verbose:
			continue
		if st == "tolerated" and not verbose:
			continue
		print(f"{st:9} {f.lang} {f.where} [{f.role}] {f.en!r} -> {f.tr!r}  en {f.en_w:.0f} tr {f.tr_w:.0f} room {f.have:.0f}  {f.note}"
		      + (f"  font={int(f.font)} scale={f.scale}" if st == "FAIL" and f.role in ("label", "value", "label+value") else ""))
	return len(bad), len(tol)


def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("--lang", action="append")
	ap.add_argument("-v", action="store_true", help="also list items that fit")
	ap.add_argument("--no-pages", action="store_true")
	ap.add_argument("--tolerated", action="store_true", help="also list tolerated (English overflows too)")
	ap.add_argument("--json", help="write all findings to this file")
	ap.add_argument("--width", nargs=3, metavar=("TEXT", "FONT", "SCALE"), help="print the pixel width of TEXT")
	a = ap.parse_args()
	langs = a.lang or ["de", "es"]
	met = Metrics()
	if a.width:
		print(met.width(a.width[0], int(a.width[1]), float(a.width[2])))
		return 0
	menus, _ = load_all_menus()
	allf = []
	total_bad = 0
	for lang in langs:
		tr = {}
		for k, v, _ in parse_strings(LANG_DIR / lang / "strings.txt"):
			tr[k] = v
		fs = check_menu_items(met, menus, tr, lang) + check_special(met, tr, lang) + check_maxlen(tr, lang)
		if not a.no_pages:
			fs += check_pages(met, menus, lang)
			total_bad += check_controls(tr, lang)
		allf += fs
		if a.tolerated:
			for f in fs:
				if f.status() == "tolerated":
					print(f"tolerated {f.lang} {f.where} [{f.role}] {f.en!r} -> {f.tr!r}  en {f.en_w:.0f} tr {f.tr_w:.0f} room {f.have:.0f}  {f.note}")
		b, t = report(fs, a.v)
		print(f"== {lang}: {len(fs)} measurements, {b} FAIL, {t} tolerated")
		total_bad += b
	if a.json:
		Path(a.json).write_text(json.dumps([f.__dict__ | {"status": f.status()} for f in allf], indent=1, ensure_ascii=False))
	return 1 if total_bad else 0


if __name__ == "__main__":
	sys.exit(main())
