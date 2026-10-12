from __future__ import annotations

import os
from pathlib import Path

DEFAULT_RTCW_DATA = (
	Path.home() / ".local/share/Steam/steamapps/common/Return to Castle Wolfenstein/Main"
)

SP_PAKS = ("pak0.pk3", "sp_pak1.pk3", "sp_pak2.pk3", "sp_pak3.pk3", "sp_pak4.pk3")

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".tga", ".png", ".bmp", ".pcx"}


def tool_root() -> Path:
	# .../tools/hd-textures
	return Path(__file__).resolve().parents[2]


def resolve_data_dir(explicit: str | None) -> Path:
	raw = explicit or os.environ.get("RTCW_DATA") or str(DEFAULT_RTCW_DATA)
	path = Path(raw).expanduser().resolve()
	if not path.is_dir():
		raise SystemExit(f"RTCW data directory not found: {path}")
	return path


def is_image_member(name: str) -> bool:
	lower = name.lower().replace("\\", "/")
	if lower.endswith("/"):
		return False
	# Skip lightmaps and common non-diffuse junk.
	if "/maps/" in lower and "lightmap" in lower:
		return False
	suf = Path(lower).suffix
	return suf in IMAGE_SUFFIXES
