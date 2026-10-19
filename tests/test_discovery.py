#!/usr/bin/env python3
"""
Test suite for K8sQuest world discovery

Usage: python3 tests/test_discovery.py [repo_root]
(repo_root defaults to the checkout containing this file; pass another tree to
test a copy of worlds/)
"""

import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml
from engine.world_discovery import (
    REQUIRED_LEVEL_FILES,
    VALID_CLUSTERS,
    WorldDiscoveryError,
    discover_worlds,
    total_levels,
    total_xp,
)
from rich.console import Console
from rich.markup import escape

console = Console()

BASE_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent

# Update these when a new world lands (Worlds 6-8 are in progress)
EXPECTED_WORLD_ORDERS = [1, 2, 3, 4, 5]
EXPECTED_LEVELS = 50
EXPECTED_XP = 11600


def level_dirs():
    """Every level directory on disk, found without using the discovery module"""
    return sorted(BASE_DIR.glob("worlds/*/level-*"))


def check_world_order():
    worlds = discover_worlds(BASE_DIR)
    orders = [w.order for w in worlds]
    if orders != EXPECTED_WORLD_ORDERS:
        return f"expected world orders {EXPECTED_WORLD_ORDERS}, got {orders}"
    return None


def check_level_count():
    dirs = [d for d in level_dirs() if d.is_dir()]
    found = total_levels(discover_worlds(BASE_DIR))
    if len(dirs) != EXPECTED_LEVELS or found != EXPECTED_LEVELS:
        return f"expected {EXPECTED_LEVELS} levels, {len(dirs)} on disk, {found} discovered"
    return None


def check_xp_total():
    on_disk = 0
    for mission in BASE_DIR.glob("worlds/*/level-*/mission.yaml"):
        with open(mission, encoding="utf-8") as f:
            on_disk += yaml.safe_load(f)["xp"]
    found = total_xp(discover_worlds(BASE_DIR))
    if on_disk != EXPECTED_XP or found != EXPECTED_XP:
        return f"expected {EXPECTED_XP} XP, {on_disk} summed from mission.yaml, {found} discovered"
    return None


def check_unique_level_names():
    names = [d.name for d in level_dirs()]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        return f"duplicate level names: {', '.join(dupes)}"
    return None


def check_mandatory_files():
    problems = []
    for level_dir in level_dirs():
        missing = [f for f in REQUIRED_LEVEL_FILES if not (level_dir / f).is_file()]
        if missing:
            problems.append(f"{level_dir.parent.name}/{level_dir.name}: {', '.join(missing)}")
    if problems:
        return "missing files: " + "; ".join(problems)
    return None


def check_world_yaml_clusters():
    problems = []
    world_dirs = [d for d in sorted(BASE_DIR.glob("worlds/*")) if d.is_dir()]
    for world_dir in world_dirs:
        world_yaml = world_dir / "world.yaml"
        if not world_yaml.is_file():
            problems.append(f"{world_dir.name}: no world.yaml")
            continue
        with open(world_yaml, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data.get("cluster") not in VALID_CLUSTERS:
            problems.append(f"{world_dir.name}: cluster {data.get('cluster')!r}")
    if problems:
        return "; ".join(problems) + f" (valid: {', '.join(VALID_CLUSTERS)})"
    return None


def _write_world(root, dir_name, order, cluster, level_names):
    world = root / "worlds" / dir_name
    world.mkdir(parents=True)
    (world / "world.yaml").write_text(
        f'order: {order}\ntitle: "T"\ndescription: "D"\ncluster: {cluster}\nrequires: []\n',
        encoding="utf-8",
    )
    for name in level_names:
        (world / name).mkdir()
        (world / name / "mission.yaml").write_text("name: x\nxp: 10\n", encoding="utf-8")


def _rejects(build):
    """True when discovery raises WorldDiscoveryError for the tree `build` makes"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build(root)
        try:
            discover_worlds(root)
        except WorldDiscoveryError:
            return True
        return False


def check_discovery_rejects_bad_trees():
    def dup_level(root):
        _write_world(root, "world-a", 1, "kind", ["level-1-same"])
        _write_world(root, "world-b", 2, "kind", ["level-1-same"])

    def bad_cluster(root):
        _write_world(root, "world-a", 1, "minikube", ["level-1-a"])

    def dup_order(root):
        _write_world(root, "world-a", 1, "kind", ["level-1-a"])
        _write_world(root, "world-b", 1, "kind", ["level-2-b"])

    problems = [
        label
        for label, build in (
            ("duplicate level name", dup_level),
            ("invalid cluster", bad_cluster),
            ("duplicate world order", dup_order),
        )
        if not _rejects(build)
    ]
    if problems:
        return "discovery accepted: " + ", ".join(problems)
    return None


def test_discovery():
    """Test world discovery against the worlds/ tree"""

    tests = [
        # (check, description)
        (check_world_order, "5 worlds discovered, ordered 1-5 by world.yaml"),
        (check_level_count, "50 levels on disk and discovered"),
        (check_xp_total, "XP total is 11600, summed from mission.yaml files"),
        (check_unique_level_names, "Level names are unique across worlds"),
        (check_mandatory_files, "Every level has the 8 mandatory files"),
        (check_world_yaml_clusters, "Every world has a world.yaml with a valid cluster"),
        (check_discovery_rejects_bad_trees, "Discovery rejects duplicate names, bad cluster, duplicate order"),
    ]

    passed = 0
    failed = 0

    console.print("\n[bold cyan]🧪 Testing K8sQuest World Discovery[/bold cyan]\n")
    console.print("="*70)

    for check, description in tests:
        try:
            error = check()
        except Exception as e:
            error = f"{type(e).__name__}: {e}"

        if error is None:
            console.print(f"[green]✅ PASS[/green] - {description}")
            passed += 1
        else:
            console.print(f"[red]❌ FAIL[/red] - {description}")
            console.print(f"  [dim]{escape(error)}[/dim]")
            failed += 1

    console.print("="*70)
    console.print(f"\n[bold]Results:[/bold] {passed} passed, {failed} failed out of {len(tests)} tests\n")

    if failed == 0:
        console.print("[bold green]🎉 All discovery tests passed![/bold green]\n")
        return 0
    else:
        console.print(f"[bold red]⚠️  {failed} test(s) failed![/bold red]\n")
        return 1

if __name__ == "__main__":
    exit_code = test_discovery()
    sys.exit(exit_code)
