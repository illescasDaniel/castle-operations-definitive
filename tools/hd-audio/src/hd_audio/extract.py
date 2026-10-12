from __future__ import annotations

import zipfile
from pathlib import Path

from .inventory import PakAudio, list_audio


def extract_paths(data_dir: Path, virtual_paths: list[str], dest_root: Path) -> list[Path]:
	"""Extract specific virtual paths into dest_root preserving layout."""
	wanted = [p.replace("\\", "/") for p in virtual_paths]
	index = {a.path.lower(): a for a in list_audio(data_dir)}
	written: list[Path] = []
	open_zips: dict[str, zipfile.ZipFile] = {}
	try:
		for vpath in wanted:
			key = vpath.lower()
			meta = index.get(key)
			if meta is None:
				raise SystemExit(f"Not found in SP paks: {vpath}")
			zf = open_zips.get(meta.pak)
			if zf is None:
				zf = zipfile.ZipFile(data_dir / meta.pak)
				open_zips[meta.pak] = zf
			out = dest_root / meta.path
			out.parent.mkdir(parents=True, exist_ok=True)
			with zf.open(meta.path) as src, out.open("wb") as dst:
				dst.write(src.read())
			written.append(out)
	finally:
		for zf in open_zips.values():
			zf.close()
	return written


def extract_all(
	data_dir: Path, dest_root: Path, entries: list[PakAudio] | None = None
) -> int:
	if entries is None:
		entries = list_audio(data_dir)
	open_zips: dict[str, zipfile.ZipFile] = {}
	count = 0
	try:
		for meta in entries:
			zf = open_zips.get(meta.pak)
			if zf is None:
				zf = zipfile.ZipFile(data_dir / meta.pak)
				open_zips[meta.pak] = zf
			out = dest_root / meta.path
			out.parent.mkdir(parents=True, exist_ok=True)
			with zf.open(meta.path) as src, out.open("wb") as dst:
				dst.write(src.read())
			count += 1
	finally:
		for zf in open_zips.values():
			zf.close()
	return count
