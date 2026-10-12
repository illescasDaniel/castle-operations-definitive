from __future__ import annotations

import gc
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from scipy import signal

from .device import DeviceInfo
from .paths import TARGET_RATE
from .wavio import load_wav, save_wav

# Prefer expandable segments to reduce fragmentation on 8GB cards.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")


@dataclass
class ExtendResult:
	path: Path
	backend: str
	ms: float
	out_rate: int


_models: dict[str, object] = {}


def _console():
	from rich.console import Console

	return Console(stderr=True)


def _cuda_cleanup() -> None:
	gc.collect()
	if torch.cuda.is_available():
		try:
			torch.cuda.empty_cache()
		except Exception:
			# Some drivers trip NVML asserts inside allocator helpers; ignore.
			pass


def _build_audiosr_cuda(model_name: str):
	"""Load weights on CPU, move to CUDA, patch generate_batch for 8GB VRAM.

	Peak VRAM is kept down by staging: VAE encode → offload VAE → diffuse →
	offload UNet → VAE decode. Checkpoint is never torch.load()'d onto CUDA
	directly (that double-allocated and OOMed on 8GB).
	"""
	from audiosr import build_model

	_console().print(
		f"[cyan]AudioSR {model_name}: CPU load → CUDA (staged VAE/UNet for 8GB)[/cyan]"
	)
	_cuda_cleanup()
	model = build_model(model_name=model_name, device="cpu")
	# audiosr checks `self.device == "cuda"` (string) in a few places
	model.device = "cuda"
	model = model.to("cuda")
	# Park UNet on CPU so encode has headroom; swapped in during diffuse.
	model.model.cpu()
	_cuda_cleanup()

	free, total = torch.cuda.mem_get_info()
	_console().print(
		f"[cyan]AudioSR on CUDA (VAE resident, UNet swapped) — "
		f"{(total - free) / 1024**3:.1f} / {total / 1024**3:.1f} GiB used[/cyan]"
	)

	from audiosr.latent_diffusion.models.ddpm import DDPM

	def generate_batch_staged(batch, *args, **kwargs):
		for key, val in list(batch.items()):
			if isinstance(val, torch.Tensor):
				batch[key] = val.to("cuda", non_blocking=True)

		_cuda_cleanup()
		with torch.inference_mode():
			# Ensure VAE on GPU, UNet on CPU for encode
			model.first_stage_model.to("cuda")
			model.model.cpu()
			_cuda_cleanup()

			z, c = model.get_input(
				batch,
				model.first_stage_key,
				unconditional_prob_cfg=0.0,
			)
			model.latent_t_size = z.size(-2)
			c = model.filter_useful_cond_dict(c)

			# Swap: VAE → CPU, UNet → GPU for diffusion
			model.first_stage_model.cpu()
			z = z.contiguous()
			_cuda_cleanup()
			model.model.to("cuda")
			_cuda_cleanup()

			n_gen = kwargs.get("n_gen", 1) or 1
			batch_size = z.shape[0] * n_gen
			for cond_key in c.keys():
				if isinstance(c[cond_key], list):
					for i in range(len(c[cond_key])):
						c[cond_key][i] = torch.cat([c[cond_key][i]] * n_gen, dim=0)
				elif isinstance(c[cond_key], dict):
					for k in c[cond_key].keys():
						c[cond_key][k] = torch.cat([c[cond_key][k]] * n_gen, dim=0)
				else:
					c[cond_key] = torch.cat([c[cond_key]] * n_gen, dim=0)

			unconditional_guidance_scale = kwargs.get(
				"unconditional_guidance_scale", 1.0
			)
			unconditional_conditioning = None
			if unconditional_guidance_scale != 1.0:
				unconditional_conditioning = {}
				for key in model.cond_stage_model_metadata:
					model_idx = model.cond_stage_model_metadata[key]["model_idx"]
					unconditional_conditioning[key] = model.cond_stage_models[
						model_idx
					].get_unconditional_condition(batch_size)

			ddim_steps = kwargs.get("ddim_steps")
			use_ddim = ddim_steps is not None
			samples, _ = model.sample_log(
				cond=c,
				batch_size=batch_size,
				x_T=kwargs.get("x_T"),
				ddim=use_ddim,
				ddim_steps=ddim_steps,
				eta=kwargs.get("ddim_eta", 1.0),
				unconditional_guidance_scale=unconditional_guidance_scale,
				unconditional_conditioning=unconditional_conditioning,
				use_plms=kwargs.get("use_plms", False),
			)

			# Decode + vocoder on CPU after GPU diffuse. VAE decode needs ~1.3 GiB
			# peak that won't fit beside a parked UNet on 8 GB + desktop.
			del c
			if unconditional_conditioning is not None:
				del unconditional_conditioning
			torch.cuda.synchronize()
			samples = samples.detach().cpu()
			# Move *entire* model — vocoder/cond stages must match decode device.
			model.to("cpu")
			model.device = "cpu"
			_cuda_cleanup()
			mel = model.decode_first_stage(samples)
			del samples

			lowpass_mel = DDPM.get_input(model, batch, "lowpass_mel")
			if isinstance(lowpass_mel, torch.Tensor):
				lowpass_mel = lowpass_mel.detach().cpu()
			mel = model.mel_replace_ops(mel, lowpass_mel)

			waveform = model.mel_spectrogram_to_waveform(
				mel, savepath="", bs=None, save=False
			)
			waveform_lowpass = DDPM.get_input(model, batch, "waveform_lowpass")
			if isinstance(waveform_lowpass, torch.Tensor):
				waveform_lowpass = waveform_lowpass.detach().cpu()
			waveform = model.postprocessing(waveform, waveform_lowpass)

			max_amp = np.max(np.abs(waveform), axis=-1)
			waveform = 0.5 * waveform / np.maximum(max_amp[..., None], 1e-8)
			mean_amp = np.mean(waveform, axis=-1)[..., None]
			waveform = waveform - mean_amp

			# Restore staging: full CUDA, then park UNet for next encode
			model.device = "cuda"
			model.to("cuda")
			model.model.cpu()
			_cuda_cleanup()
			return waveform

	model.generate_batch = generate_batch_staged
	return model


def _get_audiosr(model_name: str, device: DeviceInfo, *, force_device: str | None = None):
	dev = force_device or ("cuda" if device.kind == "cuda" else "cpu")
	key = f"{model_name}:{dev}"
	if key in _models:
		return _models[key], dev

	from audiosr import build_model

	if dev == "cuda":
		try:
			model = _build_audiosr_cuda(model_name)
		except torch.cuda.OutOfMemoryError:
			_console().print(
				"[red]AudioSR CUDA OOM even with staging — "
				"free VRAM (close other GPU apps) and retry. "
				"Not falling back to CPU for full remasters.[/red]"
			)
			_cuda_cleanup()
			raise
	else:
		_console().print(
			"[yellow]AudioSR on CPU (explicit). Full remasters should use CUDA.[/yellow]"
		)
		model = build_model(model_name=model_name, device="cpu")
		model.device = "cpu"

	_models[key] = model
	return model, dev


def unload_audiosr() -> None:
	"""Drop cached models (e.g. when switching basic ↔ speech)."""
	_models.clear()
	_cuda_cleanup()


def _to_numpy_waveform(waveform) -> np.ndarray:
	if isinstance(waveform, torch.Tensor):
		waveform = waveform.detach().cpu().numpy()
	arr = np.asarray(waveform, dtype=np.float32)
	while arr.ndim > 1 and arr.shape[0] == 1:
		arr = arr[0]
	if arr.ndim > 1:
		arr = arr.reshape(-1)
	return arr.astype(np.float32)


def _preprocess_for_audiosr(
	audio: np.ndarray, rate: int, *, category: str = "sfx"
) -> np.ndarray:
	"""Pad (and optionally low-pass) so AudioSR mel frames align."""
	arr = np.asarray(audio, dtype=np.float32)
	if arr.ndim == 1:
		arr = arr[np.newaxis, :]
	# Music: skip heavy LPF — it + diffusion was adding a weird “background” haze.
	if category != "music":
		nyq = rate / 2.0
		cutoff = min(0.95 * nyq, 10000.0)
		if cutoff > 100.0 and nyq > cutoff:
			b, a = signal.butter(4, cutoff / nyq, btype="low")
			arr = signal.filtfilt(b, a, arr, axis=-1).astype(np.float32)
	n = arr.shape[-1]
	target = max(rate, ((n + 1023) // 1024) * 1024)
	if target - n < 512:
		target += 1024
	if target > n:
		arr = np.pad(arr, ((0, 0), (0, target - n)))
	return arr


# Max seconds per AudioSR chunk (keeps activation tensors small on 8GB).
CHUNK_SECONDS = 5.0
CHUNK_OVERLAP = 0.25
# Music: same chunk size as SFX (8GB decode headroom); longer OLA for less wash.
MUSIC_CHUNK_SECONDS = 5.0
MUSIC_CHUNK_OVERLAP = 0.5


def _run_super_resolution(
	model, path: str, *, guidance_scale: float, ddim_steps: int, seed: int,
	fallback: tuple[np.ndarray, int] | None = None,
):
	from audiosr import super_resolution

	_cuda_cleanup()
	try:
		return super_resolution(
			model,
			path,
			guidance_scale=guidance_scale,
			ddim_steps=ddim_steps,
			seed=seed,
		)
	except ValueError as e:
		# AudioSR's low-pass needs a cutoff below Nyquist; already full-band input (some music)
		# has none. Such audio needs no bandwidth extension: just resample to the target rate.
		if fallback is None or "critical frequencies" not in str(e):
			raise
		from math import gcd

		audio, rate = fallback
		g = gcd(int(rate), int(TARGET_RATE))
		print(f"AudioSR cutoff >= Nyquist; resampling chunk {rate}->{TARGET_RATE} instead", flush=True)
		mono = np.asarray(audio, dtype=np.float32).reshape(-1)
		return signal.resample_poly(mono, TARGET_RATE // g, rate // g).astype(np.float32)

	_cuda_cleanup()
	return super_resolution(
		model,
		path,
		guidance_scale=guidance_scale,
		ddim_steps=ddim_steps,
		seed=seed,
	)


def _extend_chunked(
	model,
	audio: np.ndarray,
	rate: int,
	*,
	tmp_path: Path,
	guidance_scale: float,
	ddim_steps: int,
	seed: int,
	category: str = "sfx",
) -> np.ndarray:
	"""Run AudioSR in short mono chunks with overlap-add (8GB-friendly)."""
	assert audio.ndim == 2 and audio.shape[0] == 1
	tmp_path.mkdir(parents=True, exist_ok=True)
	n = audio.shape[-1]
	chunk_s = MUSIC_CHUNK_SECONDS if category == "music" else CHUNK_SECONDS
	overlap_s = MUSIC_CHUNK_OVERLAP if category == "music" else CHUNK_OVERLAP
	chunk = int(chunk_s * rate)
	hop = int((chunk_s - overlap_s) * rate)
	if hop < 1:
		hop = chunk
	# Same seed every chunk for music (correlated); SFX can vary slightly.
	seed_fn = (lambda _i: seed) if category == "music" else (lambda i: seed + i)
	if n <= chunk + rate // 2:
		# Single shot
		ch_in = tmp_path / "mono.wav"
		save_wav(ch_in, audio, rate)
		waveform = _run_super_resolution(
			model,
			str(ch_in),
			guidance_scale=guidance_scale,
			ddim_steps=ddim_steps,
			seed=seed,
			fallback=(audio, rate),
		)
		return _to_numpy_waveform(waveform)

	outs: list[np.ndarray] = []
	starts: list[int] = []
	pos = 0
	idx = 0
	while pos < n:
		end = min(pos + chunk, n)
		starts.append(pos)
		seg = audio[:, pos:end]
		# Pad short tail to stable length
		if seg.shape[-1] < rate:
			seg = np.pad(seg, ((0, 0), (0, rate - seg.shape[-1])))
		ch_in = tmp_path / f"chunk{idx}.wav"
		save_wav(ch_in, seg, rate)
		waveform = _run_super_resolution(
			model,
			str(ch_in),
			guidance_scale=guidance_scale,
			ddim_steps=ddim_steps,
			seed=seed_fn(idx),
			fallback=(seg, rate),
		)
		outs.append(_to_numpy_waveform(waveform))
		if end >= n:
			break
		pos += hop
		idx += 1

	# Overlap-add at 48 kHz
	scale = TARGET_RATE / rate
	total_out = int(round(n * scale))
	acc = np.zeros(total_out, dtype=np.float32)
	wsum = np.zeros(total_out, dtype=np.float32)
	fade = int(overlap_s * TARGET_RATE)
	for start, out in zip(starts, outs):
		o0 = int(round(start * scale))
		seg = out
		# Trim to expected chunk length at 48k
		expect = int(round(min(chunk, n - start) * scale))
		if seg.shape[-1] > expect:
			seg = seg[:expect]
		elif seg.shape[-1] < expect:
			seg = np.pad(seg, (0, expect - seg.shape[-1]))
		w = np.ones_like(seg)
		if fade > 0 and seg.shape[-1] > 2 * fade:
			ramp = np.linspace(0, 1, fade, dtype=np.float32)
			w[:fade] = ramp
			w[-fade:] = ramp[::-1]
		o1 = min(o0 + seg.shape[-1], total_out)
		use = o1 - o0
		acc[o0:o1] += seg[:use] * w[:use]
		wsum[o0:o1] += w[:use]
	wsum = np.maximum(wsum, 1e-6)
	return acc / wsum


def extend_audiosr(
	src: Path,
	dest: Path,
	*,
	model_name: str,
	device: DeviceInfo,
	ddim_steps: int = 50,
	guidance_scale: float = 3.5,
	seed: int = 42,
	category: str = "sfx",
) -> ExtendResult:
	t0 = time.perf_counter()
	# Swap model if category changed (basic ↔ speech) to avoid holding both.
	active_keys = [k for k in _models if not k.startswith(f"{model_name}:")]
	if active_keys and device.kind == "cuda":
		unload_audiosr()

	model, used_dev = _get_audiosr(model_name, device)
	src_audio, src_rate = load_wav(src)
	orig_len = src_audio.shape[-1]
	prepared = _preprocess_for_audiosr(src_audio, src_rate, category=category)

	channel_outs: list[np.ndarray] = []
	with tempfile.TemporaryDirectory(prefix="hd_audio_sr_") as tmp:
		tmp_path = Path(tmp)
		for ch in range(prepared.shape[0]):
			ch_mono = prepared[ch : ch + 1]
			try:
				out = _extend_chunked(
					model,
					ch_mono,
					src_rate,
					tmp_path=tmp_path / f"ch{ch}",
					guidance_scale=guidance_scale,
					ddim_steps=ddim_steps,
					seed=seed,
					category=category,
				)
			except RuntimeError as exc:
				if "Sizes of tensors must match" in str(exc):
					_console().print(
						f"[yellow]AudioSR shape error; retrying with extra pad.[/yellow]"
					)
					padded = np.pad(ch_mono, ((0, 0), (0, 2048)))
					(tmp_path / f"ch{ch}").mkdir(parents=True, exist_ok=True)
					out = _extend_chunked(
						model,
						padded,
						src_rate,
						tmp_path=tmp_path / f"ch{ch}_pad",
						guidance_scale=guidance_scale,
						ddim_steps=ddim_steps,
						seed=seed,
						category=category,
					)
				elif "out of memory" in str(exc).lower():
					_cuda_cleanup()
					_console().print(
						"[red]CUDA OOM during AudioSR — unload other GPU apps "
						"and retry. CPU fallback disabled for remasters.[/red]"
					)
					raise
				else:
					raise

			expect = int(round(orig_len * TARGET_RATE / src_rate))
			if out.shape[-1] > expect:
				out = out[:expect]
			elif out.shape[-1] < expect:
				out = np.pad(out, (0, expect - out.shape[-1]))
			channel_outs.append(out)
			_cuda_cleanup()

	stacked = np.stack(channel_outs, axis=0)
	save_wav(dest, stacked, TARGET_RATE)
	_data, rate = sf.read(str(dest))
	return ExtendResult(
		path=dest,
		backend=f"audiosr:{model_name}@{used_dev}+staged",
		ms=(time.perf_counter() - t0) * 1000,
		out_rate=int(rate) if rate else TARGET_RATE,
	)


def audiosr_model_for_category(category: str) -> str:
	return "speech" if category == "speech" else "basic"
