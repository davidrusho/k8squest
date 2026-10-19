import re
def validate_level_name(level_name):
    """Validate level name format to prevent path traversal and invalid input"""
    if not re.match(r'^[a-zA-Z0-9_-]+$', level_name):
        raise ValueError(f"Invalid level name: {level_name}")

def run_kubectl_with_timeout(args, timeout=30):
    """Run kubectl command with a timeout (default 30s)"""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result
    except subprocess.TimeoutExpired:
        console.print("[red]Error: Command timed out[/red]")
        return None
#!/usr/bin/env python3
"""
K8sQuest Reset Tool - Clean level state
"""

import sys
import subprocess
from pathlib import Path
from rich.console import Console
from rich.prompt import Confirm

sys.path.insert(0, str(Path(__file__).parent))
from level_reset import deploy_level, ensure_world_cluster, world_cluster

console = Console()

def reset_level_any_world(level):
    """Reset a specific level to initial state, searching all worlds"""
    try:
        validate_level_name(level)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        return False
    base_dir = Path(__file__).parent.parent
    worlds_dir = base_dir / "worlds"
    found = False
    for world_dir in worlds_dir.iterdir():
        if not world_dir.is_dir():
            continue
        level_path = world_dir / level
        if level_path.exists():
            found = True
            break
    if not found:
        console.print(f"[red]Error: Level not found in any world: {level}[/red]")
        return False
    if not (level_path / "broken.yaml").exists() and not (level_path / "setup.sh").exists():
        console.print(f"[red]Error: No broken.yaml or setup.sh found in {level}[/red]")
        return False
    console.print(f"[yellow]Resetting {world_dir.name}/{level}...[/yellow]\n")
    # switch kubectl to the level's world cluster first, so the namespace delete below hits it
    ok, why = ensure_world_cluster(world_cluster(level_path), base_dir, say=lambda m: console.print(f"[cyan]{m}[/cyan]"))
    if not ok:
        console.print(f"[red]Error: {why}[/red]")
        return False
    # Delete namespace (clean slate)
    console.print("Deleting namespace...")
    result_del = run_kubectl_with_timeout(["kubectl", "delete", "namespace", "k8squest", "--ignore-not-found"], timeout=180)
    if result_del is None:
        return False
    # Redeploy exactly as the engine does: namespace, delete all, leftovers,
    # then setup.sh if the level has one, otherwise broken.yaml
    console.print("Deploying broken resources...")
    ok, message = deploy_level(level_path)
    if ok:
        console.print("\n[green]✅ Level reset successfully![/green]")
        console.print(f"[dim]You can now retry: {level}[/dim]\n")
        return True
    console.print(f"\n[red]❌ Reset failed: {message}[/red]\n")
    return False

def reset_all():
    """Reset entire game state"""
    console.print("[yellow]This will reset ALL levels and clear your progress![/yellow]")
    
    if not Confirm.ask("Are you sure?", default=False):
        console.print("[dim]Cancelled[/dim]")
        return
    
    # Delete namespace
    console.print("\n[yellow]Cleaning up...[/yellow]")
    subprocess.run(
        ["kubectl", "delete", "namespace", "k8squest", "--ignore-not-found"],
        capture_output=True
    )
    
    # Remove progress file
    base_dir = Path(__file__).parent.parent
    progress_file = base_dir / "progress.json"
    if progress_file.exists():
        progress_file.unlink()
    
    console.print("[green]✅ Game reset complete![/green]\n")

def main():
    if len(sys.argv) < 2:
        console.print("[bold]K8sQuest Reset Tool[/bold]\n")
        console.print("Usage:")
        console.print("  python3 engine/reset.py <level-name>")
        console.print("  python3 engine/reset.py all")
        console.print("\nExamples:")
        console.print("  python3 engine/reset.py level-1-pods")
        console.print("  python3 engine/reset.py level-2-deployments")
        console.print("  python3 engine/reset.py all")
        return
    
    if sys.argv[1] == "all":
        reset_all()
    else:
        level = sys.argv[1]
        reset_level_any_world(level)

if __name__ == "__main__":
    main()
