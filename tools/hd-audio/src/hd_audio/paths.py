from __future__ import annotations

import os
from pathlib import Path

DEFAULT_RTCW_DATA = (
	Path.home() / ".local/share/Steam/steamapps/common/Return to Castle Wolfenstein/Main"
)

SP_PAKS = ("pak0.pk3", "sp_pak1.pk3", "sp_pak2.pk3", "sp_pak3.pk3", "sp_pak4.pk3")

AUDIO_SUFFIXES = {".wav", ".ogg", ".opus"}

# Locked after pilot A/B (2026-10-11): sr_only — denoise/enhance dulled VO FX.
CURRENT_RECIPE = "sr_only"

TARGET_RATE = 48000


def tool_root() -> Path:
	# .../tools/hd-audio
	return Path(__file__).resolve().parents[2]


def resolve_data_dir(explicit: str | None) -> Path:
	raw = explicit or os.environ.get("RTCW_DATA") or str(DEFAULT_RTCW_DATA)
	path = Path(raw).expanduser().resolve()
	if not path.is_dir():
		raise SystemExit(f"RTCW data directory not found: {path}")
	return path


def is_audio_member(name: str) -> bool:
	lower = name.lower().replace("\\", "/")
	if lower.endswith("/") or not lower.startswith("sound/"):
		return False
	# Skip script/metadata; remaster PCM (and rare ogg/opus) only.
	if lower.endswith((".sounds", ".txt", ".dat")):
		return False
	return Path(lower).suffix in AUDIO_SUFFIXES


def category_for(path: str) -> str:
	"""speech | music | sfx — drives enhance model choice."""
	lower = path.lower().replace("\\", "/")
	if lower.startswith("sound/music/"):
		return "music"
	if lower.startswith("sound/scenaric/"):
		return "speech"
	# Player effort / pain / death VO (not footsteps).
	if "/player/bj2/" in lower or "/player/bj/" in lower:
		return "speech"
	if any(
		tok in Path(lower).name
		for tok in ("pain", "death", "gasp", "gurp", "fall", "falling")
	) and lower.startswith("sound/player/"):
		return "speech"
	return "sfx"
