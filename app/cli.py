"""
AgenticVision Studio - Rich Terminal CLI
Demonstrates autonomous multi-agent vision capabilities directly from the command line.
"""
import sys
import argparse
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from app.agents.orchestrator import VisionOrchestrator
from app.services.market_intel import MarketIntelligenceService

console = Console()

def run_cli():
    parser = argparse.ArgumentParser(description="AgenticVision Studio CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Pipeline command
    conv_p = subparsers.add_parser("convert", help="Execute Autonomous Multi-Agent Pipeline on an image")
    conv_p.add_argument("image", help="Path to input image")
    conv_p.add_argument("--intent", default="auto", choices=["auto", "web_speed", "e_commerce", "print_ready", "lossless_archive", "ultra_compact_mobile"])
    conv_p.add_argument("--format", default=None, help="Force specific format: WEBP, PNG, JPEG, AVIF, SVG, TIFF")
    conv_p.add_argument("--quality", type=int, default=None, help="Compression quality (1-100)")
    conv_p.add_argument("--upscale", type=int, default=1, choices=[1, 2, 4], help="AI super-resolution upscale factor")
    conv_p.add_argument("--remove-bg", action="store_true", help="Simulate AI background isolation")
    conv_p.add_argument("--sharpen", action="store_true", help="Apply perceptual unsharp masking")

    # Market Intel command
    subparsers.add_parser("market-intel", help="Display 2026 Top 7 AI Image Converters Benchmark Table")

    args = parser.parse_args()

    if args.command == "convert":
        img_path = Path(args.image)
        if not img_path.exists():
            console.print(f"[bold red]Error:[/bold red] File {args.image} not found!")
            sys.exit(1)

        console.print(Panel.fit(
            f"[bold cyan]AgenticVision Studio[/bold cyan] - Autonomous Multi-Agent Pipeline\n"
            f"Input: [yellow]{img_path.name}[/yellow] | Intent: [magenta]{args.intent}[/magenta]",
            border_style="cyan"
        ))

        orchestrator = VisionOrchestrator()
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True
        ) as progress:
            task = progress.add_task("[green]Agent Pipeline executing...", total=None)
            result = orchestrator.run_pipeline(
                image_path=str(img_path),
                user_intent=args.intent,
                override_format=args.format,
                override_quality=args.quality,
                upscale=args.upscale,
                remove_bg=args.remove_bg,
                sharpen=args.sharpen
            )

        # Print Chain of Thought
        cot_panel = "\n".join([f"[dim]{step}[/dim]" for step in result.strategy.chain_of_thought])
        console.print(Panel(cot_panel, title="[bold yellow]Agent Chain-of-Thought (CoT)[/bold yellow]", border_style="yellow"))

        # Print Metrics Table
        table = Table(title="[bold green]Execution & Quality Evaluation Metrics[/bold green]")
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="magenta")

        table.add_row("Output Format", result.transformation.output_format)
        table.add_row("Dimensions", f"{result.transformation.width} x {result.transformation.height}")
        table.add_row("Original Size", f"{result.audit.original_size_kb} KB")
        table.add_row("Output Size", f"{result.audit.output_size_kb} KB")
        table.add_row("Payload Savings", f"{result.audit.savings_percent}% ({result.audit.bytes_saved} bytes)")
        table.add_row("PSNR (Fidelity)", f"{result.audit.psnr_db} dB")
        table.add_row("SSIM (Structural)", f"{result.audit.ssim}")
        table.add_row("Perceptual Score", f"{result.audit.perceptual_score} / 100")
        table.add_row("Est. 3G Speedup", f"{result.audit.lcp_speedup_slow_3g_ms} ms")
        table.add_row("Est. 4G Speedup", f"{result.audit.lcp_speedup_fast_4g_ms} ms")
        table.add_row("Critic Verdict", result.audit.critic_verdict)

        console.print(table)
        console.print(f"[bold green]Saved Output to:[/bold green] {result.transformation.output_path}")

    elif args.command == "market-intel":
        tools = MarketIntelligenceService.get_all_tools()
        table = Table(title="[bold cyan]2026 Top 7 AI Image Converters - Competitive Benchmark[/bold cyan]")
        table.add_column("Rank", style="dim", width=4)
        table.add_column("Tool", style="bold green")
        table.add_column("Category", style="cyan")
        table.add_column("Formats", style="white")
        table.add_column("AI Capabilities", style="yellow")
        table.add_column("Cost / Tier", style="magenta")

        for t in tools:
            table.add_row(
                str(t.rank),
                t.name,
                t.category,
                t.supported_formats_count,
                ", ".join(t.ai_features[:2]),
                t.cost_tier
            )
        console.print(table)
    else:
        parser.print_help()

if __name__ == "__main__":
    run_cli()
