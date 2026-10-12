from __future__ import annotations

import time
from pathlib import Path

from PIL import Image


def save_game_format(
	img: Image.Image,
	dest: Path,
	*,
	source_suffix: str,
	jpeg_quality: int = 90,
) -> tuple[int, float]:
	"""Write JPG/TGA matching the source extension. Returns (bytes, encode_ms)."""
	dest.parent.mkdir(parents=True, exist_ok=True)
	suf = source_suffix.lower()
	t0 = time.perf_counter()
	if suf in (".jpg", ".jpeg"):
		rgb = img.convert("RGB")
		rgb.save(
			dest,
			format="JPEG",
			quality=jpeg_quality,
			optimize=True,
			subsampling=0,
		)
	elif suf == ".tga":
		# Keep alpha when present; RLE when Pillow supports it.
		to_save = img.convert("RGBA") if "A" in img.getbands() else img.convert("RGB")
		try:
			to_save.save(dest, format="TGA", compression="tga_rle")
		except (TypeError, ValueError, OSError):
			to_save.save(dest, format="TGA")
	elif suf == ".png":
		img.save(dest, format="PNG", optimize=True)
	else:
		# Fallback: keep pixels as PNG but unusual for RTCW.
		img.save(dest, format="PNG")
	elapsed_ms = (time.perf_counter() - t0) * 1000.0
	return dest.stat().st_size, elapsed_ms


def save_preview_png(img: Image.Image, dest: Path) -> None:
	dest.parent.mkdir(parents=True, exist_ok=True)
	img.save(dest, format="PNG")
