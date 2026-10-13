from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import httpx
import numpy as np
import torch
from rich.console import Console
from spandrel import ImageModelDescriptor, ModelLoader

from .device import resolve_device

console = Console(stderr=True)

DEFAULT_RTCW_DATA = (
	Path.home() / ".local/share/Steam/steamapps/common/Return to Castle Wolfenstein/Main"
)
SP_PAKS = ("pak0.pk3", "sp_pak1.pk3", "sp_pak2.pk3", "sp_pak3.pk3", "sp_pak4.pk3")

# key -> (filename, url, native scale)
MODELS = {
	"span": (
		"2xLiveActionV1_SPAN_490000.pth",
		"https://huggingface.co/poor7/Other/resolve/02606599eb74781065604c22921f08bef8745b17/"
		"2xLiveActionV1_SPAN_490000.pth",
		2,
	),
	"nomos": ("2xNomosUni_compact_multijpg.pth", None, 2),
	"clearreality": ("4x-ClearRealityV1.pth", None, 4),
	"ultrasharpv2": (
		"4x-UltraSharpV2.safetensors",
		"https://huggingface.co/Kim2091/UltraSharpV2/resolve/main/4x-UltraSharpV2.safetensors",
		4,
	),
}


def _nlm(strength: float) -> str:
	return f"nlmeans=s={strength}:p=5:r=9"


# name -> (ffmpeg -vf prefilter or None, model chain); chained models run one after another (span,span = 4x)
VARIANTS: dict[str, tuple[str | None, tuple[str, ...]]] = {
	"span": (None, ("span",)),
	"span2": (None, ("span", "span")),
	"deblock+span": ("deblock=filter=strong:block=8:alpha=0.25:beta=0.2:gamma=0.2:delta=0.2", ("span",)),
	"nlm+span": (_nlm(3), ("span",)),
	"nomos": (None, ("nomos",)),
	"nlm+nomos": (_nlm(3), ("nomos",)),
	"deblock+nlm+nomos": (
		"deblock=filter=strong:block=8:alpha=0.25:beta=0.2:gamma=0.2:delta=0.2," + _nlm(3), ("nomos",)),
	"clearreality": (None, ("clearreality",)),
	"ultrasharpv2": (None, ("ultrasharpv2",)),
}
for _s in (1, 1.5, 2, 2.5):
	VARIANTS[f"nlm{_s:g}+span"] = (_nlm(_s), ("span",))
	VARIANTS[f"nlm{_s:g}+span2"] = (_nlm(_s), ("span", "span"))


def tool_root() -> Path:
	return Path(__file__).resolve().parents[2]


def data_dir(explicit: str | None) -> Path:
	raw = explicit or os.environ.get("RTCW_DATA") or str(DEFAULT_RTCW_DATA)
	path = Path(raw).expanduser().resolve()
	if not path.is_dir():
		raise SystemExit(f"RTCW data directory not found: {path}")
	return path


def ensure_model(key: str) -> Path:
	fname, url, _ = MODELS[key]
	cache = tool_root() / ".cache" / "models"
	cache.mkdir(parents=True, exist_ok=True)
	path = cache / fname
	if path.is_file() and path.stat().st_size > 1_000_000:
		return path
	local = Path.home() / "Models" / fname
	if local.is_file():
		shutil.copy2(local, path)
		return path
	if url is None:
		raise SystemExit(f"{fname} not found in {cache} or ~/Models")
	console.print(f"[cyan]Downloading {fname}[/cyan]")
	tmp = path.with_suffix(".part")
	with httpx.stream("GET", url, follow_redirects=True, timeout=300.0) as resp:
		resp.raise_for_status()
		with tmp.open("wb") as f:
			for chunk in resp.iter_bytes(1 << 20):
				f.write(chunk)
	tmp.replace(path)
	return path


def roq_members(data: Path, patterns: list[str]) -> dict[str, tuple[Path, str]]:
	"""video/*.roq in the SP paks matching any pattern (basename glob). Later paks win."""
	out: dict[str, tuple[Path, str]] = {}
	for pak in SP_PAKS:
		p = data / pak
		if not p.is_file():
			continue
		with zipfile.ZipFile(p) as zf:
			for name in zf.namelist():
				low = name.lower().replace("\\", "/")
				if not (low.startswith("video/") and low.endswith(".roq")):
					continue
				base = Path(low).stem
				if any(fnmatch.fnmatch(base, pat.lower()) for pat in patterns):
					out[base] = (p, name)
	return out


def extract(data: Path, patterns: list[str]) -> dict[str, Path]:
	dest = tool_root() / ".cache" / "roq"
	dest.mkdir(parents=True, exist_ok=True)
	out: dict[str, Path] = {}
	for base, (pak, name) in roq_members(data, patterns).items():
		target = dest / f"{base}.roq"
		if not target.is_file():
			with zipfile.ZipFile(pak) as zf, zf.open(name) as src, target.open("wb") as dst:
				shutil.copyfileobj(src, dst)
		out[base] = target
		console.print(f"{base}: {target} ({target.stat().st_size / 1e6:.1f} MB)")
	if not out:
		raise SystemExit(f"No video/*.roq matching {patterns}")
	return out


def probe(path: Path) -> tuple[int, int, float, bool]:
	r = subprocess.run(
		["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate",
		 "-of", "csv=p=0", str(path)],
		capture_output=True, text=True, check=True,
	)
	w = h = 0
	fps = 24.0
	audio = False
	for line in r.stdout.splitlines():
		parts = line.split(",")
		if parts[0] == "video":
			w, h = int(parts[1]), int(parts[2])
			n, d = parts[3].split("/")
			fps = float(n) / float(d)
		elif parts[0] == "audio":
			audio = True
	return w, h, fps, audio


def load_model(key: str, dev: torch.device, fp16: bool = True) -> ImageModelDescriptor:
	model = ModelLoader().load_from_file(ensure_model(key))
	if not isinstance(model, ImageModelDescriptor):
		raise SystemExit("Model is not an image upscaler")
	model = model.to(dev).eval()
	if fp16 and model.supports_half:
		return model.half()
	if fp16 and model.supports_bfloat16:
		return model.bfloat16()
	return model


def chain_scale(keys: tuple[str, ...]) -> int:
	n = 1
	for k in keys:
		n *= MODELS[k][2]
	return n


@torch.inference_mode()
def upscale_frame(
	models: list[ImageModelDescriptor], dev: torch.device, rgb: np.ndarray, keys: tuple[str, ...],
	out_scale: int, grain: float = 0.0,
) -> np.ndarray:
	h, w, _ = rgb.shape
	t = torch.from_numpy(rgb).to(dev).permute(2, 0, 1).unsqueeze(0).float() / 255.0
	for model in models:
		t = model(t.to(next(model.model.parameters()).dtype)).float().clamp(0, 1)
	if chain_scale(keys) != out_scale:
		t = torch.nn.functional.interpolate(
			t, size=(h * out_scale, w * out_scale), mode="bicubic", antialias=True
		).clamp(0, 1)
	if grain > 0:
		# fresh luma noise every frame (dynamic grain), slightly softened to look film-like, strongest in midtones
		n = torch.randn(1, 1, t.shape[2], t.shape[3], device=t.device)
		n = torch.nn.functional.avg_pool2d(n, 3, 1, 1) * 2.0
		luma = t.mean(1, keepdim=True)
		t = (t + n * (grain / 255.0) * (0.35 + 1.3 * luma * (1 - luma) * 2)).clamp(0, 1)
	out = t.mul(255).add(0.5).byte().squeeze(0).permute(1, 2, 0)
	return out.cpu().numpy()


def process(
	models, keys, out_scale, dev, src: Path, dst: Path, *, quality: int, ss: float, dur: float | None,
	prefilter: str | None, stills: Path | None, grain: float = 0.0,
) -> None:
	w, h, fps, has_audio = probe(src)
	ow, oh = w * out_scale, h * out_scale
	# RoQ has no usable seek index: cut on the output side (decode and discard).
	t_args = ["-ss", str(ss)] if ss else []
	if dur:
		t_args += ["-t", str(dur)]
	af = []
	if ss or dur:
		af = ["-af", f"atrim=start={ss}" + (f":duration={dur}" if dur else "") + ",asetpts=PTS-STARTPTS"]
	vf = [prefilter] if prefilter else []
	dec = subprocess.Popen(
		["ffmpeg", "-v", "error", "-i", str(src), "-an", *t_args,
		 *(["-vf", ",".join(vf)] if vf else []),
		 "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
		stdout=subprocess.PIPE,
	)
	enc_cmd = [
		"ffmpeg", "-v", "error", "-y",
		"-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ow}x{oh}", "-r", f"{fps:g}", "-i", "-",
	]
	if has_audio:
		enc_cmd += ["-i", str(src)]
	enc_cmd += ["-map", "0:v"]
	if has_audio:
		enc_cmd += ["-map", "1:a", *af, "-c:a", "pcm_s16le", "-shortest"]
	enc_cmd += ["-c:v", "mjpeg", "-q:v", str(quality), "-pix_fmt", "yuvj420p", str(dst)]
	dst.parent.mkdir(parents=True, exist_ok=True)
	enc = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE)
	size = w * h * 3
	n = 0
	t0 = time.time()
	while True:
		buf = dec.stdout.read(size)
		if len(buf) < size:
			break
		frame = np.frombuffer(buf, np.uint8).reshape(h, w, 3)
		up = upscale_frame(models, dev, frame.copy(), keys, out_scale, grain)
		enc.stdin.write(up.tobytes())
		if stills is not None and n % 48 == 0:
			from PIL import Image  # noqa: PLC0415

			stills.mkdir(parents=True, exist_ok=True)
			Image.fromarray(up).save(stills / f"{dst.stem}_{n:05d}_ai.png")
			Image.fromarray(frame).resize((ow, oh), Image.LANCZOS).save(
				stills / f"{dst.stem}_{n:05d}_lanczos.png"
			)
		n += 1
		if n % 100 == 0:
			console.print(f"{dst.stem}: {n} frames, {n / (time.time() - t0):.1f} fps")
	enc.stdin.close()
	enc.wait()
	dec.wait()
	secs = n / fps
	mb = dst.stat().st_size / 1e6
	console.print(
		f"[green]{dst.name}: {n} frames ({secs:.1f}s) {ow}x{oh}, {mb:.1f} MB "
		f"({mb / max(secs, 1e-9):.2f} MB/s) in {time.time() - t0:.0f}s[/green]"
	)


def cmd_run(args: argparse.Namespace, *, pilot: bool) -> None:
	info = resolve_device(allow_cpu=args.allow_cpu)
	console.print(info.banner())
	dev = torch.device(info.torch_device)
	roqs = extract(data_dir(args.data), args.only)
	vf, keys = VARIANTS[args.variant]
	models = [load_model(k, dev, fp16=not args.fp32) for k in keys]
	scale = args.scale or chain_scale(keys)
	out = tool_root() / "samples" / ("pilot" if pilot else "full") / args.variant / "video"
	for base, roq in roqs.items():
		process(
			models, keys, scale, dev, roq, out / f"{base}.avi", quality=args.quality,
			ss=args.ss if pilot else 0, dur=args.seconds if pilot else None,
			prefilter=vf, grain=args.grain, stills=(out.parent / "stills") if pilot else None,
		)


def decode_clip(roq: Path, w: int, h: int, vf: str | None, ss: float, dur: float) -> np.ndarray:
	cmd = ["ffmpeg", "-v", "error", "-i", str(roq), "-an", "-ss", str(ss), "-t", str(dur)]
	if vf:
		cmd += ["-vf", vf]
	raw = subprocess.run([*cmd, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
	return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)


def cmd_compare(args: argparse.Namespace) -> None:
	from PIL import Image, ImageDraw  # noqa: PLC0415

	info = resolve_device(allow_cpu=args.allow_cpu)
	dev = torch.device(info.torch_device)
	scale = args.scale or 2  # compare panels share one size
	loaded: dict[str, ImageModelDescriptor] = {}
	out = tool_root() / "samples" / "compare"
	out.mkdir(parents=True, exist_ok=True)
	crop = [int(v) for v in args.crop.split(",")] if args.crop else None  # x,y,w,h in source px
	for base, roq in extract(data_dir(args.data), args.only).items():
		w, h, fps, _ = probe(roq)
		labels = ["original (lanczos)"]
		cols: list[np.ndarray] = []
		for name in args.variants:
			vf, keys = VARIANTS[name]
			for k in keys:
				if k not in loaded:
					loaded[k] = load_model(k, dev, fp16=not args.fp32)
			vscale = scale or chain_scale(keys)
			t0 = time.time()
			frames = decode_clip(roq, w, h, vf, args.ss, args.seconds)
			if not cols:
				cols.append(np.stack([
					np.asarray(Image.fromarray(f).resize((w * scale, h * scale), Image.LANCZOS))
					for f in decode_clip(roq, w, h, None, args.ss, args.seconds)]))
			cols.append(np.stack([upscale_frame([loaded[k] for k in keys], dev, f.copy(), keys, scale, args.grain) for f in frames]))
			labels.append(name)
			console.print(f"{name}: {len(frames)} frames in {time.time() - t0:.0f}s")
		n = min(len(c) for c in cols)
		ow, oh = w * scale, h * scale
		ncols = 2
		rows = (len(cols) + ncols - 1) // ncols
		zoom = 1
		if crop:
			cx, cy, cw, ch = (v * scale for v in crop)
			zoom = 2
			pw, ph = cw * zoom, ch * zoom
		else:
			cx = cy = 0
			cw, ch, pw, ph = ow, oh, ow, oh
		mp4 = out / f"{base}.mp4"
		enc = subprocess.Popen(
			["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
			 "-s", f"{pw * ncols}x{ph * rows}", "-r", f"{fps:g}", "-i", "-",
			 "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p", str(mp4)], stdin=subprocess.PIPE)
		for i in range(n):
			sheet = Image.new("RGB", (pw * ncols, ph * rows))
			draw = ImageDraw.Draw(sheet)
			for j, c in enumerate(cols):
				tile = Image.fromarray(c[i][cy:cy + ch, cx:cx + cw])
				if zoom > 1:
					tile = tile.resize((pw, ph), Image.NEAREST)
				x, y = (j % ncols) * pw, (j // ncols) * ph
				sheet.paste(tile, (x, y))
				draw.rectangle((x, y, x + 8 * len(labels[j]) + 8, y + 14), fill=(0, 0, 0))
				draw.text((x + 4, y + 2), labels[j], fill=(255, 255, 0))
			enc.stdin.write(sheet.tobytes())
			if i % max(1, int(fps * 2)) == 0:
				sheet.save(out / f"{base}_{i:04d}.png")
		enc.stdin.close()
		enc.wait()
		console.print(f"[green]{mp4} ({n} frames)[/green]")


def cmd_pack(args: argparse.Namespace) -> None:
	src = tool_root() / "samples" / "full" / args.variant / "video"
	avis = sorted(src.glob("*.avi"))
	if not avis:
		raise SystemExit(f"No AVIs in {src}; run `hd-video batch` first")
	pk3 = Path(args.pk3).resolve()
	pk3.parent.mkdir(parents=True, exist_ok=True)
	with zipfile.ZipFile(pk3, "w", compression=zipfile.ZIP_STORED) as zf:
		for avi in avis:
			zf.write(avi, arcname=f"video/{avi.name}")
	console.print(f"[green]{pk3}: {len(avis)} videos[/green] (private, never commit)")


def main() -> None:
	ap = argparse.ArgumentParser(prog="hd-video")
	sub = ap.add_subparsers(dest="cmd", required=True)

	def common(p: argparse.ArgumentParser) -> None:
		p.add_argument("--data", help="RTCW Main/ dir (or RTCW_DATA)")
		p.add_argument("--only", nargs="+", default=["wolfintro", "menu", "menu2"],
			help="video basenames/globs (default: SP videos)")
		p.add_argument("--quality", type=int, default=3, help="mjpeg -q:v (2 best .. 31 worst)")
		p.add_argument("--variant", choices=list(VARIANTS), default="span", help="prefilter + model chain (pilot/batch)")
		p.add_argument("--scale", type=int, choices=(2, 4), help="output scale (default: the chain's native scale)")
		p.add_argument("--grain", type=float, default=0.0, help="dynamic film grain sigma in 8-bit levels (0 = off, ~2-4 typical)")
		p.add_argument("--fp32", action="store_true", help="disable half precision")
		p.add_argument("--allow-cpu", action="store_true")

	p = sub.add_parser("pilot", help="short clip + stills for A/B and size budget")
	common(p)
	p.add_argument("--ss", type=float, default=30.0, help="start second")
	p.add_argument("--seconds", type=float, default=8.0)
	p = sub.add_parser("batch", help="full upscale of the selected videos")
	common(p)
	p = sub.add_parser("compare", help="side-by-side clip + stills of several models")
	common(p)
	p.add_argument("--variants", nargs="+", default=["span", "deblock+span", "nlm+span", "nomos", "nlm+nomos",
		"clearreality"], choices=list(VARIANTS))
	p.add_argument("--ss", type=float, default=30.0)
	p.add_argument("--seconds", type=float, default=4.0)
	p.add_argument("--crop", help="x,y,w,h in source pixels; zoomed 2x nearest")
	p = sub.add_parser("pack", help="pack samples/full/<variant>/video/*.avi into a pk3")
	p.add_argument("--variant", choices=list(VARIANTS), default="span")
	p.add_argument("--pk3", default=str(tool_root().parents[1] / "run/codmod/codmod_hd_video.pk3"))

	args = ap.parse_args()
	if args.cmd == "pilot":
		cmd_run(args, pilot=True)
	elif args.cmd == "compare":
		cmd_compare(args)
	elif args.cmd == "batch":
		cmd_run(args, pilot=False)
	else:
		cmd_pack(args)


if __name__ == "__main__":
	sys.exit(main())
