"""Terminal interface for the multi-agent vision pipeline.

Three subcommands:

    convert    run the full pipeline on one image and show the agents' reasoning
    benchmark  measure the pipeline across a directory and emit a CSV
    market     print the converter comparison table

``benchmark`` exists so the numbers in the README are reproducible: anyone can
re-run it on their own images and check the claims rather than take them on
trust.
"""

from __future__ import annotations

import argparse
import base64
import csv
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from app.agents.orchestrator import PipelineExecution, VisionOrchestrator
from app.core.config import settings
from app.services.market_intel import MarketIntelligenceService

console = Console()

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}
INTENTS = [
    "auto",
    "web_speed",
    "e_commerce",
    "print_ready",
    "lossless_archive",
    "ultra_compact_mobile",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-vision",
        description="Multi-agent image optimisation: measure, plan, encode, audit.",
    )
    subparsers = parser.add_subparsers(dest="command")

    convert = subparsers.add_parser("convert", help="Run the full pipeline on one image")
    convert.add_argument("image", help="Path to the input image")
    convert.add_argument("--intent", default="auto", choices=INTENTS)
    convert.add_argument("--format", default=None, help="Force a format (WEBP, PNG, JPEG, AVIF, TIFF, SVG)")
    convert.add_argument("--quality", type=int, default=None, help="Force encoder quality (10-100)")
    convert.add_argument("--upscale", type=int, default=1, choices=[1, 2, 4], help="Lanczos resample factor")
    convert.add_argument("--max-kb", type=float, default=None, help="Hard output size budget in KB")
    convert.add_argument("--remove-bg", action="store_true", help="Matte out a flat background")
    convert.add_argument("--sharpen", action="store_true", help="Apply an unsharp mask")
    convert.add_argument("--out", default=None, help="Output directory (default: ./outputs)")

    bench = subparsers.add_parser("benchmark", help="Measure the pipeline across a directory of images")
    bench.add_argument("directory", help="Directory of source images")
    bench.add_argument("--intent", default="web_speed", choices=INTENTS)
    bench.add_argument("--csv", default="benchmark_results.csv", help="Where to write the results CSV")

    subparsers.add_parser("market", help="Print the image-converter comparison table")
    return parser


def _encoded_bytes(execution: PipelineExecution, image_path: Path) -> bytes:
    """Recover the encoded image for writing to disk.

    ``run_pipeline`` returns metadata plus an optional inline data URI rather
    than raw bytes, so decode the URI we asked for instead of repeating a
    possibly multi-pass encode.
    """
    if execution.output_data_uri:
        return base64.b64decode(execution.output_data_uri.split(",", 1)[1])

    from app.agents.transformer import ImageTransformAgent

    return ImageTransformAgent().transform(
        image_path.read_bytes(),
        target_format=execution.transformation.output_format,
        quality=execution.transformation.quality_used or 85,
        stem=image_path.stem,
    ).data


def cmd_convert(args: argparse.Namespace) -> int:
    image_path = Path(args.image)
    if not image_path.exists():
        console.print(f"[bold red]Error:[/bold red] {args.image} not found")
        return 1

    console.print(
        Panel.fit(
            f"[bold cyan]{settings.APP_NAME}[/bold cyan]\n"
            f"Input: [yellow]{image_path.name}[/yellow]   Objective: [magenta]{args.intent}[/magenta]",
            border_style="cyan",
        )
    )

    orchestrator = VisionOrchestrator()
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as progress:
        progress.add_task("[green]Running the agent pipeline...", total=None)
        execution = orchestrator.run_pipeline(
            image_path.read_bytes(),
            filename=image_path.name,
            user_intent=args.intent,
            override_format=args.format,
            override_quality=args.quality,
            upscale=args.upscale,
            remove_bg=args.remove_bg,
            sharpen=args.sharpen,
            target_size_kb=args.max_kb,
            include_data_uri=True,
        )

    console.print(
        Panel(
            "\n".join(f"[dim]{step}[/dim]" for step in execution.strategy.chain_of_thought),
            title="[bold yellow]Reasoning agent: why these settings[/bold yellow]",
            border_style="yellow",
        )
    )

    audit = execution.audit
    table = Table(title="[bold green]Result[/bold green]", show_header=True)
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")
    table.add_row("Output format", execution.transformation.output_format)
    table.add_row("Dimensions", f"{execution.transformation.width} x {execution.transformation.height}")
    table.add_row("Size", f"{audit.original_size_kb} KB -> {audit.output_size_kb} KB")
    table.add_row("Payload change", f"{audit.savings_percent}% ({audit.bytes_saved:,} bytes)")
    table.add_row("SSIM", f"{audit.ssim}  (floor {execution.strategy.ssim_floor})")
    table.add_row("PSNR", f"{audit.psnr_db} dB")
    table.add_row("Perceptual score", f"{audit.perceptual_score} / 100")
    table.add_row("Transfer saved (Slow 3G)", f"{audit.lcp_speedup_slow_3g_ms} ms")
    table.add_row("Transfer saved (4G)", f"{audit.lcp_speedup_fast_4g_ms} ms")
    table.add_row("Encoder passes", str(execution.transformation.encode_attempts))
    table.add_row("Critic retries", str(execution.quality_retries))
    table.add_row("Verdict", audit.critic_verdict)
    console.print(table)

    output_dir = Path(args.out) if args.out else settings.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / execution.transformation.output_filename
    destination.write_bytes(_encoded_bytes(execution, image_path))
    console.print(f"[bold green]Saved:[/bold green] {destination}")

    if not execution.met_quality_floor:
        console.print(
            "[yellow]Note:[/yellow] the result sits below this profile's fidelity floor. "
            "Raise --quality or relax --max-kb."
        )
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    directory = Path(args.directory)
    if not directory.is_dir():
        console.print(f"[bold red]Error:[/bold red] {args.directory} is not a directory")
        return 1

    images = sorted(p for p in directory.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    if not images:
        console.print(f"[bold red]Error:[/bold red] no images found in {args.directory}")
        return 1

    orchestrator = VisionOrchestrator()
    rows: list[dict] = []

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), transient=True) as progress:
        task = progress.add_task(f"Benchmarking {len(images)} images...", total=None)
        for image in images:
            progress.update(task, description=f"Processing {image.name}...")
            execution = orchestrator.run_pipeline(
                image.read_bytes(), filename=image.name, user_intent=args.intent
            )
            rows.append(
                {
                    "image": image.name,
                    "format": execution.transformation.output_format,
                    "intent": args.intent,
                    "original_kb": execution.audit.original_size_kb,
                    "output_kb": execution.audit.output_size_kb,
                    "savings_pct": execution.audit.savings_percent,
                    "ssim": execution.audit.ssim,
                    "psnr_db": execution.audit.psnr_db,
                    "retries": execution.quality_retries,
                    "encode_ms": execution.transformation.execution_time_ms,
                }
            )

    table = Table(title=f"[bold cyan]Benchmark: {args.intent}[/bold cyan]")
    for column in ("Image", "Fmt", "Original", "Output", "Saved", "SSIM", "PSNR"):
        table.add_column(column)
    for row in rows:
        table.add_row(
            row["image"][:28],
            row["format"],
            f"{row['original_kb']:.0f} KB",
            f"{row['output_kb']:.0f} KB",
            f"{row['savings_pct']:.1f}%",
            f"{row['ssim']:.4f}",
            f"{row['psnr_db']:.1f} dB",
        )
    console.print(table)

    savings = sorted(r["savings_pct"] for r in rows)
    ssims = sorted(r["ssim"] for r in rows)
    console.print(
        f"\n[bold]Median saving:[/bold] {savings[len(savings) // 2]:.1f}%   "
        f"[bold]Median SSIM:[/bold] {ssims[len(ssims) // 2]:.4f}   "
        f"[bold]n =[/bold] {len(rows)}"
    )

    csv_path = Path(args.csv)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    console.print(f"[bold green]Wrote:[/bold green] {csv_path}")
    return 0


def cmd_market() -> int:
    table = Table(title="[bold cyan]Online image converters compared[/bold cyan]")
    table.add_column("#", style="dim", width=3)
    table.add_column("Tool", style="bold green")
    table.add_column("Category", style="cyan")
    table.add_column("Formats", style="white")
    table.add_column("Notable features", style="yellow")
    table.add_column("Cost", style="magenta")
    for tool in MarketIntelligenceService.get_all_tools():
        table.add_row(
            str(tool.rank),
            tool.name,
            tool.category,
            tool.supported_formats_count,
            ", ".join(tool.ai_features[:2]),
            tool.cost_tier,
        )
    console.print(table)
    return 0


def run_cli(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "convert":
        return cmd_convert(args)
    if args.command == "benchmark":
        return cmd_benchmark(args)
    if args.command == "market":
        return cmd_market()
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(run_cli())
