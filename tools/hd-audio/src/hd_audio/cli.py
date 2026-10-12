from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .device import resolve_device
from .extract import extract_all, extract_paths
from .inventory import list_audio, summarize
from .pack import merge_into_pk3, pack_directory
from .music import CURRENT_MUSIC_MODE, MUSIC_MODES
from .paths import CURRENT_RECIPE, resolve_data_dir
from .pipeline import RECIPES, remaster_file
from .wavio import load_wav, save_wav, truncate_seconds

console = Console()

DEFAULT_PILOT_CLIPS = [
	"sound/weapons/luger/lugerf1.wav",
	"sound/weapons/luger/luger_reload.wav",
	"sound/weapons/mp40/mp40f1.wav",
	"sound/weapons/thompson/thompson.wav",
	"sound/weapons/rocket/rocklf1a.wav",
	"sound/movers/doors/door2_open.wav",
	"sound/world/debris_hit.wav",
	"sound/player/footsteps/step1.wav",
	"sound/player/land1.wav",
	"sound/player/bj2/pain25_1.wav",
	"sound/music/l_theme.wav",
	"sound/scenaric/escape1/axis2_hey_hans.wav",
	"sound/scenaric/escape1/axis1_american_is_loose.wav",
	"sound/scenaric/escape1/axis13_yes1_relax.wav",
]

MUSIC_PILOT_SECONDS = 8.0


def main(argv: list[str] | None = None) -> None:
	parser = argparse.ArgumentParser(
		prog="hd-audio",
		description="Local AI remaster for RTCW SP audio (owned Steam data).",
	)
	sub = parser.add_subparsers(dest="cmd", required=True)

	p_inv = sub.add_parser("inventory", help="List SP audio counts from Steam paks")
	p_inv.add_argument("--data", default=None)

	p_pilot = sub.add_parser("pilot", help="A/B remaster sample clips + report.json")
	p_pilot.add_argument("--data", default=None)
	p_pilot.add_argument("--out", type=Path, default=Path("samples/pilot"))
	p_pilot.add_argument(
		"--recipes",
		default=CURRENT_RECIPE,
		help="Comma-separated recipes (locked default: sr_only)",
	)
	p_pilot.add_argument(
		"--clips",
		default=",".join(DEFAULT_PILOT_CLIPS),
		help="Comma-separated virtual paths",
	)
	p_pilot.add_argument("--ddim-steps", type=int, default=50)
	p_pilot.add_argument("--guidance-scale", type=float, default=3.5)
	p_pilot.add_argument("--seed", type=int, default=42)
	p_pilot.add_argument("--allow-cpu", action="store_true")
	p_pilot.add_argument(
		"--music-seconds",
		type=float,
		default=MUSIC_PILOT_SECONDS,
		help="Truncate music clips for faster A/B (0 = full)",
	)
	p_pilot.add_argument(
		"--resume",
		action="store_true",
		help="Skip clips that already have a remaster WAV under --out",
	)

	p_batch = sub.add_parser("batch", help="Remaster full SP audio set with one recipe")
	p_batch.add_argument("--data", default=None)
	p_batch.add_argument(
		"--recipe",
		default=CURRENT_RECIPE,
		choices=sorted(RECIPES),
		help=f"Default locked recipe: {CURRENT_RECIPE}",
	)
	p_batch.add_argument("--out", type=Path, default=Path("samples/full"))
	p_batch.add_argument("--ddim-steps", type=int, default=50)
	p_batch.add_argument("--guidance-scale", type=float, default=3.5)
	p_batch.add_argument("--seed", type=int, default=42)
	p_batch.add_argument("--allow-cpu", action="store_true")
	p_batch.add_argument("--limit", type=int, default=0, help="Debug: only first N files")
	p_batch.add_argument(
		"--category",
		default=None,
		choices=("sfx", "speech", "music"),
		help="Optional: only process one category",
	)
	p_batch.add_argument(
		"--music-mode",
		default=CURRENT_MUSIC_MODE,
		choices=list(MUSIC_MODES),
		help=f"Music path (default: {CURRENT_MUSIC_MODE})",
	)
	p_batch.add_argument(
		"--resume",
		action="store_true",
		help="Skip files that already have a remaster WAV under --out/game",
	)

	p_music = sub.add_parser(
		"pilot-music",
		help="A/B music-only remaster modes (resample / sr_mid / sr_linked)",
	)
	p_music.add_argument("--data", default=None)
	p_music.add_argument("--out", type=Path, default=Path("samples/pilot-music"))
	p_music.add_argument(
		"--modes",
		default=",".join(MUSIC_MODES),
		help="Comma-separated music modes",
	)
	p_music.add_argument(
		"--clips",
		default="sound/music/l_theme.wav,sound/music/m_stealth.wav",
		help="Music virtual paths",
	)
	p_music.add_argument("--music-seconds", type=float, default=12.0)
	p_music.add_argument("--ddim-steps", type=int, default=60)
	p_music.add_argument("--guidance-scale", type=float, default=2.0)
	p_music.add_argument("--seed", type=int, default=42)
	p_music.add_argument("--allow-cpu", action="store_true")

	p_pack = sub.add_parser("pack", help="Zip remastered tree into codmod_hd_audio.pk3")
	p_pack.add_argument("--from", dest="src", type=Path, required=True)
	p_pack.add_argument(
		"--pk3",
		type=Path,
		default=Path("../../run/codmod/codmod_hd_audio.pk3"),
	)
	p_pack.add_argument(
		"--merge",
		action="store_true",
		help="Replace/add audio in an existing pk3; keep other members",
	)

	args = parser.parse_args(argv)
	if args.cmd == "inventory":
		cmd_inventory(args)
	elif args.cmd == "pilot":
		cmd_pilot(args)
	elif args.cmd == "pilot-music":
		cmd_pilot_music(args)
	elif args.cmd == "batch":
		cmd_batch(args)
	elif args.cmd == "pack":
		cmd_pack(args)


def cmd_inventory(args: argparse.Namespace) -> None:
	data = resolve_data_dir(args.data)
	entries = list_audio(data)
	stats = summarize(entries)
	console.print(f"Data: {data}")
	console.print(f"Unique audio (later pak wins): {stats['total']}")
	for k, v in sorted(stats.items()):
		if k == "total":
			continue
		console.print(f"  {k}: {v}")


def _abs_out(out: Path) -> Path:
	if out.is_absolute():
		return out
	return (Path.cwd() / out).resolve()


def cmd_pilot(args: argparse.Namespace) -> None:
	data = resolve_data_dir(args.data)
	out = _abs_out(args.out)
	device = resolve_device(allow_cpu=args.allow_cpu)
	recipes = [r.strip() for r in args.recipes.split(",") if r.strip()]
	for r in recipes:
		if r not in RECIPES:
			raise SystemExit(f"Unknown recipe {r!r}; choose from {sorted(RECIPES)}")
	clips = [c.strip() for c in args.clips.split(",") if c.strip()]

	src_dir = out / "_source"
	extract_paths(data, clips, src_dir)

	# Write listening originals (music truncated).
	orig_root = out / "original"
	for vpath in clips:
		src = src_dir / vpath
		dest = orig_root / vpath
		audio, rate = load_wav(src)
		if args.music_seconds > 0 and "sound/music/" in vpath.lower():
			audio = truncate_seconds(audio, rate, args.music_seconds)
		save_wav(dest, audio, rate)

	rows: list[dict] = []
	for recipe in recipes:
		console.print(f"\n[bold]Recipe {recipe}[/bold]")
		for vpath in clips:
			src = src_dir / vpath
			dest = out / "remaster" / recipe / vpath
			max_sec = None
			if args.music_seconds > 0 and "sound/music/" in vpath.lower():
				max_sec = args.music_seconds
			if args.resume and dest.is_file() and dest.stat().st_size > 44:
				console.print(f"  [dim]skip[/dim] {vpath} ({recipe})")
				rows.append(
					{
						"path": vpath,
						"recipe": recipe,
						"skipped": True,
						"out_file": str(dest),
						"device": device.torch_device,
						"device_name": device.name,
					}
				)
				continue
			try:
				with tempfile.TemporaryDirectory(prefix="hd_audio_pilot_") as tmp:
					stats = remaster_file(
						src,
						dest,
						recipe=recipe,
						device=device,
						work_dir=Path(tmp),
						virtual_path=vpath,
						ddim_steps=args.ddim_steps,
						guidance_scale=args.guidance_scale,
						seed=args.seed,
						max_seconds=max_sec,
					)
			except Exception as exc:
				console.print(f"[red]  FAIL {vpath}: {exc}[/red]")
				rows.append(
					{
						"path": vpath,
						"recipe": recipe,
						"error": str(exc),
						"device": device.torch_device,
						"device_name": device.name,
					}
				)
				continue
			row = stats.to_dict()
			row["path"] = vpath
			row["device"] = device.torch_device
			row["device_name"] = device.name
			row["out_file"] = str(dest)
			rows.append(row)
			console.print(
				f"  {vpath}: {stats.category} | "
				f"{stats.src_rate}→{stats.out_rate} Hz | "
				f"{stats.total_ms / 1000:.1f}s | "
				f"{stats.enhance_backend} → {stats.extend_backend}"
			)

	report = {
		"device": device.to_dict(),
		"current_recipe": CURRENT_RECIPE,
		"recipes": recipes,
		"clips": clips,
		"rows": rows,
		"listen": {
			"original": str(orig_root),
			"remaster": str(out / "remaster"),
		},
	}
	report_path = out / "report.json"
	report_path.write_text(json.dumps(report, indent=2) + "\n")
	_print_summary(rows)
	console.print(f"\nReport: {report_path}")
	console.print(f"Originals: {orig_root}")
	console.print(f"Remasters: {out / 'remaster'}")
	console.print(
		"[yellow]Do not commit or redistribute samples/ — proprietary derivatives.[/yellow]"
	)
	console.print(f"[green]{device.banner()}[/green]")


def cmd_pilot_music(args: argparse.Namespace) -> None:
	"""Compare music remaster modes against the original."""
	data = resolve_data_dir(args.data)
	out = _abs_out(args.out)
	device = resolve_device(allow_cpu=args.allow_cpu)
	modes = [m.strip() for m in args.modes.split(",") if m.strip()]
	for m in modes:
		if m not in MUSIC_MODES:
			raise SystemExit(f"Unknown music mode {m!r}; choose from {MUSIC_MODES}")
	clips = [c.strip() for c in args.clips.split(",") if c.strip()]

	src_dir = out / "_source"
	extract_paths(data, clips, src_dir)

	orig_root = out / "original"
	for vpath in clips:
		audio, rate = load_wav(src_dir / vpath)
		if args.music_seconds > 0:
			audio = truncate_seconds(audio, rate, args.music_seconds)
		save_wav(orig_root / vpath, audio, rate)

	rows: list[dict] = []
	for mode in modes:
		console.print(f"\n[bold]Music mode {mode}[/bold]")
		for vpath in clips:
			src = src_dir / vpath
			dest = out / "remaster" / mode / vpath
			max_sec = args.music_seconds if args.music_seconds > 0 else None
			try:
				with tempfile.TemporaryDirectory(prefix="hd_audio_music_") as tmp:
					stats = remaster_file(
						src,
						dest,
						recipe="sr_only",
						device=device,
						work_dir=Path(tmp),
						virtual_path=vpath,
						ddim_steps=args.ddim_steps,
						guidance_scale=args.guidance_scale,
						seed=args.seed,
						max_seconds=max_sec,
						music_mode=mode,
					)
			except Exception as exc:
				console.print(f"[red]  FAIL {vpath}: {exc}[/red]")
				rows.append({"path": vpath, "mode": mode, "error": str(exc)})
				continue
			row = stats.to_dict()
			row["music_mode"] = mode
			row["out_file"] = str(dest)
			rows.append(row)
			console.print(
				f"  {vpath}: {stats.extend_backend} | {stats.total_ms / 1000:.1f}s"
			)

	report_path = out / "report.json"
	report_path.write_text(
		json.dumps(
			{
				"device": device.to_dict(),
				"modes": modes,
				"clips": clips,
				"rows": rows,
				"listen": {
					"original": str(orig_root),
					"remaster": str(out / "remaster"),
				},
			},
			indent=2,
		)
		+ "\n"
	)
	console.print(f"\nReport: {report_path}")
	console.print(f"Originals: {orig_root}")
	console.print(f"Modes: {out / 'remaster'}/{{resample,sr_mid,sr_linked}}/")
	console.print(
		"[yellow]Do not commit or redistribute samples/ — proprietary derivatives.[/yellow]"
	)


def cmd_batch(args: argparse.Namespace) -> None:
	data = resolve_data_dir(args.data)
	out = _abs_out(args.out)
	device = resolve_device(allow_cpu=args.allow_cpu)
	entries = list_audio(data)
	if args.category:
		entries = [e for e in entries if e.category == args.category]
	if args.limit > 0:
		entries = entries[: args.limit]

	src_dir = out / "_source"
	console.print(f"Extracting {len(entries)} audio files…")
	extract_all(data, src_dir, entries)

	game_root = out / "game"
	rows: list[dict] = []
	console.print(
		f"[bold]Batch recipe={args.recipe} music={args.music_mode}[/bold] "
		f"on {device.banner()}"
	)
	skipped = 0
	for i, meta in enumerate(entries, 1):
		src = src_dir / meta.path
		dest = game_root / meta.path
		if args.resume and dest.is_file() and dest.stat().st_size > 44:
			skipped += 1
			rows.append(
				{
					"path": meta.path,
					"skipped": True,
					"out_file": str(dest),
				}
			)
			if i % 50 == 0 or i == len(entries):
				console.print(f"  [{i}/{len(entries)}] skip {meta.path}")
			continue
		try:
			with tempfile.TemporaryDirectory(prefix="hd_audio_batch_") as tmp:
				stats = remaster_file(
					src,
					dest,
					recipe=args.recipe,
					device=device,
					work_dir=Path(tmp),
					virtual_path=meta.path,
					ddim_steps=args.ddim_steps,
					guidance_scale=args.guidance_scale,
					music_mode=args.music_mode,
					seed=args.seed,
				)
		except Exception as e:  # keep a long batch alive: fall back to a plain resample
			from .music import hq_resample
			from .paths import TARGET_RATE

			console.print(f"[yellow]  FALLBACK resample {meta.path}: {type(e).__name__}: {e}[/yellow]")
			audio, rate = load_wav(src)
			dest.parent.mkdir(parents=True, exist_ok=True)
			save_wav(dest, hq_resample(audio, rate, TARGET_RATE) if rate != TARGET_RATE else audio, TARGET_RATE)
			rows.append({"path": meta.path, "fallback": f"{type(e).__name__}: {e}", "out_file": str(dest)})
			continue
		row = stats.to_dict()
		row["path"] = meta.path
		rows.append(row)
		if i % 10 == 0 or i == len(entries):
			console.print(f"  [{i}/{len(entries)}] {meta.path} ({stats.total_ms / 1000:.1f}s)")

	report_path = out / "report.json"
	report_path.write_text(
		json.dumps(
			{
				"device": device.to_dict(),
				"recipe": args.recipe,
				"music_mode": args.music_mode,
				"count": len(rows),
				"skipped": skipped,
				"rows": rows,
			},
			indent=2,
		)
		+ "\n"
	)
	console.print(f"Game tree: {game_root}")
	console.print(f"Report: {report_path} (skipped {skipped})")
	console.print(
		"[yellow]Pack next: uv run hd-audio pack --from "
		f"{game_root} --pk3 ../../run/codmod/codmod_hd_audio.pk3[/yellow]"
	)
	console.print(
		"[yellow]Do not commit or redistribute the pk3 — proprietary derivatives.[/yellow]"
	)


def cmd_pack(args: argparse.Namespace) -> None:
	src = args.src
	if not src.is_absolute():
		src = (Path.cwd() / src).resolve()
	# Accept samples/full or samples/full/game
	if (src / "game" / "sound").is_dir():
		src = src / "game"
	elif (src / "sound").is_dir():
		pass
	else:
		# remaster/<recipe>/sound layout from pilot
		pass

	pk3 = args.pk3
	if not pk3.is_absolute():
		pk3 = (Path.cwd() / pk3).resolve()

	if args.merge:
		n, kept = merge_into_pk3(src, pk3)
		console.print(f"Merged {n} audio file(s); kept {kept} other member(s) → {pk3}")
	else:
		n = pack_directory(src, pk3)
		console.print(f"Packed {n} audio file(s) → {pk3}")
	console.print(
		"[yellow]Do not commit or redistribute codmod_hd_audio.pk3 — "
		"proprietary asset derivatives.[/yellow]"
	)


def _print_summary(rows: list[dict]) -> None:
	table = Table(title="Pilot summary")
	table.add_column("recipe")
	table.add_column("path")
	table.add_column("cat")
	table.add_column("Hz")
	table.add_column("sec", justify="right")
	for r in rows:
		if r.get("error"):
			table.add_row(r.get("recipe", "?"), r["path"].split("/")[-1], "ERR", "-", "-")
			continue
		table.add_row(
			r["recipe"],
			r["path"].split("/")[-1],
			r["category"],
			f"{r['src_rate']}→{r['out_rate']}",
			f"{r['total_ms'] / 1000:.1f}",
		)
	console.print(table)


if __name__ == "__main__":
	main()
