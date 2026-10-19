#!/usr/bin/env python3
"""
K8sQuest World Discovery

Worlds are directories: worlds/<world>/world.yaml plus level-* subdirectories.
Everything the game needs to know about the world list, level counts and XP
totals is computed from what is on disk, so adding a world is adding a directory.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml

VALID_CLUSTERS = ("kind", "kind-multinode", "lima")

REQUIRED_WORLD_FIELDS = ("order", "title", "description", "cluster", "requires")

# The mandatory files in every level (docs/contributing.md)
REQUIRED_LEVEL_FILES = (
    "mission.yaml",
    "broken.yaml",
    "solution.yaml",
    "validate.sh",
    "hint-1.txt",
    "hint-2.txt",
    "hint-3.txt",
    "debrief.md",
)


class WorldDiscoveryError(ValueError):
    """Raised when worlds/ on disk is inconsistent."""


@dataclass
class Level:
    name: str
    path: Path
    xp: int = 0
    mission: dict = field(default_factory=dict)


@dataclass
class World:
    dir_name: str
    path: Path
    order: int
    title: str
    description: str
    cluster: str
    requires: List[str]
    levels: List[Level] = field(default_factory=list)

    @property
    def display_name(self):
        return f"World {self.order}: {self.title}"

    @property
    def total_xp(self):
        return sum(level.xp for level in self.levels)


def natural_sort_key(path):
    """Sort level-2 before level-10."""
    return [
        int(part) if part.isdigit() else part
        for part in re.split(r"(\d+)", Path(path).name)
    ]


def _load_yaml(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return yaml.safe_load(f)


def _load_world(world_yaml):
    data = _load_yaml(world_yaml)
    where = str(world_yaml)
    if not isinstance(data, dict):
        raise WorldDiscoveryError(f"{where}: expected a mapping")
    for key in REQUIRED_WORLD_FIELDS:
        if key not in data:
            raise WorldDiscoveryError(f"{where}: missing field '{key}'")
    # bool is an int subclass; reject it explicitly
    if not isinstance(data["order"], int) or isinstance(data["order"], bool):
        raise WorldDiscoveryError(f"{where}: 'order' must be an integer")
    if data["cluster"] not in VALID_CLUSTERS:
        raise WorldDiscoveryError(
            f"{where}: 'cluster' must be one of {', '.join(VALID_CLUSTERS)}, "
            f"got {data['cluster']!r}"
        )
    requires = data["requires"]
    if not isinstance(requires, list) or not all(isinstance(r, str) for r in requires):
        raise WorldDiscoveryError(f"{where}: 'requires' must be a list of strings")
    for key in ("title", "description"):
        if not isinstance(data[key], str) or not data[key].strip():
            raise WorldDiscoveryError(f"{where}: '{key}' must be a non-empty string")

    world_dir = world_yaml.parent
    world = World(
        dir_name=world_dir.name,
        path=world_dir,
        order=data["order"],
        title=data["title"],
        description=data["description"],
        cluster=data["cluster"],
        requires=list(requires),
    )
    for level_dir in sorted(world_dir.glob("level-*"), key=natural_sort_key):
        if not level_dir.is_dir():
            continue
        mission = {}
        mission_file = level_dir / "mission.yaml"
        if mission_file.exists():
            mission = _load_yaml(mission_file) or {}
        xp = mission.get("xp", 0)
        world.levels.append(
            Level(
                name=level_dir.name,
                path=level_dir,
                xp=xp if isinstance(xp, int) else 0,
                mission=mission,
            )
        )
    return world


def discover_worlds(base_dir: Optional[Path] = None) -> List[World]:
    """Return all worlds under <base_dir>/worlds, sorted by world.yaml `order`.

    Raises WorldDiscoveryError on a malformed world.yaml, a duplicate `order`,
    or a level name that appears more than once across worlds.
    """
    if base_dir is None:
        base_dir = Path(__file__).parent.parent
    worlds_dir = Path(base_dir) / "worlds"

    worlds = [_load_world(p) for p in sorted(worlds_dir.glob("*/world.yaml"))]
    worlds.sort(key=lambda w: (w.order, w.dir_name))

    orders = {}
    for world in worlds:
        if world.order in orders:
            raise WorldDiscoveryError(
                f"duplicate world order {world.order}: "
                f"{orders[world.order]} and {world.dir_name}"
            )
        orders[world.order] = world.dir_name

    seen = {}
    for world in worlds:
        for level in world.levels:
            if level.name in seen:
                raise WorldDiscoveryError(
                    f"duplicate level name '{level.name}' in "
                    f"{seen[level.name]} and {world.dir_name}"
                )
            seen[level.name] = world.dir_name
    return worlds


def total_levels(worlds: List[World]) -> int:
    return sum(len(w.levels) for w in worlds)


def total_xp(worlds: List[World]) -> int:
    return sum(w.total_xp for w in worlds)


def find_world(order: int, base_dir: Optional[Path] = None) -> Optional[World]:
    """Return the world whose world.yaml `order` is `order`, or None."""
    return next((w for w in discover_worlds(base_dir) if w.order == order), None)
