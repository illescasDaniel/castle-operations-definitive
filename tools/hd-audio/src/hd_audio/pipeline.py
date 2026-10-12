from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .device import DeviceInfo
from .enhance import enhance_file
from .extend import audiosr_model_for_category, extend_audiosr
from .master import match_loudness
from .music import CURRENT_MUSIC_MODE, remaster_music
from .paths import category_for
from .wavio import load_wav, save_wav, truncate_seconds

# Recipe name → enhance mode (none | denoise | enhance)
RECIPES: dict[str, str] = {
	"sr_only": "none",
	"denoise_sr": "denoise",
	"enhance_sr": "enhance",
}


@dataclass
class RemasterStats:
	path: str
	category: str
	recipe: str
	enhance_backend: str
	extend_backend: str
	src_rate: int
	out_rate: int
	src_peak: float
	out_peak: float
	enhance_ms: float
	extend_ms: float
	total_ms: float
	out_bytes: int

	def to_dict(self) -> dict:
		return asdict(self)


def remaster_file(
	src: Path,
	dest: Path,
	*,
	recipe: str,
	device: DeviceInfo,
	work_dir: Path,
	virtual_path: str | None = None,
	ddim_steps: int = 50,
	guidance_scale: float = 3.5,
	seed: int = 42,
	max_seconds: float | None = None,
	music_mode: str | None = None,
) -> RemasterStats:
	if recipe not in RECIPES:
		raise SystemExit(f"Unknown recipe {recipe!r}; choose from {sorted(RECIPES)}")

	t0 = time.perf_counter()
	parts = src.as_posix().replace("\\", "/")
	if virtual_path:
		vpath = virtual_path.replace("\\", "/")
	elif "sound/" in parts:
		vpath = parts[parts.index("sound/") :]
	else:
		vpath = src.name
	category = category_for(vpath)

	ref_audio, src_rate = load_wav(src)
	if max_seconds is not None:
		ref_audio = truncate_seconds(ref_audio, src_rate, max_seconds)
		cut = work_dir / "cut_src.wav"
		save_wav(cut, ref_audio, src_rate)
		src_for_pipe = cut
	else:
		src_for_pipe = src

	from .wavio import peak

	# Music uses a dedicated path (diffusion on stereo was adding haze).
	if category == "music":
		mode = music_mode or CURRENT_MUSIC_MODE
		mres = remaster_music(
			src_for_pipe,
			dest,
			mode=mode,
			device=device,
			work_dir=work_dir,
			ddim_steps=max(ddim_steps, 60),
			guidance_scale=min(guidance_scale, 2.0) if mode != "resample" else guidance_scale,
			seed=seed,
		)
		out_audio, out_rate = load_wav(dest)
		return RemasterStats(
			path=vpath,
			category=category,
			recipe=f"{recipe}+music:{mode}",
			enhance_backend="music_bypass",
			extend_backend=mres.backend,
			src_rate=src_rate,
			out_rate=out_rate,
			src_peak=peak(ref_audio),
			out_peak=peak(out_audio),
			enhance_ms=0.0,
			extend_ms=mres.ms,
			total_ms=(time.perf_counter() - t0) * 1000,
			out_bytes=dest.stat().st_size,
		)

	enh_path = work_dir / "enhanced.wav"
	enh = enhance_file(
		src_for_pipe,
		enh_path,
		category=category,
		device=device,
		mode=RECIPES[recipe],
	)

	ext_path = work_dir / "extended.wav"
	model_name = audiosr_model_for_category(category)
	ext = extend_audiosr(
		enh.path,
		ext_path,
		model_name=model_name,
		device=device,
		ddim_steps=ddim_steps,
		guidance_scale=guidance_scale,
		seed=seed,
		category=category,
	)

	out_audio, out_rate = load_wav(ext.path)
	mastered = match_loudness(out_audio, ref_audio, mode="peak")
	out_bytes = save_wav(dest, mastered, out_rate)

	return RemasterStats(
		path=vpath,
		category=category,
		recipe=recipe,
		enhance_backend=enh.backend,
		extend_backend=ext.backend,
		src_rate=src_rate,
		out_rate=out_rate,
		src_peak=peak(ref_audio),
		out_peak=peak(mastered),
		enhance_ms=enh.ms,
		extend_ms=ext.ms,
		total_ms=(time.perf_counter() - t0) * 1000,
		out_bytes=out_bytes,
	)
