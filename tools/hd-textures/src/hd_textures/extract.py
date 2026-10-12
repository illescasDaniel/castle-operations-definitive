from __future__ import annotations

import zipfile
from pathlib import Path

from .inventory import PakImage, list_images
from .paths import SP_PAKS


def _pak_index(data_dir: Path) -> dict[str, tuple[str, zipfile.ZipInfo]]:
	"""Map lowercased virtual path → (pak_name, ZipInfo), later pak wins."""
	index: dict[str, tuple[str, zipfile.ZipInfo]] = {}
	for pak_name in SP_PAKS:
		pak_path = data_dir / pak_name
		if not pak_path.is_file():
			continue
		with zipfile.ZipFile(pak_path) as zf:
			for info in zf.infolist():
				name = info.filename.replace("\\", "/")
				index[name.lower()] = (pak_name, info)
	return index


def extract_paths(data_dir: Path, virtual_paths: list[str], dest_root: Path) -> list[Path]:
	"""Extract specific virtual paths into dest_root preserving layout."""
	# Build live open handles lazily per pak.
	wanted = [p.replace("\\", "/") for p in virtual_paths]
	images = {img.path.lower(): img for img in list_images(data_dir)}
	written: list[Path] = []
	open_zips: dict[str, zipfile.ZipFile] = {}
	try:
		for vpath in wanted:
			key = vpath.lower()
			img = images.get(key)
			if img is None:
				raise SystemExit(f"Not found in SP paks: {vpath}")
			zf = open_zips.get(img.pak)
			if zf is None:
				zf = zipfile.ZipFile(data_dir / img.pak)
				open_zips[img.pak] = zf
			out = dest_root / img.path
			out.parent.mkdir(parents=True, exist_ok=True)
			with zf.open(img.path) as src, out.open("wb") as dst:
				dst.write(src.read())
			written.append(out)
	finally:
		for zf in open_zips.values():
			zf.close()
	return written


def extract_all(data_dir: Path, dest_root: Path, images: list[PakImage] | None = None) -> int:
	"""Extract full winning image set. Returns file count."""
	if images is None:
		images = list_images(data_dir)
	open_zips: dict[str, zipfile.ZipFile] = {}
	count = 0
	try:
		for img in images:
			zf = open_zips.get(img.pak)
			if zf is None:
				zf = zipfile.ZipFile(data_dir / img.pak)
				open_zips[img.pak] = zf
			out = dest_root / img.path
			out.parent.mkdir(parents=True, exist_ok=True)
			with zf.open(img.path) as src, out.open("wb") as dst:
				dst.write(src.read())
			count += 1
	finally:
		for zf in open_zips.values():
			zf.close()
	return count
