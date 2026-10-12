from __future__ import annotations

import zipfile
from pathlib import Path

from .paths import AUDIO_SUFFIXES


def _collect_audio(src_root: Path) -> dict[str, Path]:
	out: dict[str, Path] = {}
	for path in sorted(src_root.rglob("*")):
		if not path.is_file():
			continue
		if path.suffix.lower() not in AUDIO_SUFFIXES:
			continue
		arc = path.relative_to(src_root).as_posix()
		out[arc] = path
	return out


def pack_directory(src_root: Path, pk3_path: Path) -> int:
	if not src_root.is_dir():
		raise SystemExit(f"Missing remaster output dir: {src_root}")
	pk3_path.parent.mkdir(parents=True, exist_ok=True)
	files = _collect_audio(src_root)
	with zipfile.ZipFile(pk3_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
		for arc, path in files.items():
			zf.write(path, arcname=arc)
	return len(files)


def merge_into_pk3(src_root: Path, pk3_path: Path) -> tuple[int, int]:
	if not src_root.is_dir():
		raise SystemExit(f"Missing remaster output dir: {src_root}")
	if not pk3_path.is_file():
		raise SystemExit(f"Cannot merge: pk3 does not exist: {pk3_path}")

	updates = _collect_audio(src_root)
	if not updates:
		raise SystemExit(f"No audio files under {src_root}")

	update_by_lower = {arc.lower(): (arc, path) for arc, path in updates.items()}
	replaced = 0
	kept = 0

	pk3_path.parent.mkdir(parents=True, exist_ok=True)
	tmp = pk3_path.with_suffix(pk3_path.suffix + ".merge.tmp")
	try:
		with zipfile.ZipFile(pk3_path, "r") as zin, zipfile.ZipFile(
			tmp, "w", compression=zipfile.ZIP_DEFLATED
		) as zout:
			seen_lower: set[str] = set()
			for info in zin.infolist():
				name = info.filename.replace("\\", "/")
				key = name.lower()
				if key in update_by_lower:
					_arc, path = update_by_lower[key]
					zout.write(path, arcname=name)
					seen_lower.add(key)
					replaced += 1
				else:
					zout.writestr(info, zin.read(info.filename))
					kept += 1
			for key, (arc, path) in update_by_lower.items():
				if key in seen_lower:
					continue
				zout.write(path, arcname=arc)
				replaced += 1
		tmp.replace(pk3_path)
	finally:
		if tmp.is_file():
			tmp.unlink(missing_ok=True)

	return replaced, kept
