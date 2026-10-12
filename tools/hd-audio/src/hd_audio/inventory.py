from __future__ import annotations

import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .paths import SP_PAKS, category_for, is_audio_member


@dataclass(frozen=True)
class PakAudio:
	pak: str
	path: str  # virtual path inside pk3, forward slashes
	size: int

	@property
	def category(self) -> str:
		return category_for(self.path)


def list_audio(data_dir: Path) -> list[PakAudio]:
	by_path: dict[str, PakAudio] = {}
	for pak_name in SP_PAKS:
		pak_path = data_dir / pak_name
		if not pak_path.is_file():
			continue
		with zipfile.ZipFile(pak_path) as zf:
			for info in zf.infolist():
				name = info.filename.replace("\\", "/")
				if not is_audio_member(name):
					continue
				key = name.lower()
				by_path[key] = PakAudio(pak=pak_name, path=name, size=info.file_size)
	return sorted(by_path.values(), key=lambda e: e.path.lower())


def summarize(entries: list[PakAudio]) -> dict[str, int]:
	by_ext: Counter[str] = Counter()
	by_cat: Counter[str] = Counter()
	for e in entries:
		by_ext[Path(e.path).suffix.lower()] += 1
		by_cat[e.category] += 1
	out: dict[str, int] = {"total": len(entries)}
	out.update({f"ext{k}": v for k, v in sorted(by_ext.items())})
	out.update({f"cat_{k}": v for k, v in sorted(by_cat.items())})
	return out
