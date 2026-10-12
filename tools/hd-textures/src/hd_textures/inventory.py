from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

from .paths import SP_PAKS, is_image_member


@dataclass(frozen=True)
class PakImage:
	pak: str
	path: str  # virtual path inside pk3, forward slashes
	size: int


def is_font_path(path: str) -> bool:
	"""True for UI glyph atlases and menu prop fonts (not world textures)."""
	lower = path.lower().replace("\\", "/")
	if lower.startswith("fonts/"):
		return True
	name = Path(lower).name
	return lower.startswith("menu/art/") and name.startswith("font")


def list_images(data_dir: Path) -> list[PakImage]:
	found: list[PakImage] = []
	seen: set[str] = set()
	# Later paks override earlier ones in-game; inventory keeps first occurrence
	# but records all for counting. For extract we prefer the highest-priority pak.
	by_path: dict[str, PakImage] = {}
	for pak_name in SP_PAKS:
		pak_path = data_dir / pak_name
		if not pak_path.is_file():
			continue
		with zipfile.ZipFile(pak_path) as zf:
			for info in zf.infolist():
				name = info.filename.replace("\\", "/")
				if not is_image_member(name):
					continue
				key = name.lower()
				entry = PakImage(pak=pak_name, path=name, size=info.file_size)
				found.append(entry)
				# Later SP pak wins (same as fs override within main).
				by_path[key] = entry
				seen.add(key)
	# Return deduped winning set, sorted.
	return sorted(by_path.values(), key=lambda e: e.path.lower())


def summarize(images: list[PakImage]) -> dict[str, int]:
	by_ext: dict[str, int] = {}
	for img in images:
		ext = Path(img.path).suffix.lower()
		by_ext[ext] = by_ext.get(ext, 0) + 1
	by_ext["total"] = len(images)
	return by_ext
