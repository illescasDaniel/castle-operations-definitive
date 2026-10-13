from __future__ import annotations

from dataclasses import asdict, dataclass

import torch
from rich.console import Console

console = Console(stderr=True)


@dataclass(frozen=True)
class DeviceInfo:
	kind: str  # "cuda" | "cpu"
	torch_device: str  # "cuda:0" | "cpu"
	name: str
	vram_gb: float | None
	torch_version: str
	cuda_build: str | None

	def banner(self) -> str:
		if self.kind == "cuda":
			vram = f"{self.vram_gb:.1f} GB" if self.vram_gb is not None else "?"
			return (
				f"Device: CUDA — {self.name} ({vram}) | "
				f"torch {self.torch_version} | cuda {self.cuda_build}"
			)
		return (
			f"Device: CPU — {self.name} | torch {self.torch_version} | "
			f"cuda build {self.cuda_build or 'none'}"
		)

	def to_dict(self) -> dict:
		return asdict(self)


def resolve_device(*, allow_cpu: bool = False) -> DeviceInfo:
	cuda_ok = torch.cuda.is_available()
	if cuda_ok:
		idx = torch.cuda.current_device()
		props = torch.cuda.get_device_properties(idx)
		vram_gb = props.total_memory / (1024**3)
		info = DeviceInfo(
			kind="cuda",
			torch_device=f"cuda:{idx}",
			name=torch.cuda.get_device_name(idx),
			vram_gb=vram_gb,
			torch_version=torch.__version__,
			cuda_build=torch.version.cuda,
		)
		console.print(f"[bold green]{info.banner()}[/bold green]")
		return info

	info = DeviceInfo(
		kind="cpu",
		torch_device="cpu",
		name="cpu",
		vram_gb=None,
		torch_version=torch.__version__,
		cuda_build=torch.version.cuda,
	)
	if not allow_cpu:
		console.print(f"[bold red]{info.banner()}[/bold red]")
		console.print(
			"[red]CUDA is required for pilot/batch. "
			"Pass --allow-cpu to override (timings will not be comparable).[/red]"
		)
		raise SystemExit(2)
	console.print(f"[bold yellow]{info.banner()} (allowed via --allow-cpu)[/bold yellow]")
	return info
