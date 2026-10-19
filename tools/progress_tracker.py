#!/usr/bin/env python3
"""
K8sQuest Progress Tracker
Displays completion status of every level found under worlds/
"""

import json
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

# World discovery lives in the engine; import it rather than keep a second world list
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "engine"))

from world_discovery import discover_worlds, total_levels, total_xp

console = Console()

def load_progress():
    """Load progress from progress.json (the file the engine writes)"""
    progress_file = BASE_DIR / "progress.json"
    if progress_file.exists():
        with open(progress_file, encoding='utf-8') as f:
            return json.load(f)
    return {"completed_levels": [], "total_xp": 0}

def main():
    console.clear()

    worlds = discover_worlds(BASE_DIR)
    progress = load_progress()
    completed_levels = set(progress.get("completed_levels", []))
    player_xp = progress.get("total_xp", 0)
    available_total = total_levels(worlds)
    max_xp = total_xp(worlds)

    # Header
    console.print(Panel.fit(
        "[bold cyan]🎮 K8sQuest - Progress Tracker[/bold cyan]\n"
        f"[yellow]Total XP:[/yellow] {player_xp:,} / {max_xp:,}\n"
        f"[yellow]Levels Completed:[/yellow] {len(completed_levels)} / {available_total}",
        border_style="cyan"
    ))

    console.print()

    # World-by-world breakdown
    for world in worlds:
        available_count = len(world.levels)

        # Count completed levels in this world
        completed_in_world = sum(
            1 for level in world.levels if level.name in completed_levels
        )

        # Status icon
        if available_count == 0:
            status = "⏳"
            status_text = "Coming Soon"
            color = "yellow"
        elif completed_in_world == available_count:
            status = "✅"
            status_text = "Complete"
            color = "green"
        else:
            status = "🚧"
            status_text = "In Progress"
            color = "cyan"

        # World header
        console.print(f"\n{status} [{color}]{world.display_name}[/{color}]")
        console.print(f"   Cluster: {world.cluster} | XP: {world.total_xp:,}")

        # Progress bar
        if available_count > 0:
            progress_pct = (completed_in_world / available_count) * 100
            console.print(f"   Levels: {available_count} | Completed: {completed_in_world}/{available_count}")

            # Visual progress bar
            bar_length = 40
            filled = int((completed_in_world / available_count) * bar_length)
            bar = "█" * filled + "░" * (bar_length - filled)
            console.print(f"   [{color}]{bar}[/{color}] {progress_pct:.0f}%")
        else:
            console.print(f"   Status: {status_text}")

    console.print()

    # Overall progress
    overall_pct = (len(completed_levels) / available_total) * 100 if available_total > 0 else 0

    console.print(Panel.fit(
        f"[bold]Overall Progress:[/bold] {len(completed_levels)}/{available_total} levels ({overall_pct:.1f}%)",
        title="Summary",
        border_style="green"
    ))

if __name__ == "__main__":
    main()
