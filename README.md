# K8sQuest 🕹️⚙️

[![Platform Support](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-blue)]()
[![Shell](https://img.shields.io/badge/shell-bash-green)]()
[![Kubernetes](https://img.shields.io/badge/kubernetes-learning-326CE5)]()

Learn Kubernetes by fixing it.

K8sQuest is a **local, game-based Kubernetes training platform** with an interactive GUI-like terminal interface. Each mission breaks something in Kubernetes. Your job is to fix it.

**76 progressive challenges across 8 worlds** - from beginner to expert. World 8 builds, upgrades and repairs a real kubeadm cluster on two Lima virtual machines.

No cloud. No AWS. No costs.

## Features

- 📊 **Real-time Monitoring** - Watch Kubernetes resources update live with "check" command
- 💡 **Progressive Hints** - Unlocks gradually as you need help
- 📚 **Step-by-Step Guides** - Beginner-friendly walkthroughs when you need them
- **Post-Mission Debriefs** - Learn WHY your fix worked with real-world examples
- 🎯 **Clear Mission Briefings** - Know difficulty, time estimate, and concepts
- 🏆 **XP & Progress System** - Track your learning journey and achievements
- 🎮 **Multi-Terminal Workflow** - Learn real-world debugging patterns
- 💾 **Auto-Save Progress** - Never lose your achievements
- 🔄 **Reset Levels** - Get stuck? Clean slate anytime

## 🛡️ Safety First

K8sQuest includes **comprehensive safety guards** (enabled by default):
- ✅ Prevents deletion of critical namespaces (kube-system, default, etc.)
- ✅ Blocks destructive cluster-wide operations
- ✅ Limits operations to `k8squest` namespace via RBAC
- ✅ Confirms risky operations before execution
- ✅ Safe for beginners - hard to break things!

[Learn more about safety guards →](docs/SAFETY.md)

**Note:** the game changes your current `kubectl` context (to `kind-k8squest`, `kind-k8squest-multinode` or `k8squest-lima`, whichever the world needs). To go back to yours, run `kubectl config use-context <your-context>`.

## Requirements
- Docker Desktop (running)
- kubectl v1.37.x (the Dockerfile pins v1.37.1, and the kind cluster runs Kubernetes v1.37.0)
- kind v0.33.0 or newer (`install.sh` warns on anything older)
- bash
- python3 (3.9+)
- jq
- Docker is also what World 7 (Troubleshooting) uses to reach the cluster nodes (`docker exec -it <node> bash`). The first World 7 level creates a second, 3-node kind cluster (`k8squest-multinode`, about 30-60 seconds, and it uses additional memory while it runs); `./install.sh --multinode` creates it ahead of time. World 7 needs internet access at setup time for level 68 (metrics-server). **Linux hosts:** the game cluster (1 node) and the World 7 cluster (3 nodes) together need `fs.inotify.max_user_instances` of at least 512 (Ubuntu defaults to 128; below that pods fail with `too many open files`, for example `kube-proxy` in CrashLoopBackOff). Before it creates the World 7 cluster the game checks the value and, if it is too low, stops and prints the fix from the [kind known-issues page](https://kind.sigs.k8s.io/docs/user/known-issues/#pod-errors-due-to-too-many-open-files): `sudo sysctl fs.inotify.max_user_instances=512`, and to keep it, `echo 'fs.inotify.max_user_instances = 512' | sudo tee /etc/sysctl.d/90-kind-inotify.conf && sudo sysctl --system`. The check is skipped where `/proc/sys/fs/inotify/max_user_instances` does not exist (macOS, Docker Desktop)
- [Lima](https://lima-vm.io/docs/installation/) 2.0 or newer (only for World 8, Cluster lifecycle with kubeadm). World 8 does not use kind: the first World 8 level creates two Ubuntu 26.04 virtual machines with Lima (`k8squest-cp` and `k8squest-worker`) and the levels build a kubeadm cluster on them. They use **2 CPUs each and 5.5 GiB of RAM together** (3 GiB for the control plane, 2.5 GiB for the worker) and about 16 GiB of disk each, next to the kind clusters, so plan on a host with 16 GiB of RAM and 4 or more CPU cores (the game refuses to create the machines on a host with less than 8 GiB). It needs a host that can run hardware-accelerated virtual machines: **macOS** (Lima uses the system hypervisor; this path has not been run yet, only Linux with KVM has), or **Linux with KVM** (`/dev/kvm` present and writable by you, which usually means being in the `kvm` group, plus QEMU: `sudo apt install qemu-system qemu-utils` on Debian and Ubuntu). A Linux virtual machine needs nested virtualization turned on. Before it creates anything the game checks for all of this and says what is missing. World 8 needs internet access at setup time: packages from pkgs.k8s.io and Ubuntu, images from registry.k8s.io and ghcr.io, and the Flannel manifest from GitHub. The first level takes a few minutes while the machines install the Kubernetes packages; the machines are reused after that (the game refuses to touch a Lima machine of the same name that it did not create) and are not deleted when you leave the game (`limactl delete -f k8squest-cp k8squest-worker` removes them). World 8 does not run in the Docker image, because the machines are started from your host. Lima runs on macOS and Linux, not natively on Windows.
- helm 3.13 or newer (only for World 6, Cluster Architecture & Extensions; Helm 4 works too). World 6 needs internet access at setup time: its levels download and install cert-manager, Gateway API, Envoy Gateway, metrics-server and the VPA recommender into the kind cluster
- The Docker image built from the `Dockerfile` copies only `engine/` and `worlds/` and installs kubectl, and it has no `helm`, `docker` or `limactl`. World 6 (needs `helm`), World 7 (needs `docker`) and World 8 (needs `limactl`) therefore cannot run in it as built. It also has no kind or install script, so it needs a `KUBECONFIG` for an existing cluster

## Platform Support

K8sQuest works on **Linux, macOS, and Windows**!

- ✅ **Linux** - Native bash support
- ✅ **macOS** - Native bash support  
- ✅ **Windows** - Requires Git Bash (see Windows installation below)

## Installation

### Linux & macOS

Quick setup - just run:
```bash
./install.sh
```

### Windows Installation

K8sQuest supports Windows! Follow these steps:

#### Prerequisites

1. **Docker Desktop** - [Download](https://www.docker.com/products/docker-desktop/)
   - Install and enable WSL2 backend (recommended)
   - **Start Docker Desktop** before running K8sQuest

2. **Git for Windows** - [Download](https://git-scm.com/download/win)
   - ✅ Includes Git Bash (required!)
   - ✅ Includes essential Unix utilities
   - **Important:** Always use Git Bash, not PowerShell or CMD

3. **kubectl** - Choose one installation method:
   ```bash
   # Option 1: Using Chocolatey (in PowerShell as Admin)
   choco install kubernetes-cli
   
   # Option 2: Using Scoop
   scoop install kubectl
   
   # Option 3: Manual download
   # Visit: https://kubernetes.io/docs/tasks/tools/install-kubectl-windows/
   ```

4. **Kind** - Choose one installation method:
   ```bash
   # Option 1: Using Chocolatey (in PowerShell as Admin)
   choco install kind
   
   # Option 2: Using Scoop
   scoop install kind
   
   # Option 3: Using Go (if you have Go installed)
   go install sigs.k8s.io/kind@latest
   ```

5. **Python 3.9+**
   - **Recommended:** Microsoft Store (search "Python 3.11" or newer)
   - Or download from [python.org](https://www.python.org/downloads/windows/)

6. **jq** ( Required for advanced )
   ```bash
   # Option 1: Using Chocolatey
   choco install jq
   
   # Option 2: Using Scoop
   scoop install jq
   ```

#### Running on Windows

⚠️ **CRITICAL:** Always use **Git Bash**, not PowerShell or CMD!

```bash
# 1. Open Git Bash (not PowerShell/CMD!)
# 2. Clone the repository
git clone https://github.com/davidrusho/k8squest.git
cd k8squest

# 3. Run installation
./install.sh

# 4. Start playing
./play.sh
```

#### Windows Troubleshooting

**Issue:** `TypeError: 'type' object is not subscriptable` when running `./play.sh`
- **Cause:** Python 3.8 or older is being used. K8sQuest requires **Python 3.9+**
- **Solution (macOS):**
  ```bash
  brew install python@3.11
  ./install.sh
  ```
- **Solution (Linux):**
  ```bash
  sudo apt install python3.11
  sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
  ./install.sh
  ```
- **Solution (Windows):** Install Python 3.11+ from Microsoft Store or [python.org](https://www.python.org/downloads/windows/)

**Issue:** `bash: command not found`
- **Solution:** Make sure you're using Git Bash, not PowerShell or CMD

**Issue:** `docker: command not found`  
- **Solution:** Start Docker Desktop and wait until it's fully running

**Issue:** Scripts show `^M` errors  
- **Solution:** This is fixed by `.gitattributes`, but if you still see it:
  ```bash
  git config core.autocrlf input
  git rm --cached -r .
  git reset --hard
  ```
#### Alternative: WSL2

For the best experience on Windows, use Windows Subsystem for Linux:

```bash
# In PowerShell (as Administrator)
wsl --install -d Ubuntu

# Then restart your computer and use Ubuntu terminal for K8sQuest
```

This provides a native Linux environment and the smoothest experience.

## Quick Start
```bash
# One-time setup
./install.sh

# Start playing
./play.sh
```

## 🎮 How to Play

1. **Start the game** - Run `./play.sh` (keeps the game running)
2. **Read the mission briefing** - Understand what's broken  
3. **OPEN A NEW TERMINAL** ⚠️ - Keep the game running in the first terminal!
4. **Use kubectl to investigate** - Check pods, logs, and events in the NEW terminal
5. **Fix the issue** - Apply corrections using kubectl commands
6. **Return to game terminal** - Choose an action (check/validate/guide)
7. **Earn XP** - Complete missions to level up!

## 🎯 Available Commands During Play

- `check` - Monitor resource status in real-time (watch for changes!)
- `guide` - Show step-by-step solution walkthrough *(Coming soon - will be updated in future)*
- `hints` - Display progressive hints (unlocks more on each use)
- `solution` - View the solution.yaml file
- `validate` - Test if your solution works
- `skip` - Skip to the next level (no XP awarded)
- `quit` - Exit the game (progress is auto-saved)

## 🎓 Post-Mission Debriefs

After completing each mission, you'll get a detailed debrief explaining:
- ✅ What actually happened and why
- 🧠 The correct mental model for this concept
- 🚨 Real-world production incident examples
- 💼 Interview questions you can now answer
- 🔧 kubectl commands you mastered

**This is where the real learning happens!**

## 🔧 Reset Levels

Get stuck or want to retry? Reset any level from any world:
```bash
# First, activate the virtual environment
source venv/bin/activate

# Reset levels from any world
python3 engine/reset.py level-1-pods                # World 1
python3 engine/reset.py level-15-rollout            # World 2
python3 engine/reset.py level-28-endpoints          # World 3
python3 engine/reset.py level-38-volume-permissions # World 4
python3 engine/reset.py level-45-node-affinity      # World 5
python3 engine/reset.py level-55-httproute-parentref # World 6
python3 engine/reset.py level-63-scheduler-down      # World 7
python3 engine/reset.py level-73-join-worker         # World 8 (rebuilds the cluster on the Lima machines)
```

Or reset everything:
```bash
python3 engine/reset.py all
```

## 📚 Learning Path

### 🎯 World 1: Core Kubernetes Basics (Levels 1-10) 
**Difficulty**: Beginner | **Total XP**: 1,500  
Master the fundamentals of Kubernetes debugging and troubleshooting.

- ✅ Level 1: Fix the Crashing Pod (100 XP)
- ✅ Level 2: Fix the Deployment (150 XP)
- ✅ Level 3: ImagePullBackOff Mystery (100 XP)
- ✅ Level 4: Pending Pod Problem (150 XP)
- ✅ Level 5: Lost Connection - Labels & Selectors (150 XP)
- ✅ Level 6: Port Mismatch Mayhem (100 XP)
- ✅ Level 7: Sidecar Sabotage (200 XP)
- ✅ Level 8: Pod Logs Mystery (150 XP)
- ✅ Level 9: Init Container Gridlock (200 XP)
- ✅ Level 10: Namespace Confusion (200 XP)

### 🏆 World 2: Deployments & Scaling (Levels 11-20) 
**Difficulty**: Intermediate | **Total XP**: 2,050  
Master deployment strategies, scaling, and health checks.

- ✅ Rolling updates, rollbacks, HPA, liveness/readiness probes
- ✅ PodDisruptionBudgets, canary deployments, anti-affinity
- ✅ Resource management, pod lifecycle, and production patterns

### 🏆 World 3: Networking & Services (Levels 21-30) 
**Difficulty**: Intermediate | **Total XP**: 2,300  
Master service discovery, load balancing, and network policies.

- ✅ ClusterIP, NodePort, LoadBalancer services
- ✅ DNS resolution, Ingress controllers, NetworkPolicies
- ✅ Session affinity, cross-namespace communication, headless services

### 🏆 World 4: Storage & Stateful Apps (Levels 31-40) 
**Difficulty**: Advanced | **Total XP**: 2,450  
Master persistent storage, StatefulSets, and configuration management.

- ✅ PersistentVolumes, PVCs, access modes, StorageClasses
- ✅ StatefulSets, volume permissions, reclaim policies
- ✅ ConfigMaps, Secrets, and production storage patterns

### 🏆 World 5: Security & Production Ops (Levels 41-50) 
**Difficulty**: Advanced | **Total XP**: 3,300  
Production-ready Kubernetes: RBAC, security, resource management, and chaos engineering.

- ✅ RBAC (ServiceAccounts, Roles, RoleBindings)
- ✅ SecurityContext, Pod Security Standards (restricted)
- ✅ ResourceQuotas, NetworkPolicies, node scheduling
- ✅ Taints/Tolerations, PodDisruptionBudgets, PriorityClass
- ✅ **Level 50**: 🔥 **The Chaos Finale** - 9 simultaneous failures in a production scenario!

### 🏆 World 6: Cluster Architecture & Extensions (Levels 51-60) 
**Difficulty**: Intermediate → Expert | **Total XP**: 3,250  
Cluster extensions and the packaging, routing and certificate tooling around them. Needs `helm` on the host.

- ✅ Helm releases: revision history and rollback
- ✅ Kustomize bases and overlays, patch targets
- ✅ CustomResourceDefinitions and their OpenAPI schemas
- ✅ cert-manager Issuers and Certificates
- ✅ Gateway API: HTTPRoute, parentRefs, backendRefs, ReferenceGrant (Envoy Gateway)
- ✅ Vertical Pod Autoscaler targetRef
- ✅ ServiceAccount RoleBindings, and the RuntimeClass (CRI) and StorageClass (CSI) extension points
- ✅ **Level 60**: three independent faults across cert-manager, Gateway API and RBAC

### 🔧 World 7: Troubleshooting (Levels 61-70) 
**Difficulty**: Intermediate → Expert | **Total XP**: 3,150  
Faults in the cluster itself rather than in a workload, on a 3-node kind cluster (1 control plane, 2 workers). "SSH to the node" is `docker exec -it <node> bash`. Needs `docker` on the host.

- ✅ A NotReady worker: stopped kubelet, broken kubelet configuration, missing pod network (CNI)
- ✅ Control-plane components as static pods: kube-scheduler, kube-controller-manager, kube-apiserver (diagnosed with `crictl` when `kubectl` is down)
- ✅ CoreDNS: replicas and a wrong Corefile zone
- ✅ `kubectl top` and the metrics-server pipeline
- ✅ Container output: `kubectl logs -c ... --previous` in a multi-container pod
- ✅ **Level 70**: 🔥 an etcd snapshot with `etcdctl`/`etcdutl`, and a lost worker (cordon, drain and what drain cannot do on a dead node)
- Not in this world: etcd restore, kubeadm upgrades and HA control planes (all in World 8, except HA)

### 🏗️ World 8: Cluster lifecycle with kubeadm (Levels 71-76)
**Difficulty**: Intermediate → Expert | **Total XP**: 2,050  
Build and look after a real cluster, on two Lima virtual machines (Ubuntu 26.04, `k8squest-cp` and `k8squest-worker`) that share a network. "SSH to the node" is `limactl shell k8squest-cp`. Levels 71 and 72 start before the cluster exists, so kubectl has nothing to talk to until you run `kubeadm init`. Needs `limactl` on the host (see Requirements).

- ✅ **Level 71**: node prerequisites: swap, the `overlay` and `br_netfilter` modules, IP forwarding, containerd on the systemd cgroup driver, checked with `kubeadm init phase preflight`
- ✅ **Level 72**: `kubeadm init` and a pod network (Flannel), so the node turns Ready and CoreDNS starts
- ✅ **Level 73**: `kubeadm join` with a token and the CA certificate hash
- ✅ **Level 74**: a minor upgrade, v1.36.5 to v1.37.1, control plane then worker (`kubeadm upgrade plan`, `apply`, `node`)
- ✅ **Level 75**: an etcd snapshot, a deleted application, and a restore with `etcdutl snapshot restore`
- ✅ **Level 76**: 🔥 maintenance on a node: `kubectl drain` past DaemonSets, local storage and a PodDisruptionBudget, then `uncordon`
- Not in this world: HA control planes and certificate renewal. Only the Linux/KVM path has been run; the macOS path has not

Every World 8 `setup.sh` puts the machines into the state before its level from whatever state they are in (`kubeadm reset`, then the preparation it needs), so levels can be replayed or played out of order. Setup takes a few seconds for levels 71 and 72, and between about 30 seconds and a minute and a half for levels 73-76 (they build a cluster). The first level of a fresh install is slower, about a minute and a half, while the machines install the Kubernetes packages; level 74 is slower once, when it installs the older Kubernetes version. The scripted fix of level 74 (the upgrade itself) takes about five minutes.

**Today**: 8 worlds, 76 levels, 20,050 XP in total (summed from the `mission.yaml` files) | Beginner → Expert

New worlds are discovered from `worlds/<world>/world.yaml`, so the game picks them up as they land.

📖 **Full Blueprint**: See [docs/50-CHALLENGE-BLUEPRINT.md](docs/50-CHALLENGE-BLUEPRINT.md) for detailed descriptions of all 50 challenges.


## 🛠️ Manual Play (Advanced)

If you prefer the old-school bash script:
```bash
./engine/start_game.sh
```

## ⭐ Support the Project

If K8sQuest helped you learn Kubernetes, please consider:

- **⭐ Star this repo** - Help others discover this free resource!
- **🐦 Share** - Tell your teammates and friends about it
- **💬 Feedback** - Open an issue with suggestions or bugs
- **🤝 Contribute** - Add new levels or improve existing ones

Your support helps keep this project free and accessible to everyone learning Kubernetes! 

## 📖 Contributing

Want to add more missions? Check out [docs/contributing.md](docs/contributing.md)
