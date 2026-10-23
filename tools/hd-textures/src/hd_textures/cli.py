from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image
from rich.console import Console
from rich.table import Table

from .compress import save_game_format, save_preview_png
from .device import resolve_device
from .extract import extract_all, extract_paths
from .inventory import is_font_path, list_images, summarize
from .models import DEFAULT_PILOT_MODELS, parse_model_ids
from .pack import merge_into_pk3, pack_directory
from .paths import resolve_data_dir, tool_root
from .upscale import PostProcess, load_model, upscale_image

console = Console()

DEFAULT_PILOT_TEXTURES = [
	"textures/chateau/wall_c01.jpg",
	"textures/chateau/wood_c06.jpg",
	"models/weapons2/luger/luger7.jpg",
	"models/players/Bj/bj_body1.jpg",
	"models/players/Bj/acc/bj_glass.tga",
]

JPEG_SWEEP = (80, 85, 90, 95)


def main(argv: list[str] | None = None) -> None:
	parser = argparse.ArgumentParser(
		prog="hd-textures",
		description="Local AI upscale for RTCW SP textures (owned Steam data).",
	)
	sub = parser.add_subparsers(dest="cmd", required=True)

	p_inv = sub.add_parser("inventory", help="List SP image counts from Steam paks")
	p_inv.add_argument("--data", default=None, help="Path to RTCW Main/ (or RTCW_DATA)")

	p_pilot = sub.add_parser("pilot", help="A/B upscale sample textures + metrics")
	p_pilot.add_argument("--data", default=None)
	p_pilot.add_argument("--out", type=Path, default=Path("samples/pilot"))
	p_pilot.add_argument(
		"--models",
		default=",".join(DEFAULT_PILOT_MODELS),
		help="Comma-separated model ids",
	)
	p_pilot.add_argument(
		"--textures",
		default=",".join(DEFAULT_PILOT_TEXTURES),
		help="Comma-separated virtual paths inside the paks",
	)
	p_pilot.add_argument("--jpeg-quality", type=int, default=90)
	p_pilot.add_argument(
		"--scale",
		type=int,
		choices=(2, 4),
		default=2,
		help="Output scale factor (4× cascades native-2× models)",
	)
	p_pilot.add_argument("--tile", type=int, default=0, help="Tile size (0=auto for large)")
	p_pilot.add_argument("--allow-cpu", action="store_true")
	p_pilot.add_argument(
		"--no-jpeg-sweep",
		action="store_true",
		help="Skip JPEG quality sweep on the first opaque sample",
	)

	p_batch = sub.add_parser("batch", help="Upscale full SP image set with one model")
	p_batch.add_argument("--data", default=None)
	p_batch.add_argument("--model", required=True)
	p_batch.add_argument("--out", type=Path, default=Path("samples/full"))
	p_batch.add_argument("--jpeg-quality", type=int, default=90)
	p_batch.add_argument(
		"--scale",
		type=int,
		choices=(2, 4),
		default=2,
		help="Output scale factor (4× cascades native-2× models like ani4k)",
	)
	p_batch.add_argument(
		"--font-model",
		default=None,
		help="Optional model id for fonts/ and menu/art/font* (e.g. ultrasharp)",
	)
	p_batch.add_argument(
		"--font-scale",
		type=int,
		choices=(2, 4),
		default=None,
		help="Scale for font images (default: 4 if --font-model set, else --scale)",
	)
	p_batch.add_argument(
		"--only-fonts",
		action="store_true",
		help="Process only font atlases / menu prop fonts",
	)
	p_batch.add_argument(
		"--blend",
		type=float,
		default=0.85,
		help="World textures: weight of the AI result vs a bicubic upscale (1.0 = pure AI; default 0.85 = anti-halo)",
	)
	p_batch.add_argument(
		"--ring-clamp",
		type=float,
		default=0.02,
		metavar="MARGIN",
		help="World textures: limit output to the local min/max of the bicubic upscale +- MARGIN "
		"(0..1 levels, default 0.02); removes dark halos / pale fringes",
	)
	p_batch.add_argument(
		"--no-ring-clamp", action="store_true", help="Disable the ring clamp (old pure-AI look with --blend 1)"
	)
	p_batch.add_argument(
		"--ring-radius", type=int, default=1, help="Ring clamp window radius in output pixels"
	)
	p_batch.add_argument(
		"--downsample",
		choices=("lanczos", "box", "bicubic"),
		default="box",
		help="World textures: filter for 4x network output -> 2x (default box: no ringing; lanczos was the old one)",
	)
	p_batch.add_argument("--tile", type=int, default=0, help="Tile size (0=auto for large)")
	p_batch.add_argument("--allow-cpu", action="store_true")
	p_batch.add_argument("--limit", type=int, default=0, help="Debug: only first N images")

	p_pack = sub.add_parser("pack", help="Zip upscaled tree into codmod_hd.pk3")
	p_pack.add_argument("--from", dest="src", type=Path, required=True)
	p_pack.add_argument(
		"--pk3",
		type=Path,
		default=Path("../../run/codmod/codmod_hd.pk3"),
	)
	p_pack.add_argument(
		"--merge",
		action="store_true",
		help="Replace/add images in an existing pk3; keep other members",
	)

	args = parser.parse_args(argv)
	if args.cmd == "inventory":
		cmd_inventory(args)
	elif args.cmd == "pilot":
		cmd_pilot(args)
	elif args.cmd == "batch":
		cmd_batch(args)
	elif args.cmd == "pack":
		cmd_pack(args)


def cmd_inventory(args: argparse.Namespace) -> None:
	data = resolve_data_dir(args.data)
	images = list_images(data)
	stats = summarize(images)
	console.print(f"Data: {data}")
	console.print(f"Unique images (later pak wins): {stats['total']}")
	for k, v in sorted(stats.items()):
		if k == "total":
			continue
		console.print(f"  {k}: {v}")


def cmd_pilot(args: argparse.Namespace) -> None:
	root = tool_root()
	data = resolve_data_dir(args.data)
	out: Path = args.out
	if not out.is_absolute():
		out = (Path.cwd() / out).resolve()
	device = resolve_device(allow_cpu=args.allow_cpu)
	models = parse_model_ids(args.models)
	textures = [t.strip() for t in args.textures.split(",") if t.strip()]

	src_dir = out / "source"
	extract_paths(data, textures, src_dir)

	rows: list[dict] = []
	for spec in models:
		console.print(f"\n[bold]Model {spec.id}[/bold] — {spec.notes}")
		model = load_model(spec, root, device)
		for vpath in textures:
			src_path = src_dir / vpath
			img = Image.open(src_path)
			src_bytes = src_path.stat().st_size
			up, up_ms = upscale_image(
				img, model, device, target_scale=args.scale, tile=args.tile
			)

			preview = out / "preview" / spec.id / (Path(vpath).stem + ".png")
			save_preview_png(up, preview)

			game_dest = out / "game" / spec.id / vpath
			out_bytes, enc_ms = save_game_format(
				up,
				game_dest,
				source_suffix=Path(vpath).suffix,
				jpeg_quality=args.jpeg_quality,
			)
			row = {
				"device": device.torch_device,
				"device_name": device.name,
				"model": spec.id,
				"scale": args.scale,
				"path": vpath,
				"in_px": f"{img.width}x{img.height}",
				"out_px": f"{up.width}x{up.height}",
				"upscale_ms": round(up_ms, 2),
				"encode_ms": round(enc_ms, 2),
				"src_bytes": src_bytes,
				"out_bytes": out_bytes,
				"ratio": round(out_bytes / src_bytes, 3) if src_bytes else None,
				"jpeg_quality": args.jpeg_quality,
				"preview": str(preview),
				"game_file": str(game_dest),
			}
			rows.append(row)
			console.print(
				f"  {vpath}: {row['in_px']} → {row['out_px']} | "
				f"upscale {row['upscale_ms']:.0f} ms | "
				f"out {out_bytes / 1024:.1f} KiB ({row['ratio']}×)"
			)

	if not args.no_jpeg_sweep:
		opaque = next((t for t in textures if t.lower().endswith((".jpg", ".jpeg"))), None)
		if opaque and models:
			console.print(f"\n[bold]JPEG quality sweep[/bold] on {opaque}")
			spec = models[0]
			model = load_model(spec, root, device)
			img = Image.open(src_dir / opaque)
			up, _ = upscale_image(
				img, model, device, target_scale=args.scale, tile=args.tile
			)
			for q in JPEG_SWEEP:
				dest = out / "jpeg_sweep" / spec.id / f"q{q}_{Path(opaque).name}"
				nbytes, enc_ms = save_game_format(
					up, dest, source_suffix=".jpg", jpeg_quality=q
				)
				rows.append(
					{
						"device": device.torch_device,
						"device_name": device.name,
						"model": spec.id,
						"path": opaque,
						"kind": "jpeg_sweep",
						"jpeg_quality": q,
						"out_bytes": nbytes,
						"encode_ms": round(enc_ms, 2),
						"game_file": str(dest),
					}
				)
				console.print(f"  q={q}: {nbytes / 1024:.1f} KiB | encode {enc_ms:.1f} ms")

	report = {
		"device": device.to_dict(),
		"rows": rows,
	}
	report_path = out / "report.json"
	report_path.write_text(json.dumps(report, indent=2) + "\n")
	_print_summary_table(rows)
	console.print(f"\nReport: {report_path}")
	console.print(f"Previews: {out / 'preview'}")
	console.print(f"[green]{device.banner()}[/green]")


def cmd_batch(args: argparse.Namespace) -> None:
	root = tool_root()
	data = resolve_data_dir(args.data)
	out: Path = args.out
	if not out.is_absolute():
		out = (Path.cwd() / out).resolve()
	device = resolve_device(allow_cpu=args.allow_cpu)
	specs = parse_model_ids(args.model)
	if len(specs) != 1:
		raise SystemExit("batch takes exactly one --model id")
	spec = specs[0]

	font_spec = None
	if args.font_model:
		font_specs = parse_model_ids(args.font_model)
		if len(font_specs) != 1:
			raise SystemExit("batch takes exactly one --font-model id")
		font_spec = font_specs[0]
	font_scale = args.font_scale
	if font_spec is not None and font_scale is None:
		font_scale = 4
	elif font_scale is None:
		font_scale = args.scale

	images = list_images(data)
	if args.only_fonts:
		images = [im for im in images if is_font_path(im.path)]
		if not images:
			raise SystemExit("No font images found in SP paks")
		if font_spec is None:
			raise SystemExit("--only-fonts requires --font-model")
	if args.limit > 0:
		images = images[: args.limit]

	src_dir = out / "_source"
	console.print(f"Extracting {len(images)} images…")
	extract_all(data, src_dir, images)

	need_main = any(not is_font_path(im.path) for im in images) or font_spec is None
	need_font = font_spec is not None and any(is_font_path(im.path) for im in images)

	model = load_model(spec, root, device) if need_main else None
	font_model = load_model(font_spec, root, device) if need_font and font_spec else None

	banner = f"[bold]Batch {spec.id} @ {args.scale}×[/bold]"
	if font_spec is not None:
		banner += f" [bold]fonts→{font_spec.id} @ {font_scale}×[/bold]"
	console.print(f"{banner} on {device.banner()}")

	post = PostProcess(
		blend=args.blend,
		clamp=None if args.no_ring_clamp else args.ring_clamp,
		radius=args.ring_radius,
		downsample=args.downsample,
	)
	rows: list[dict] = []
	game_root = out / "game"
	for i, img_meta in enumerate(images, 1):
		src_path = src_dir / img_meta.path
		img = Image.open(src_path)
		use_font = font_model is not None and is_font_path(img_meta.path)
		active_model = font_model if use_font else model
		active_scale = font_scale if use_font else args.scale
		active_id = font_spec.id if use_font and font_spec else spec.id
		assert active_model is not None
		up, up_ms = upscale_image(
			img,
			active_model,
			device,
			target_scale=active_scale,
			tile=args.tile,
			post=None if use_font else post,
		)
		dest = game_root / img_meta.path
		out_bytes, enc_ms = save_game_format(
			up,
			dest,
			source_suffix=Path(img_meta.path).suffix,
			jpeg_quality=args.jpeg_quality,
		)
		rows.append(
			{
				"device": device.torch_device,
				"model": active_id,
				"scale": active_scale,
				"font": use_font,
				"path": img_meta.path,
				"in_px": f"{img.width}x{img.height}",
				"out_px": f"{up.width}x{up.height}",
				"upscale_ms": round(up_ms, 2),
				"encode_ms": round(enc_ms, 2),
				"out_bytes": out_bytes,
			}
		)
		if i % 25 == 0 or i == len(images):
			console.print(
				f"  [{i}/{len(images)}] {img_meta.path} "
				f"{img.width}x{img.height}→{up.width}x{up.height} "
				f"({active_id} {active_scale}×, {up_ms:.0f} ms)"
			)

	report_path = out / "report.json"
	report_path.write_text(
		json.dumps(
			{
				"device": device.to_dict(),
				"model": spec.id,
				"scale": args.scale,
				"font_model": font_spec.id if font_spec else None,
				"font_scale": font_scale if font_spec else None,
				"only_fonts": bool(args.only_fonts),
				"rows": rows,
			},
			indent=2,
		)
		+ "\n"
	)
	console.print(f"Done. Game files: {game_root}")
	console.print(f"Report: {report_path}")
	console.print(f"[green]{device.banner()}[/green]")


def cmd_pack(args: argparse.Namespace) -> None:
	src = args.src
	if not src.is_absolute():
		src = (Path.cwd() / src).resolve()
	# Convenience layouts:
	#   batch → <out>/game/{textures,models,...}
	#   pilot → <out>/game/<model_id>/{textures,models,...}
	#   fonts-only → <out>/game/{fonts,menu,...}
	if (src / "game").is_dir():
		game = src / "game"
		if (
			(game / "textures").is_dir()
			or (game / "models").is_dir()
			or (game / "fonts").is_dir()
			or (game / "menu").is_dir()
		):
			src = game
		else:
			model_dirs = sorted(p for p in game.iterdir() if p.is_dir())
			if len(model_dirs) == 1:
				src = model_dirs[0]
			elif len(model_dirs) > 1:
				raise SystemExit(
					"Pass --from to a single model tree, e.g. "
					+ str(model_dirs[0])
				)
			else:
				src = game
	pk3: Path = args.pk3
	if not pk3.is_absolute():
		pk3 = (Path.cwd() / pk3).resolve()
	if args.merge:
		replaced, kept = merge_into_pk3(src, pk3)
		console.print(
			f"Merged {replaced} file(s) into {pk3} "
			f"(kept {kept} other; {pk3.stat().st_size / (1024 * 1024):.1f} MiB)"
		)
	else:
		n = pack_directory(src, pk3)
		console.print(
			f"Packed {n} files → {pk3} ({pk3.stat().st_size / (1024 * 1024):.1f} MiB)"
		)
	console.print("[yellow]Do not commit or redistribute this pk3 (proprietary source art).[/yellow]")


def _print_summary_table(rows: list[dict]) -> None:
	table = Table(title="Pilot upscale timings")
	table.add_column("model")
	table.add_column("path")
	table.add_column("px")
	table.add_column("upscale ms", justify="right")
	table.add_column("out KiB", justify="right")
	table.add_column("ratio", justify="right")
	for r in rows:
		if r.get("kind") == "jpeg_sweep":
			continue
		table.add_row(
			r["model"],
			r["path"].split("/")[-1],
			f"{r['in_px']}→{r['out_px']}",
			f"{r['upscale_ms']:.0f}",
			f"{r['out_bytes'] / 1024:.1f}",
			f"{r['ratio']}",
		)
	console.print(table)


if __name__ == "__main__":
	main()
