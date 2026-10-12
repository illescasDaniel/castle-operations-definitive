from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from spandrel import ImageModelDescriptor, ModelLoader

from .device import DeviceInfo
from .models import ModelSpec, ensure_model


def _to_tensor(img: Image.Image, device: torch.device) -> torch.Tensor:
	arr = np.asarray(img).astype(np.float32) / 255.0
	if arr.ndim == 2:
		arr = np.stack([arr, arr, arr], axis=-1)
	tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
	return tensor.to(device)


def _from_tensor(tensor: torch.Tensor) -> Image.Image:
	tensor = tensor.detach().clamp(0.0, 1.0).squeeze(0).permute(1, 2, 0).cpu().numpy()
	arr = (tensor * 255.0 + 0.5).astype(np.uint8)
	if arr.shape[2] == 1:
		return Image.fromarray(arr[:, :, 0], mode="L")
	return Image.fromarray(arr, mode="RGB")


def load_model(spec: ModelSpec, tool_root: Path, device: DeviceInfo) -> ImageModelDescriptor:
	path = ensure_model(spec, tool_root)
	model = ModelLoader().load_from_file(path)
	if not isinstance(model, ImageModelDescriptor):
		raise SystemExit(f"Model {spec.id} is not an image upscaler ({type(model)})")
	model = model.to(torch.device(device.torch_device)).eval()
	return model


@torch.inference_mode()
def upscale_image(
	img: Image.Image,
	model: ImageModelDescriptor,
	device: DeviceInfo,
	*,
	target_scale: int = 2,
	tile: int = 0,
) -> tuple[Image.Image, float]:
	"""Upscale by target_scale (2 or 4). Cascades native-2× models for 4×. Returns (image, ms)."""
	if target_scale not in (2, 4):
		raise SystemExit(f"target_scale must be 2 or 4, got {target_scale}")

	has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
	if has_alpha:
		rgba = img.convert("RGBA")
		rgb = rgba.convert("RGB")
		alpha = rgba.getchannel("A")
	else:
		rgb = img.convert("RGB")
		alpha = None

	t0 = time.perf_counter()
	rgb_out = _run_rgb_to_scale(rgb, model, device, target_scale=target_scale, tile=tile)
	if alpha is not None:
		a_rgb = Image.merge("RGB", (alpha, alpha, alpha))
		a_up = _run_rgb_to_scale(
			a_rgb, model, device, target_scale=target_scale, tile=tile
		).getchannel("R")
		if a_up.size != rgb_out.size:
			a_up = a_up.resize(rgb_out.size, Image.Resampling.LANCZOS)
		out = rgb_out.convert("RGBA")
		out.putalpha(a_up)
	else:
		out = rgb_out
	if device.kind == "cuda":
		torch.cuda.synchronize()
	elapsed_ms = (time.perf_counter() - t0) * 1000.0
	return out, elapsed_ms


def _run_rgb_to_scale(
	rgb: Image.Image,
	model: ImageModelDescriptor,
	device: DeviceInfo,
	*,
	target_scale: int,
	tile: int,
) -> Image.Image:
	native = int(model.scale)
	current = rgb
	# Cascade: e.g. native 2 → run twice for 4×.
	achieved = 1
	while achieved < target_scale:
		step = min(native, target_scale // achieved)
		if step < native and native > target_scale // achieved:
			# Native scale overshoots remaining factor: run native then downscale.
			current = _infer_once(current, model, device, tile=tile)
			achieved *= native
			break
		current = _infer_once(current, model, device, tile=tile)
		achieved *= native

	wanted = (rgb.width * target_scale, rgb.height * target_scale)
	if current.size != wanted:
		current = current.resize(wanted, Image.Resampling.LANCZOS)
	return current


def _infer_once(
	rgb: Image.Image,
	model: ImageModelDescriptor,
	device: DeviceInfo,
	*,
	tile: int,
) -> Image.Image:
	dev = torch.device(device.torch_device)
	# Auto-tile large frames to stay within laptop VRAM (esp. 4× second pass).
	max_side = max(rgb.size)
	use_tile = tile
	if use_tile <= 0 and max_side >= 768:
		use_tile = 512
	tensor = _to_tensor(rgb, dev)
	if use_tile and max_side > use_tile:
		out_t = _tiled(tensor, model, tile=use_tile, overlap=16)
	else:
		out_t = model(tensor)
	return _from_tensor(out_t)


def _tiled(
	tensor: torch.Tensor,
	model: ImageModelDescriptor,
	*,
	tile: int,
	overlap: int,
) -> torch.Tensor:
	"""Simple reflective tile inference for large textures."""
	_, _, h, w = tensor.shape
	scale = int(model.scale)
	out = torch.zeros(
		(1, tensor.shape[1], h * scale, w * scale),
		device=tensor.device,
		dtype=tensor.dtype,
	)
	weights = torch.zeros_like(out)

	ys = list(range(0, h, max(tile - overlap, 1)))
	xs = list(range(0, w, max(tile - overlap, 1)))
	if not ys:
		ys = [0]
	if not xs:
		xs = [0]

	for y in ys:
		for x in xs:
			y1 = min(y + tile, h)
			x1 = min(x + tile, w)
			y0 = max(0, y1 - tile) if y1 - y < tile and y > 0 else y
			x0 = max(0, x1 - tile) if x1 - x < tile and x > 0 else x
			patch = tensor[:, :, y0:y1, x0:x1]
			pred = model(patch)
			oy0, ox0 = y0 * scale, x0 * scale
			oy1, ox1 = y1 * scale, x1 * scale
			out[:, :, oy0:oy1, ox0:ox1] += pred
			weights[:, :, oy0:oy1, ox0:ox1] += 1.0
	return out / weights.clamp_min(1.0)
