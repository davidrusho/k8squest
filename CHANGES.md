# Changes

This repository is a modified fork of [K8sQuest](https://github.com/Manoj-engineer/k8squest)
by Manoj-engineer, licensed under the Apache License, Version 2.0 (see `License`).
As required by section 4(b) of that license, this file states that the files
listed below have been changed from the upstream versions. Files not listed
are unchanged from upstream.

## Data-driven worlds and refreshed Kubernetes version

### Added

- `engine/world_discovery.py` - discovers worlds from `worlds/*/world.yaml`, sorted by `order`; computes level and XP totals from the `mission.yaml` files; rejects duplicate level names, duplicate world orders and invalid `world.yaml` files; `find_world(order)` looks a world up by its `order`.
- `worlds/world-1-basics/world.yaml`, `worlds/world-2-deployments/world.yaml`, `worlds/world-3-networking/world.yaml`, `worlds/world-4-storage/world.yaml`, `worlds/world-5-security/world.yaml` - world metadata (`order`, `title`, `description`, `cluster`, `requires`).
- `worlds/world-2-deployments/level-14-hpa/solution.yaml` - the level previously had only `SOLUTION.md`; the new file carries the same commands so the level has the 8 mandatory files.
- `kind/cluster.yaml` - kind cluster configuration pinning the node image to Kubernetes v1.37.0.
- `tests/test_discovery.py` - tests for world discovery, level and XP totals, unique level names, mandatory files and `world.yaml` validity.
- `CHANGES.md` - this file.

### Modified

- `engine/engine.py` - world list, level count and XP total come from discovery instead of hard-coded values.
- `engine/retro_ui.py` - XP bar maximum and "all levels" message take their numbers from the caller; worlds without a hand-drawn banner get one built from the `title` and `description` in `world.yaml`.
- `engine/certificate.py` - worlds without a hand-written entry take their name, level count and skills from `world.yaml` and the level missions; the "Next:" line comes from the next world by `order`.
- `engine/start_game.sh` - plays the lowest-`order` world found in `world.yaml` files, in numeric level order, instead of a hard-coded World 1 path.
- `tools/progress_tracker.py` - uses the engine's world discovery and reads the `completed_levels` key the engine writes.
- `tools/create_level.sh` - looks up the world by `order` in `world.yaml`, refuses duplicate level names, and creates `solution.yaml`.
- `utils/test-all-levels.sh` - checks every level in every world, plus `world.yaml` validity and the 8 mandatory files.
- `utils/audit_levels.sh` - derives the level count from disk.
- `install.sh` - creates the cluster from `kind/cluster.yaml` and warns when kind is older than v0.33.0.
- `Dockerfile` - kubectl v1.37.1, verified against the `kubectl.sha256` published next to it on dl.k8s.io; no longer copies the git-ignored `progress.json` (the engine creates it at runtime).
- `worlds/world-5-security/level-50-chaos-finale/validate.sh` - dropped the hard-coded level and XP totals.
- `worlds/world-5-security/level-50-chaos-finale/debrief.md` - "What's Next" points to Worlds 6-8 instead of declaring exam readiness; per-world and total XP corrected.
- `worlds/world-2-deployments/QUICK-REFERENCE.md` - replaced the deprecated `--record` flag with the `kubernetes.io/change-cause` annotation.
- `docs/LEARNING-PATH.md` - certification sections rewritten against the official CKA domains and weights; removed the "exam-ready in 2 weeks" and "production-ready" claims and the stale "(Coming)" markers.
- `docs/ARCHITECTURE.md` - removed the "CKA exam preparation level" claim; corrected the level and XP statistics.
- `docs/50-CHALLENGE-BLUEPRINT.md` - added a note that the blueprint is historical and that totals are computed from `mission.yaml` files.
- `docs/contributing.md` - documented the `world.yaml` schema; a level may only use tools its world declares in `requires`; the world list now points at `world.yaml`; updated the status line.
- `README.md` - describes 5 worlds today with Worlds 6-8 in progress; per-world XP and the World 1 level list match the mission files.
