"""Generate mod/codmod/lang/{en,de,es}/flag.tga (64x40, 32-bit uncompressed TGA). Stdlib only.

  python3 tools/l10n/flags.py
"""
import struct
from pathlib import Path

W, H = 64, 40
LANG = Path(__file__).resolve().parents[2] / "mod" / "codmod" / "lang"

RED, BLUE, WHITE = (178, 34, 52), (60, 59, 110), (255, 255, 255)   # US Old Glory
BLACK, DE_RED, GOLD = (0, 0, 0), (221, 0, 0), (255, 206, 0)
ES_RED, ES_YELLOW = (170, 21, 27), (241, 191, 0)


def new(color):
	return [[color] * W for _ in range(H)]


def rect(img, x0, y0, x1, y1, color):
	for y in range(max(0, y0), min(H, y1)):
		for x in range(max(0, x0), min(W, x1)):
			img[y][x] = color


def bands(img, colors, weights):
	total, y = sum(weights), 0
	for i, (c, w) in enumerate(zip(colors, weights)):
		y1 = H if i == len(colors) - 1 else y + round(H * w / total)
		rect(img, 0, y, W, y1, c)
		y = y1


def usa():
	img = new(WHITE)
	for i in range(13):                       # 13 stripes, red first
		if i % 2 == 0:
			rect(img, 0, round(i * H / 13), W, round((i + 1) * H / 13), RED)
	cw, ch = round(W * 0.4), round(H * 7 / 13)
	rect(img, 0, 0, cw, ch, BLUE)
	for r in range(9):                        # 50 stars: alternating rows of 6 and 5
		n = 6 if r % 2 == 0 else 5
		for c in range(n):
			x = round((c * 2 + (0 if n == 6 else 1) + 1) * cw / 12)
			y = round((r + 1) * ch / 10)
			rect(img, x - 1, y - 1, x + 1, y + 1, WHITE)
	return img


def germany():
	img = new(BLACK)
	bands(img, [BLACK, DE_RED, GOLD], [1, 1, 1])
	return img


def spain():
	img = new(ES_RED)
	bands(img, [ES_RED, ES_YELLOW, ES_RED], [1, 2, 1])
	return img


def write_tga(path, img):
	hdr = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, W, H, 32, 8)   # bottom-left origin, 8 alpha bits
	rows = [b"".join(bytes((b, g, r, 255)) for r, g, b in row) for row in reversed(img)]
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_bytes(hdr + b"".join(rows))


if __name__ == "__main__":
	for code, make in (("en", usa), ("de", germany), ("es", spain)):
		write_tga(LANG / code / "flag.tga", make())
		print("wrote", LANG / code / "flag.tga")
