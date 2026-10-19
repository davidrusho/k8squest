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
    milestones_for,
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


def _write_world(root, dir_name, order, cluster, level_names,
                 mission_text="name: x\nxp: 10\n", world_text=None):
    """Write a tiny world. mission_text=None writes no mission.yaml at all."""
    world = root / "worlds" / dir_name
    world.mkdir(parents=True)
    if world_text is None:
        world_text = f'order: {order}\ntitle: "T"\ndescription: "D"\ncluster: {cluster}\nrequires: []\n'
    (world / "world.yaml").write_text(world_text, encoding="utf-8")
    for name in level_names:
        (world / name).mkdir()
        if mission_text is not None:
            (world / name / "mission.yaml").write_text(mission_text, encoding="utf-8")


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


def _bad_mission_cases():
    """(label, mission.yaml text or None) pairs discovery must reject"""
    return [
        ("string xp", 'name: x\nxp: "100"\n'),
        ("float xp", "name: x\nxp: 1.5\n"),
        ("bool xp", "name: x\nxp: true\n"),
        ("missing xp", "name: x\n"),
        ("missing mission.yaml", None),
        ("malformed mission.yaml", "name: [unclosed\nxp: 10\n"),
        ("non-mapping mission.yaml", "- just\n- a list\n"),
        ("empty mission.yaml", ""),
    ]


def check_discovery_rejects_bad_missions():
    problems = []
    for label, text in _bad_mission_cases():
        def build(root, text=text):
            _write_world(root, "world-a", 1, "kind", ["level-1-a"], mission_text=text)
        try:
            if not _rejects(build):
                problems.append(f"{label}: accepted")
        except Exception as e:
            problems.append(f"{label}: raised {type(e).__name__} instead of WorldDiscoveryError")
    if problems:
        return "; ".join(problems)
    return None


def check_discovery_rejects_malformed_world_yaml():
    def build(root):
        _write_world(root, "world-a", 1, "kind", ["level-1-a"], world_text="order: [unclosed\n")
    try:
        if not _rejects(build):
            return "accepted a malformed world.yaml"
    except Exception as e:
        return f"raised {type(e).__name__} instead of WorldDiscoveryError"
    return None


def _simulate(total, per_world=10):
    """Complete `total` levels in order across worlds of `per_world`; return [(count, milestones)]"""
    names = [f"level-{i}-x" for i in range(1, total + 1)]
    world_levels = [names[i:i + per_world] for i in range(0, total, per_world)]
    completed = set()
    events = []
    for name in names:
        completed.add(name)
        got = milestones_for(world_levels, completed, name, True)
        events.append((len(completed), got))
    return world_levels, names, events


def check_milestones_across_totals():
    problems = []
    for total in (1, 2, 3, 10, 11, 20, 50, 60, 76):
        world_levels, names, events = _simulate(total)
        fired = {}
        for count, got in events:
            for m in got:
                fired.setdefault(m, []).append(count)
        expect_once = ["game_complete"] + (["final_boss"] if total >= 2 else []) + (["halfway"] if total >= 3 else [])
        for m in expect_once:
            if len(fired.get(m, [])) != 1:
                problems.append(f"T={total}: {m} fired at {fired.get(m, [])}")
        if total < 3 and fired.get("halfway"):
            problems.append(f"T={total}: halfway fired at {fired['halfway']} (cannot be distinct)")
        if total < 2 and fired.get("final_boss"):
            problems.append(f"T={total}: final_boss fired at {fired['final_boss']} (cannot be distinct)")
        if fired.get("game_complete") and fired["game_complete"] != [total]:
            problems.append(f"T={total}: game_complete at {fired['game_complete']}")
        if total >= 3:
            counts = [fired[m][0] for m in ("halfway", "final_boss", "game_complete") if fired.get(m)]
            if len(set(counts)) != len(counts):
                problems.append(f"T={total}: milestone counts collide {counts}")
        # world_complete: once per world except the last (game_complete covers that)
        want = len(world_levels) - 1
        got_wc = fired.get("world_complete", [])
        if len(got_wc) != want:
            problems.append(f"T={total}: world_complete fired {len(got_wc)}x, expected {want}")
        else:
            ends = [sum(len(w) for w in world_levels[:i + 1]) for i in range(want)]
            if got_wc != ends:
                problems.append(f"T={total}: world_complete at {got_wc}, world ends {ends}")
    if problems:
        return "; ".join(problems)
    return None


def check_milestones_not_on_replay():
    world_levels, names, _ = _simulate(20)
    completed = set(names)
    for name in names:
        got = milestones_for(world_levels, completed, name, False)
        if got:
            return f"replaying {name} fired {got}"
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
        (check_discovery_rejects_bad_missions, "Discovery rejects non-int/bool/missing xp, missing/malformed/non-mapping mission.yaml"),
        (check_discovery_rejects_malformed_world_yaml, "Discovery rejects a malformed world.yaml"),
        (check_milestones_across_totals, "Milestones fire once each and never collide for T = 1, 2, 3, 10, 11, 20, 50, 60, 76"),
        (check_milestones_not_on_replay, "Replaying a completed level fires no milestone"),
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
