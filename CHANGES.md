# Changes

This repository is a modified fork of [K8sQuest](https://github.com/Manoj-engineer/k8squest)
by Manoj-engineer, licensed under the Apache License, Version 2.0 (see `License`).
As required by section 4(b) of that license, this file states that the files
listed below have been changed from the upstream versions. Files not listed
are unchanged from upstream.

## Level fixes: six levels now start in the broken state they describe

### Modified

- `worlds/world-4-storage/level-37-secret-encoding` - `broken.yaml` no longer passes `validate.sh` before the player acts: the Secret's `username` is base64-encoded twice, so the pod receives `YWRtaW4=` and crash-loops on its username check. Mission, hints and debrief describe the double encoding.
- `worlds/world-5-security/level-43-resourcequota` and `level-48-pod-security` - the broken object is now a Deployment (`resource-hungry-app`, `secure-app`) instead of a bare Pod. Quota and Pod Security `enforce` apply to Pods, so the Deployment is admitted and the engine's `kubectl apply` succeeds; the rejection shows as `FailedCreate` events on the ReplicaSet (`kubectl describe rs`, `kubectl get events`). Before, the bare Pod was rejected at apply time and the engine aborted with "Deployment failed". `broken.yaml`, `solution.yaml`, `validate.sh`, mission, hints and debrief were updated; `validate.sh` of level 48 now also requires a `seccompProfile` instead of only warning.
- `worlds/world-5-security/level-45-node-affinity`, `level-46-taints-tolerations`, `level-50-chaos-finale` - `setup.sh` now applies `broken.yaml` after preparing the node. The engine runs only `setup.sh` when a level has one, so the player used to get an empty namespace.

## World 8: Cluster lifecycle with kubeadm, and Lima virtual machines

### Added

- `worlds/world-8-cluster-lifecycle/` - World 8 (`order: 8`, `cluster: lima`, `requires: [limactl]`), levels 71-76, 2,050 XP: node prerequisites checked with `kubeadm init phase preflight` (71), `kubeadm init` and a Flannel pod network (72), `kubeadm join` with a token and the CA hash (73), a v1.36.5 to v1.37.1 upgrade (74), an etcd snapshot and a restore with `etcdutl` (75), and a finale that drains, maintains and uncordons a node behind a PodDisruptionBudget (76).
- `worlds/world-8-cluster-lifecycle/_shared/lib.sh` and `_shared/guest/` - helpers that put the two machines into the state before a level from any state (`kubeadm reset` plus cleanup, then the preparation that level needs), run commands in the machines with `limactl shell`, build the cluster, and export the cluster's credentials into the kubectl context `k8squest-lima`. Versions are pinned in this one file: Kubernetes v1.36.5 and v1.37.1 (packages 1.36.5-1.1 and 1.37.1-1.1 from pkgs.k8s.io) and Flannel v0.28.9.
- `lima/node.yaml` - the Lima instance definition for `k8squest-cp` and `k8squest-worker`: Ubuntu 26.04 server image pinned to the release-20260927 build with sha256 digests, the shared `user-v2` network, no host mounts, only the API server port forwarded to the host (16443).
- `engine/level_reset.py` - `cluster: lima`: `context_for("lima")` is `k8squest-lima`; `lima_preflight` checks for `limactl` 2.0 or newer, and on Linux for QEMU, `/dev/kvm` readable and writable, and 8 GiB of RAM, and says what is missing; `ensure_world_cluster` creates and starts the two machines from `lima/node.yaml` (reusing existing ones) and makes sure the kubectl context exists (a placeholder with no credentials until a level builds a cluster); `world_has_api` lets the engine, `engine/reset.py` and the harness skip the namespace work for levels that start before any cluster exists.
- `solution.sh` convention extended to levels 71-76.
- Supply chain and ownership: the etcd tarball (3.7.0, per architecture) and the Flannel v0.28.9 manifest are pinned by sha256 in the repo (`_shared/guest/base.sh`, `_shared/lib.sh`) and refused on a mismatch. The machines the game creates carry the Lima template parameter `k8squest_world: "8"` (`lima/node.yaml`); a same-named machine without it is refused with instructions to delete or clone it, and the harness deletes only the machines it created.

### Modified

- `engine/engine.py` and `engine/reset.py` - skip the connectivity check, the namespace apply, `kubectl delete all` and the leftover clean-up when `world_has_api` says the World 8 cluster does not exist yet.
- `tests/level_harness.py` - supports `lima`: creates the machines through `ensure_world_cluster`, deletes the ones it created, treats a comment-only `broken.yaml` as having nothing to apply, and allows 900 seconds for a setup or a scripted fix.
- `tests/test_level_reset.py` - tests for the Lima mapping, the preflight, creating, starting and reusing the machines, the placeholder context, and skipping the namespace work, using a stub `limactl`.
- `tests/test_discovery.py` - expects 8 worlds, 76 levels and 20,050 XP.
- `README.md`, `docs/ARCHITECTURE.md`, `docs/LEARNING-PATH.md`, `docs/contributing.md` - World 8, its requirements (Lima, KVM or macOS, 5.5 GiB of RAM for the machines), the Lima cluster type, and totals (76 levels, 20,050 XP); the CKA rows say what is and is not covered.
- `worlds/world-7-troubleshooting/level-70-troubleshooting-finale/debrief.md` - "What's Next" points to World 8.

## World 7: Troubleshooting, and multi-node cluster support

### Added

- `worlds/world-7-troubleshooting/` - World 7 (`order: 7`, `cluster: kind-multinode`, `requires: [docker]`), levels 61-70, 3,150 XP: stopped kubelet (61), kubelet configuration fault (62), kube-scheduler manifest fault (63), kube-controller-manager manifest fault (64), kube-apiserver manifest fault diagnosed with `crictl` (65), CoreDNS scaled to 0 and a wrong Corefile zone (66), a node without its CNI configuration because the kindnet DaemonSet skips it (67), metrics-server missing `--kubelet-insecure-tls` (68), a crash-looping container read with `kubectl logs -c ... --previous` (69), and a finale with an etcd snapshot (`etcdctl` and `etcdutl` through `kubectl exec`) plus a lost worker (cordon and drain) (70). etcd restore and a multi-control-plane failover are not part of this world.
- `worlds/world-7-troubleshooting/_shared/lib.sh` and `heal.sh` - `heal_cluster` puts back anything an earlier level or the player left broken (kubelet state, kubelet config and flags, the control-plane manifests, the CoreDNS Corefile and replicas, the kindnet nodeSelector and node label, metrics-server arguments, cordoned nodes) from pristine copies kept on the nodes in `/root/k8squest-pristine/`. Every `setup.sh` heals first and injects its own fault second.
- `worlds/_shared/lib.sh` - helpers shared by Worlds 6 and 7: `log`, `need`, `retry`, `wait_available`, `require_game_context` (now checks `K8SQUEST_CONTEXT`) and `ensure_metrics_server` (moved here from World 6's `_shared/lib.sh`, version pin unchanged).
- `engine/level_reset.py` `inotify_preflight`: before the engine creates the multi-node cluster on Linux it requires `fs.inotify.max_user_instances` >= 512 (the `k8squest` and `k8squest-multinode` clusters together fail with `too many open files` at the Ubuntu default of 128) and otherwise refuses with the `sysctl` commands; skipped where the file does not exist. Documented in `README.md` and `docs/contributing.md`.
- `kind/multinode.yaml` - one control-plane node and two workers with the same pinned node image as `kind/cluster.yaml`; created as the cluster `k8squest-multinode` (context `kind-k8squest-multinode`).
- `solution.sh` convention (levels 61-70): when a level has one, `tests/level_harness.py` runs it instead of applying `solution.yaml`; the engine never runs it. `solution.yaml` stays as the player-facing reference.

### Modified

- `engine/level_reset.py` - `context_for(cluster)` is the one mapping from a `world.yaml` `cluster:` value to a kubectl context; `ensure_world_cluster` creates the multi-node cluster when it is missing and switches the kubectl context (also back to the main cluster for `cluster: kind` worlds); `level_env` gives `setup.sh` and `validate.sh` `K8SQUEST_CONTEXT`; `run_world_heal` runs a world's optional `heal.sh`; `on_game_cluster` also accepts the multi-node context.
- `engine/engine.py` - `deploy_mission` ensures the world's cluster, runs the world's heal step and passes `K8SQUEST_CONTEXT` to `setup.sh` and `validate.sh`.
- `engine/reset.py` - switches to the level's world cluster before it deletes the namespace; `deploy_level` also ensures the cluster and runs the world's heal step.
- `tests/level_harness.py` - supports `kind-multinode`, switches the kubectl context per world, deletes only clusters it created, runs `solution.sh`, runs the world's `heal.sh`, exits non-zero when a level is skipped, and takes repeatable `--world` and `--level` options (several `--level` run in the order given) and `--from-world N`.
- `tests/test_level_reset.py` - tests for the context mapping and the cluster creation and switching, using a stub `kind`.
- `tests/test_discovery.py` - expects 7 worlds, 70 levels and 18,000 XP; checks that `worlds/_shared` is not treated as a world.
- `utils/test-all-levels.sh` - skips `worlds/_shared`.
- `install.sh` - optional `--multinode` flag; the existing-cluster test now matches the exact name `k8squest` (a plain `grep k8squest` would also match `k8squest-multinode`).
- World 6's `require_game_context` (now in `worlds/_shared/lib.sh`) accepts the context the engine exports in `K8SQUEST_CONTEXT`, so with `K8S_CLUSTER_TYPE=k3s` it now accepts `k3s-k8squest` (before, it accepted only `kind-k8squest`). `tests/level_harness.py` restores the kubectl context it started with when it exits. `ensure_world_cluster` reports a missing `kubectl`/`kind`/`docker`, checks the follow-up namespace and RBAC applies, and tells the player to delete a multinode cluster whose node containers are not running. World 7's lib defaults `K8SQUEST_CONTEXT` to `kind-k8squest-multinode`, so a script run by hand on the main cluster refuses.
- `worlds/world-6-cluster-architecture/_shared/lib.sh` - sources `worlds/_shared/lib.sh` for the helpers that moved there.
- `worlds/world-6-cluster-architecture/level-60-architecture-finale/debrief.md` - "What's Next" points to World 7.
- `README.md`, `docs/ARCHITECTURE.md`, `docs/LEARNING-PATH.md`, `docs/contributing.md` - World 7, the second cluster, `heal.sh`, `solution.sh`, and totals (70 levels, 18,000 XP); the CKA troubleshooting row says what is and is not covered.

## World 6: Cluster Architecture & Extensions

### Added

- `worlds/world-6-cluster-architecture/` - World 6 (`order: 6`, `cluster: kind`, `requires: [helm]`), levels 51-60, 3,250 XP: Helm failed upgrade (51), Kustomize overlay patch target (52), CRD schema (53), cert-manager Issuer/Certificate (54), Gateway API HTTPRoute parentRef and backendRef (55), ReferenceGrant (56), VPA targetRef (57), ServiceAccount RoleBinding subject (58), RuntimeClass and StorageClass extension points (59), and a three-component finale (60).
- `worlds/world-6-cluster-architecture/_shared/lib.sh` - idempotent installers for cert-manager v1.21.2, Gateway API v1.6.3 (standard channel), Envoy Gateway v1.9.2, metrics-server v0.9.0 (with `--kubelet-insecure-tls` for kind) and the VPA 1.8.0 recommender, used by the `setup.sh` scripts of levels 54-57, 60. All versions are pinned in this one file.
- Level 51 (`chart/`) and level 52 (`kustomize/`) carry their own Helm chart and Kustomize base and overlay.

- `tests/test_level_reset.py` - stub-kubectl tests for `engine/level_reset.py`.
- `engine/level_reset.py` - shared reset used by the engine, `engine/reset.py` and `tests/level_harness.py`: after `kubectl delete all` it clears quotas, limit ranges, network policies, roles, role bindings, service accounts, config maps, secrets, PVCs and the level-set node taint and label.

### Modified

- `engine/engine.py` - calls `clear_leftovers` after `kubectl delete all`.
- `engine/reset.py` - redeploys through the same path as the engine (runs `setup.sh` when a level has one, otherwise applies `broken.yaml`) instead of applying `broken.yaml` with `-n`.
- `tests/level_harness.py` - uses `clear_leftovers`; `--isolate` now only deletes the namespace.
- `tests/test_discovery.py` - expects 6 worlds, 60 levels and 14,850 XP.
- `README.md`, `docs/ARCHITECTURE.md`, `docs/LEARNING-PATH.md`, `docs/contributing.md` - World 6 added; level, world and XP totals updated; the CKA coverage table now lists what World 6 covers; `helm` listed as a requirement for World 6.
- `worlds/world-5-security/level-50-chaos-finale/debrief.md` - "What's Next" now points to World 6 as available.

## Data-driven worlds and refreshed Kubernetes version

### Added

- `engine/world_discovery.py` - discovers worlds from `worlds/*/world.yaml`, sorted by `order`; computes level and XP totals from the `mission.yaml` files; rejects duplicate level names, duplicate world orders and invalid `world.yaml` files; `find_world(order)` looks a world up by its `order`; a level without a valid `mission.yaml` (a mapping with an integer `xp`) is an error; `milestones_for` decides which milestones to celebrate.
- `worlds/world-1-basics/world.yaml`, `worlds/world-2-deployments/world.yaml`, `worlds/world-3-networking/world.yaml`, `worlds/world-4-storage/world.yaml`, `worlds/world-5-security/world.yaml` - world metadata (`order`, `title`, `description`, `cluster`, `requires`).
- `worlds/world-2-deployments/level-14-hpa/solution.yaml` - the level previously had only `SOLUTION.md`; the new file carries the same commands so the level has the 8 mandatory files.
- `kind/cluster.yaml` - kind cluster configuration pinning the node image to Kubernetes v1.37.0.
- `tests/test_discovery.py` - tests for world discovery, level and XP totals, unique level names, mandatory files, `world.yaml` and `mission.yaml` validity, and milestone selection.
- `CHANGES.md` - this file.

### Modified

- `engine/engine.py` - world list, level count and XP total come from discovery instead of hard-coded values; milestones are decided by `milestones_for` (per-world and total-aware, and only when a level is newly completed).
- `engine/retro_ui.py` - XP bar maximum and "all levels" message take their numbers from the caller; worlds without a hand-drawn banner get one built from the `title` and `description` in `world.yaml`.
- `engine/certificate.py` - worlds without a hand-written entry take their name, level count and skills from `world.yaml` and the level missions; the "Next:" line comes from the next world by `order`.
- `engine/start_game.sh` - plays the lowest-`order` world found in `world.yaml` files, in numeric level order, instead of a hard-coded World 1 path.
- `tools/progress_tracker.py` - uses the engine's world discovery and reads the `completed_levels` key the engine writes.
- `tools/create_level.sh` - looks up the world by `order` using the engine's world discovery, refuses duplicate level names, and creates `solution.yaml`.
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

Each modified source or script file listed above (`engine/*.py`, `engine/start_game.sh`, `tools/*`, `utils/*`, `install.sh`, `Dockerfile`) carries a "Modified 2026 by David Rusho; see CHANGES.md" comment near the top.
