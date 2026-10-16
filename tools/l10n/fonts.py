"""Audit RTCW's UI bitmap fonts for Latin-1 coverage and render preview lines.

  python3 tools/l10n/fonts.py            audit every font + write previews
  python3 tools/l10n/fonts.py --no-preview

Findings (2026-10-16): the retail fonts fonts/fontImage_{12,16,17,24}.dat (the ones SP uses) already contain real
glyphs for every Latin-1 letter German and Spanish need (A-umlaut ... y-acute, inverted ? and !, guillemets, sharp s).
Only 0xA0 (no-break space) and 0xFF (y-diaeresis) are empty; the MP-only size 20 also lacks 0xD6 (O-diaeresis).
No glyph synthesis is therefore needed.

TGA orientation matters when auditing: the pages are 32-bit TGAs with a bottom-left origin flag. The engine (rend2
tr_image_tga.c) honours it, so memory row 0 is the LAST file row, and the .dat's t coordinates count from there.
Reading the file rows in file order mirrors the page vertically and reports random glyphs as empty; that mistake
produced the old hardcoded lang_missing* lists in ui_lang.c.

A glyph is "missing" when its cell has no pixels: imageWidth == 0 / imageHeight == 0 / empty shaderName (the runtime
test in ui_lang.c), or an all-transparent bitmap (checked here as well).

Preview text is composed as the UI does (ui_main.c Text_Paint): quad of imageWidth x imageHeight at
(x, baseline - top), then x += xSkip. Pure stdlib; PNGs are written with zlib.
"""
import struct, sys, zlib, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GLYPH = struct.Struct("<7i4fi32s")          # glyphInfo_t, 80 bytes, little endian (readInt/readFloat in tr_font.c)
NGLYPH = 256
SIZES = (12, 16, 17, 20, 24)
SAMPLE = "Ä Ö Ü ä ö ü ß  Á É Í Ó Ú Ñ á é í ó ú ñ ¿ ¡  Español Übersetzt Atrás Optionen Lautstärke « » °"
NEEDED = "ÀÁÂÄÇÈÉÊËÍÏÑÓÔÖÚÜàáâäçèéêëíïñóôöúüß¿¡«»°·"
OUT = ROOT / "tools" / "l10n" / "build" / "fontpreview"


def find_main():
	p = ROOT / "run" / "main" / "pak0.pk3"
	if p.exists():
		return p.resolve().parent
	sys.exit("fonts.py: cannot find the RTCW Main/ directory (run/main/pak0.pk3)")


def load_files(main):
	"""{name: bytes} for fonts/fontImage_* from the paks; mp_* first so pak0/sp_pak* override them."""
	paks = sorted(main.glob("*.pk3"), key=lambda p: (not p.name.startswith("mp_"), p.name))
	out = {}
	for p in paks:
		with zipfile.ZipFile(p) as z:
			for n in z.namelist():
				if n.startswith("fonts/fontImage_") and not n.endswith("/"):
					out[n] = z.read(n)
	return out


def read_tga(data):
	"""Decode a TGA (type 2 or 10, 24/32 bit) -> (w, h, rows), rows[y] = RGBA bytearray, y=0 at the top as the
	engine sees it (bottom-left-origin files are reversed)."""
	idlen, cmtype, itype = data[0], data[1], data[2]
	w, h = struct.unpack_from("<HH", data, 12)
	bpp, desc = data[16], data[17]
	assert cmtype == 0 and itype in (2, 10) and bpp in (24, 32), "unsupported TGA"
	bpb = bpp // 8
	pos = 18 + idlen
	n = w * h
	if itype == 2:
		raw = data[pos:pos + n * bpb]
	else:
		raw = bytearray()
		while len(raw) < n * bpb:
			c = data[pos]; pos += 1
			cnt = (c & 127) + 1
			if c & 128:
				raw += data[pos:pos + bpb] * cnt; pos += bpb
			else:
				raw += data[pos:pos + cnt * bpb]; pos += cnt * bpb
		raw = bytes(raw[:n * bpb])
	rows = []
	for y in range(h):
		r = bytearray(w * 4)
		for x in range(w):
			o = (y * w + x) * bpb
			b, g, rr = raw[o:o + 3]
			r[x * 4:x * 4 + 4] = bytes((rr, g, b, raw[o + 3] if bpb == 4 else 255))
		rows.append(r)
	if not (desc & 0x20):
		rows.reverse()
	return w, h, rows


def parse_dat(data):
	"""fontInfo_t -> (glyphs, glyphScale); glyph = [height, top, bottom, pitch, xSkip, imageWidth, imageHeight,
	s, t, s2, t2, handle, shaderName]."""
	g = []
	for i in range(NGLYPH):
		v = GLYPH.unpack_from(data, i * GLYPH.size)
		g.append(list(v[:12]) + [v[12].split(b"\0")[0].decode()])
	return g, struct.unpack_from("<f", data, NGLYPH * GLYPH.size)[0]


def glyph_alpha(files, pages, e):
	"""Alpha rows (list of lists) of a glyph cell, or None when the glyph has no cell."""
	if not e[12] or e[5] <= 0 or e[6] <= 0:
		return None
	if e[12] not in pages:
		pages[e[12]] = read_tga(files[e[12]])
	w, h, rows = pages[e[12]]
	x0, y0 = round(e[7] * w), round(e[8] * h)
	return [[rows[y][x * 4 + 3] if y < h and x < w else 0 for x in range(x0, x0 + e[5])] for y in range(y0, y0 + e[6])]


def missing(files, sz):
	g, _ = parse_dat(files[f"fonts/fontImage_{sz}.dat"])
	pages = {}
	out = []
	for i in range(160, 256):
		a = glyph_alpha(files, pages, g[i])
		if a is None or not any(any(r) for r in a):
			out.append(i)
	return out


def write_png(path, w, h, rows):
	raw = b"".join(b"\0" + bytes(r) for r in rows)

	def chunk(t, d):
		return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
	                 + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def preview(files, sz, text, scale=4):
	g, _ = parse_dat(files[f"fonts/fontImage_{sz}.dat"])
	pages = {}
	data = text.encode("latin-1")
	width = sum(g[c][4] for c in data) + 8
	base = 30
	W, H = width * scale, 44 * scale
	bg = (0x1c, 0x1e, 0x26)
	img = [bytearray(bytes(bg) * W) for _ in range(H)]
	x = 4
	for c in data:
		e = g[c]
		a = glyph_alpha(files, pages, e)
		if a:
			for yy, row in enumerate(a):
				for xx, v in enumerate(row):
					if not v:
						continue
					py, px = (base - e[1] + yy) * scale, (x + xx) * scale
					col = tuple(int(b + (255 - b) * v / 255) for b in bg)
					for dy in range(scale):
						if 0 <= py + dy < H:
							for dx in range(scale):
								if 0 <= px + dx < W:
									img[py + dy][(px + dx) * 3:(px + dx) * 3 + 3] = bytes(col)
		x += e[4]
	write_png(OUT / f"{sz}.png", W, H, img)


def main():
	files = load_files(find_main())
	for sz in SIZES:
		name = f"fonts/fontImage_{sz}.dat"
		if name not in files:
			print(f"{sz}: no {name}")
			continue
		m = missing(files, sz)
		need = [c for c in NEEDED if ord(c) in m]
		print(f"{sz}: empty Latin-1 cells {m}; needed-but-empty {need or 'none'}")
		if "--no-preview" not in sys.argv:
			preview(files, sz, SAMPLE)
	if "--no-preview" not in sys.argv:
		print(f"previews in {OUT}")


if __name__ == "__main__":
	main()
