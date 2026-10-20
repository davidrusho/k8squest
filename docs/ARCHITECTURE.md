# K8sQuest Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        K8sQuest Platform                         │
│                 Kubernetes Training Game System                  │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
        ┌───────────────────────────────────────────┐
        │         User Interaction Layer            │
        │  • ./play.sh (Game Launcher)              │
        │  • Rich TUI (Colorful Terminal Interface) │
        │  • Interactive Menus & Commands           │
        └───────────────────────────────────────────┘
                                │
                                ▼
        ┌───────────────────────────────────────────┐
        │         Game Engine (engine.py)           │
        │  • Mission Management                     │
        │  • Progressive Hint System (3 tiers)      │
        │  • XP Tracking & Persistence              │
        │  • Real-time Resource Monitoring          │
        │  • Command Validation                     │
        └───────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
        ┌───────────────────┐   ┌───────────────────┐
        │  Safety Module    │   │  Mission Content  │
        │  (safety.py)      │   │  (Worlds 1-7)     │
        │                   │   │                   │
        │  • Pattern Match  │   │  • 70 Levels      │
        │  • RBAC Check     │   │  • Broken Configs │
        │  • Confirmation   │   │  • Solutions      │
        └───────────────────┘   │  • Hints          │
                                │  • Debriefs       │
                                └───────────────────┘
                                        │
                                        ▼
                        ┌───────────────────────────┐
                        │  Kubernetes Cluster       │
                        │  (kind - Local)           │
                        │                           │
                        │  • k8squest namespace     │
                        │  • RBAC Isolation         │
                        │  • Safe Playground        │
                        └───────────────────────────┘

═══════════════════════════════════════════════════════════════════

                        Data Flow Diagram

    User Input              Game Engine              Kubernetes
        │                       │                        │
        │  Play Level          │                        │
        │─────────────────────>│                        │
        │                       │  Apply broken.yaml    │
        │                       │───────────────────────>│
        │                       │                        │
        │  Request Hint        │                        │
        │─────────────────────>│                        │
        │<─────────────────────│                        │
        │   Display Hint 1     │                        │
        │                       │                        │
        │  kubectl commands    │                        │
        │──────────────────────────────────────────────>│
        │                       │  Safety Check         │
        │<──────────────────────│                        │
        │   Confirm/Block      │                        │
        │                       │                        │
        │  Validate Solution   │                        │
        │─────────────────────>│                        │
        │                       │  Run validate.sh      │
        │                       │───────────────────────>│
        │                       │<───────────────────────│
        │                       │   Pass/Fail           │
        │<─────────────────────│                        │
        │   Show Debrief       │                        │
        │   Award XP           │                        │

═══════════════════════════════════════════════════════════════════

                    Level Structure (Template)

worlds/
└── world-X-name/
    └── level-Y-topic/
        ├── mission.yaml          ← Metadata (name, XP, difficulty, concepts)
        ├── broken.yaml          ← Intentionally broken K8s resources
        ├── solution.yaml        ← (Optional) Fixed version
        ├── validate.sh          ← Pass/fail test script
        ├── hint-1.txt           ← Observation hint
        ├── hint-2.txt           ← Direction hint
        ├── hint-3.txt           ← Near-solution hint
        └── debrief.md           ← Post-mission learning
                                   • What happened
                                   • How K8s behaved
                                   • Mental model
                                   • Real-world incident
                                   • Commands learned

═══════════════════════════════════════════════════════════════════

                    Safety System Architecture

┌──────────────────────────────────────────────────────────────────┐
│                     Safety Guard Layers                          │
└──────────────────────────────────────────────────────────────────┘

Layer 1: Command Pattern Validation (safety.py)
┌────────────────────────────────────────────────────────────┐
│  • Regex pattern matching                                  │
│  • Dangerous commands: delete namespace, --all flags, etc. │
│  • Severity levels: CRITICAL (block) | WARNING (confirm)   │
│  • Rich UI for user feedback                              │
└────────────────────────────────────────────────────────────┘
                            ↓ (if allowed)
Layer 2: RBAC Enforcement (Kubernetes)
┌────────────────────────────────────────────────────────────┐
│  • ServiceAccount: k8squest-player                         │
│  • Namespace: k8squest (isolated)                          │
│  • Role: Full access ONLY in k8squest namespace            │
│  • ClusterRole: Read-only cluster-wide                     │
└────────────────────────────────────────────────────────────┘
                            ↓
Layer 3: Namespace Isolation (Kubernetes)
┌────────────────────────────────────────────────────────────┐
│  • All operations scoped to 'k8squest' namespace           │
│  • System namespaces protected (kube-system, default)      │
│  • Resource quotas can limit usage                         │
└────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════

                    World Progression Path

┌─────────────────────────────────────────────────────────────┐
│  WORLD 1: Core Kubernetes Basics (Levels 1-10) 🚧          │
│  Difficulty: ⭐ Beginner                                    │
│  XP: 1,450                                                  │
│  Status: COMPLETE                                           │
│                                                             │
│  Topics: Pods, Deployments, Labels, Ports, Logs,          │
│          Namespaces, Init Containers                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  WORLD 2: Deployments & Scaling (Levels 11-20) 🚧          │
│  Difficulty: ⭐⭐ Intermediate                              │
│  XP: 2,000                                                  │
│  Status: BLUEPRINTED                                        │
│                                                             │
│  Topics: Rolling Updates, HPA, Probes, Rollbacks,          │
│          Blue-Green, Canary, PDB, StatefulSets             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  WORLD 3: Networking & Services (Levels 21-30) 🚧          │
│  Difficulty: ⭐⭐ Intermediate                              │
│  XP: 2,300                                                  │
│  Status: BLUEPRINTED                                        │
│                                                             │
│  Topics: Services, Ingress, DNS, NetworkPolicy,            │
│          Session Affinity, Cross-namespace                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  WORLD 4: Storage & Stateful Apps (Levels 31-40) 🚧        │
│  Difficulty: ⭐⭐⭐ Advanced                                │
│  XP: 2,600                                                  │
│  Status: BLUEPRINTED                                        │
│                                                             │
│  Topics: PV/PVC, StatefulSets, StorageClass, ConfigMaps,   │
│          Secrets, Volume Permissions                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  WORLD 5: Security & Production Ops (Levels 41-50) 🚧      │
│  Difficulty: ⭐⭐⭐ Advanced                                │
│  XP: 3,150                                                  │
│  Status: BLUEPRINTED                                        │
│                                                             │
│  Topics: RBAC, SecurityContext, ResourceQuotas,            │
│          LimitRanges, PSP, Node Affinity, Taints,          │
│          🔥 CHAOS FINALE (Level 50)                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  WORLD 6: Cluster Architecture & Extensions (Levels 51-60)  │
│  Difficulty: ⭐⭐⭐ Intermediate to Expert                  │
│  XP: 3,250                                                  │
│  Status: COMPLETE                                           │
│                                                             │
│  Topics: Helm, Kustomize, CRDs, cert-manager, Gateway API, │
│          VPA, ServiceAccount RBAC, RuntimeClass/StorageClass│
│          🔥 FINALE (Level 60)                              │
└─────────────────────────────────────────────────────────────┘

                            ↓
┌─────────────────────────────────────────────────────────────┐
│  WORLD 7: Troubleshooting (Levels 61-70)                    │
│  Difficulty: ⭐⭐⭐ Intermediate to Expert                  │
│  XP: 3,150                                                  │
│  Status: COMPLETE                                           │
│  Cluster: kind-multinode (1 control plane + 2 workers),     │
│           created by the engine on first entry              │
│                                                             │
│  Topics: kubelet, scheduler, controller manager, API       │
│          server, CoreDNS, CNI, metrics-server, container   │
│          logs, etcd snapshot, node loss (cordon/drain)     │
│          🔥 FINALE (Level 70)                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  WORLD 8: Cluster lifecycle with kubeadm (Levels 71-76)     │
│  Difficulty: ⭐⭐⭐ Intermediate to Expert                  │
│  XP: 2,050                                                  │
│  Status: COMPLETE                                           │
│  Cluster: lima (two Ubuntu VMs, k8squest-cp and             │
│           k8squest-worker, created by the engine on first   │
│           entry; the levels build the kubeadm cluster)      │
│                                                             │
│  Topics: node prerequisites, kubeadm init, CNI, kubeadm     │
│          join, minor upgrade, etcd snapshot and restore,    │
│          cordon/drain/uncordon with a PodDisruptionBudget   │
│          🔥 FINALE (Level 76)                              │
└─────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════

                    Technology Stack

┌─────────────────────┬─────────────────────────────────────────┐
│ Component           │ Technology                              │
├─────────────────────┼─────────────────────────────────────────┤
│ Game Engine         │ Python 3.x                              │
│ UI Framework        │ rich (Python TUI library)               │
│ Kubernetes          │ kind (Kubernetes in Docker); World 7    │
│                     │ uses a 3-node kind cluster; World 8 a   │
│                     │ kubeadm cluster on two Lima VMs         │
│ Container Runtime   │ Docker Desktop (kind); containerd in    │
│                     │ the World 8 VMs                         │
│ CLI Tool            │ kubectl                                 │
│ Data Format         │ YAML (configs), JSON (progress)         │
│ Scripting           │ Bash (automation, validation)           │
│ Testing             │ Python unittest-style (pytest patterns) │
│ Version Control     │ Git (.gitignore configured)             │
│ Isolation           │ Python venv (dependency management)     │
└─────────────────────┴─────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════

                    Key Metrics Dashboard

┌────────────────────────────────────────────────────────────────┐
│  📊 K8sQuest Statistics                                        │
├────────────────────────────────────────────────────────────────┤
│  Total Levels:              76 (7 worlds of 10, one of 6)     │
│  Total XP Available:        20,050                            │
│  Worlds:                    8                                 │
│  Lines of Code (Engine):    ~1,500                            │
│  Lines of Documentation:    ~3,000+                           │
│  Safety Test Coverage:      20 tests, 100% passing            │
│  Setup Time:                ~5 minutes                        │
│  Avg Level Duration:        10-15 minutes                     │
│  Learning Outcomes:         Practice for parts of the CKA     │
└────────────────────────────────────────────────────────────────┘

Created with ❤️ for Kubernetes learners worldwide
```

## Clusters per world

`world.yaml` names the cluster a world runs on (`cluster: kind`, `kind-multinode` or `lima`), and
`engine/level_reset.py` is the one place that maps it to a kubectl context:

| `cluster:` | kind cluster | kubectl context | Config | Created by |
|---|---|---|---|---|
| `kind` | `k8squest` | `kind-k8squest` (`k3s-k8squest` with `K8S_CLUSTER_TYPE=k3s`) | `kind/cluster.yaml` | `install.sh` |
| `kind-multinode` | `k8squest-multinode` | `kind-k8squest-multinode` | `kind/multinode.yaml` | the engine, on first entry to a World 7 level (or `install.sh --multinode`) |
| `lima` | none: Lima instances `k8squest-cp` and `k8squest-worker` | `k8squest-lima` | `lima/node.yaml` | the engine, on first entry to a World 8 level |

Before deploying a level the engine (`deploy_mission`) calls `ensure_world_cluster`: it
creates the world's cluster if it is missing and switches `kubectl` to the world's context
(also when the player goes back to a `cluster: kind` world). `setup.sh` and `validate.sh`
get `K8SQUEST_CONTEXT` in their environment; `require_game_context` in
`worlds/_shared/lib.sh` refuses to run against any other context. `tests/level_harness.py`
and `engine/reset.py` use the same functions.

A world may ship an optional `heal.sh` next to `world.yaml`. The engine, `engine/reset.py` and
the harness run it before resetting a level, so a fault an earlier level left in the cluster
(World 7 breaks kubelets, control-plane manifests, CoreDNS and kindnet) cannot block the reset
that follows. World 7's `setup.sh` scripts also heal first and only then inject their own fault.

### World 8: the cluster does not exist yet

`cluster: lima` is different from the kind clusters in one way that matters: the game creates two
virtual machines (`ensure_world_cluster` runs `lima_preflight` first, which says what is missing:
`limactl`, QEMU, `/dev/kvm`, RAM), but Kubernetes is built on them by the levels. Levels 71 and 72
start before `kubeadm init`, so there is no API server yet:

- The kubectl context `k8squest-lima` always exists. Until a level has built a cluster it is a
  placeholder that points at the forwarded API port (`127.0.0.1:16443`, `lima/node.yaml`) and has
  no credentials, so kubectl answers "connection refused". Once a cluster exists, the level
  scripts (`export_kubeconfig` in `worlds/world-8-cluster-lifecycle/_shared/lib.sh`) replace it
  with the cluster's admin credentials.
- `world_has_api("lima")` asks the API server whether it answers. When it does not, the engine,
  `engine/reset.py` and `tests/level_harness.py` skip the steps that need one (the connectivity
  check, applying the `k8squest` namespace, `kubectl delete all`, clearing leftovers) and go
  straight to `setup.sh`.
- Players work on the machines with `limactl shell`, and validators run `kubectl` on the control
  plane through `limactl shell` with its own `admin.conf` (`kc` in the lib), so they never depend
  on the player's kubeconfig.
- Every `setup.sh` takes the machines to the state before its level from any state: `kubeadm reset`
  plus the cleanup kubeadm documents as not done, then only the preparation that level needs.
  The machines are reused; deleting them (`limactl delete -f k8squest-cp k8squest-worker`) is the
  fallback and the next level start recreates them.
