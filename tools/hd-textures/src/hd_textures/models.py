from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx
from rich.console import Console

console = Console(stderr=True)

# Default CLI scale; override with --scale 2|4.
DEFAULT_SCALE = 2


@dataclass(frozen=True)
class ModelSpec:
	id: str
	filename: str
	# Native network scale. For --scale 4, native-2 models are cascaded (2× then 2×).
	native_scale: int
	notes: str
	url: str | None = None


MODELS: dict[str, ModelSpec] = {
	"x2plus": ModelSpec(
		id="x2plus",
		filename="RealESRGAN_x2plus.pth",
		url="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
		native_scale=2,
		notes="Dedicated 2× Real-ESRGAN; solid general baseline",
	),
	"general-wdn": ModelSpec(
		id="general-wdn",
		filename="realesr-general-wdn-x4v3.pth",
		url="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-wdn-x4v3.pth",
		native_scale=4,
		notes="General WDN x4v3 @ 2× (4× then downscale); good on photo-like textures",
	),
	"animevideov3": ModelSpec(
		id="animevideov3",
		filename="realesr-animevideov3.pth",
		url="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth",
		native_scale=4,
		notes="Compact / faster; clean look on painted/game art",
	),
	"ultrasharp": ModelSpec(
		id="ultrasharp",
		filename="4x-UltraSharp.pth",
		url="https://huggingface.co/Kim2091/UltraSharp/resolve/main/4x-UltraSharp.pth",
		native_scale=4,
		notes="Popular game-texture sharpness (4× then downscale)",
	),
	"ani4k": ModelSpec(
		id="ani4k",
		filename="2x_Ani4K_Compact_35000.pth",
		url="https://github.com/Sirosky/Upscale-Hub/releases/download/Ani4K/2x_Ani4K_Compact_35000.pth",
		native_scale=2,
		notes="2x Ani4K Compact (Sirosky, Upscale-Hub); very fast CompactArch",
	),
}

DEFAULT_PILOT_MODELS = ("x2plus", "general-wdn", "animevideov3", "ultrasharp", "ani4k")


def cache_dir(root: Path) -> Path:
	d = root / ".cache" / "models"
	d.mkdir(parents=True, exist_ok=True)
	return d


def ensure_model(spec: ModelSpec, root: Path) -> Path:
	path = cache_dir(root) / spec.filename
	if path.is_file() and path.stat().st_size > 1_000_000:
		return path
	if not spec.url:
		raise SystemExit(f"Model {spec.id} has no download url")
	console.print(f"[cyan]Downloading {spec.id} → {path.name}[/cyan]")
	tmp = path.with_suffix(path.suffix + ".part")
	with httpx.stream("GET", spec.url, follow_redirects=True, timeout=120.0) as resp:
		resp.raise_for_status()
		with tmp.open("wb") as f:
			for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
				f.write(chunk)
	tmp.replace(path)
	return path


def parse_model_ids(raw: str | None) -> list[ModelSpec]:
	if not raw:
		ids = list(DEFAULT_PILOT_MODELS)
	else:
		ids = [p.strip() for p in raw.split(",") if p.strip()]
	out: list[ModelSpec] = []
	for mid in ids:
		if mid not in MODELS:
			known = ", ".join(MODELS)
			raise SystemExit(f"Unknown model {mid!r}. Known: {known}")
		out.append(MODELS[mid])
	return out
