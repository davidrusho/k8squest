# Contributing to K8sQuest

## 🎯 Mission: Create Consistent, High-Quality Challenges

Welcome, contributor! This guide will help you create new K8sQuest challenges that are maintainable, consistent, and provide actual learning value.

**K8sQuest has 76 levels across 8 worlds today.** We welcome:
- Bug fixes and improvements to existing levels
- New bonus levels or alternative challenges
- Translations and localization
- Documentation improvements
- Engine enhancements

## 📁 Required File Structure (8 Files Per Level)

Every challenge MUST have this structure:

```
worlds/
  world-X-name/
    level-Y-name/
      ├── mission.yaml      # REQUIRED: Challenge metadata
      ├── broken.yaml       # REQUIRED: The broken K8s resources
      ├── solution.yaml     # REQUIRED: The fixed configuration
      ├── validate.sh       # REQUIRED: Pass/fail test script (must be executable)
      ├── hint-1.txt        # REQUIRED: Initial observation hint
      ├── hint-2.txt        # REQUIRED: Direction hint
      ├── hint-3.txt        # REQUIRED: Near-solution hint
      └── debrief.md        # REQUIRED: Post-completion learning guide
```

**All 8 files are mandatory.** This ensures consistency across all levels.

## 📋 File Requirements

### 1. mission.yaml

Metadata describing the challenge.

```yaml
level: 42
title: "SecurityContext Privilege Escalation"
description: "The web-app pod is failing security admission. Fix the SecurityContext to run as non-root."
difficulty: intermediate
xp_reward: 250
world: 5
estimated_time: "10-15 minutes"
concepts:
  - securitycontext
  - pod-security
  - non-root
learning_objectives:
  - Understand SecurityContext configuration
  - Configure runAsNonRoot and allowPrivilegeEscalation
  - Meet Pod Security Standards requirements
```

**Rules:**
- `level`: Sequential number across all worlds (1-76 today)
- `title`: Max 60 characters, clear and descriptive
- `xp_reward`: 100 (beginner), 150-250 (intermediate), 300-350 (advanced), 500 (expert finale)
- `difficulty`: beginner | intermediate | advanced | expert
- `estimated_time`: Realistic for target skill level
- `concepts`: 2-5 concepts, lowercase, hyphenated
- `learning_objectives`: 3-5 specific learning outcomes

### 2. broken.yaml

The intentionally broken Kubernetes resources that students must fix.

**Rules:**
- Must be valid YAML syntax
- Must deploy without syntax errors (broken behavior ≠ malformed YAML)
- Should demonstrate ONE specific misconfiguration
- Must use namespace `k8squest` for all namespaced resources
- Include comments explaining what's wrong (for educational value)
- Use realistic resource names and configurations

**Example:**
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: web-app
  namespace: k8squest
spec:
  containers:
  - name: web
    image: nginx:latest
    securityContext:
      runAsUser: 0  # ❌ Running as root - violates security policy
      allowPrivilegeEscalation: true  # ❌ Allows privilege escalation
```

### 3. solution.yaml

The corrected configuration that fixes the issue.

**Rules:**
- Must pass validation script
- Include comments explaining the fix
- Should represent best practices
- Must be a complete, working configuration

**Example:**
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: web-app
  namespace: k8squest
spec:
  securityContext:
    runAsNonRoot: true  # ✅ Require non-root user
    runAsUser: 1000     # ✅ Run as specific non-root user
    fsGroup: 2000
  containers:
  - name: web
    image: nginx:latest
    securityContext:
      allowPrivilegeEscalation: false  # ✅ Prevent privilege escalation
      capabilities:
        drop:
        - ALL  # ✅ Drop all capabilities
```

### 4. validate.sh

Bash script that returns 0 (success) or 1 (failure). Must be executable.

**Template for simple validation:**
```bash
#!/bin/bash

NAMESPACE="k8squest"
POD_NAME="web-app"

echo "🔍 Validating SecurityContext configuration..."

# Check if pod exists
if ! kubectl get pod $POD_NAME -n $NAMESPACE &>/dev/null; then
    echo "❌ Pod not found"
    exit 1
fi

# Check runAsNonRoot
RUN_AS_NON_ROOT=$(kubectl get pod $POD_NAME -n $NAMESPACE -o jsonpath='{.spec.containers[0].securityContext.runAsNonRoot}')
if [ "$RUN_AS_NON_ROOT" != "true" ]; then
    echo "❌ runAsNonRoot not set to true"
    exit 1
fi

# Check allowPrivilegeEscalation
ALLOW_PRIV=$(kubectl get pod $POD_NAME -n $NAMESPACE -o jsonpath='{.spec.containers[0].securityContext.allowPrivilegeEscalation}')
if [ "$ALLOW_PRIV" != "false" ]; then
    echo "❌ allowPrivilegeEscalation not set to false"
    exit 1
fi

echo "✅ SUCCESS! SecurityContext properly configured!"
exit 0
```

**Template for multi-stage validation:**
```bash
#!/bin/bash

NAMESPACE="k8squest"
ERRORS=0

echo "🔍 MULTI-STAGE VALIDATION"
echo ""

# Stage 1
echo "Stage 1: Checking pod exists..."
if ! kubectl get pod web-app -n $NAMESPACE &>/dev/null; then
    echo "❌ FAILED: Pod not found"
    ((ERRORS++))
else
    echo "✅ PASSED"
fi

# Stage 2
echo "Stage 2: Checking SecurityContext..."
# ... validation logic ...

# Final result
if [ $ERRORS -eq 0 ]; then
    echo "✅ ALL CHECKS PASSED!"
    exit 0
else
    echo "❌ $ERRORS check(s) failed"
    exit 1
fi
```

**Important:**
- Make executable: `chmod +x validate.sh`
- Use clear stage-by-stage output
- Provide helpful error messages
- Exit 0 for success, 1 for failure

### 5. debrief.md (MOST IMPORTANT!)

Post-completion learning guide - this is where real learning happens!

**Required Sections:**

1. **What You Just Fixed** - Clear explanation of the problem
2. **Why It Was Broken** - Root cause analysis
3. **The Solution** - Step-by-step breakdown of the fix
4. **Key Concepts** - Deep dive into the concepts
5. **Real-World Scenario** - Production incident example with costs/impact
6. **Best Practices** - Production recommendations
7. **Common Pitfalls** - What to avoid
8. **Verification Commands** - How to check your work
9. **Further Reading** - Official docs and resources

**Example Structure:**
```markdown
# Level 42 Debrief: SecurityContext Privilege Escalation

## What You Just Fixed

The web-app pod was being rejected by the Pod Security admission controller because it was configured to run as root with privilege escalation enabled.

## Why It Was Broken

The SecurityContext had:
- `runAsUser: 0` (root user)
- `allowPrivilegeEscalation: true`
- No capability restrictions

This violates the "restricted" Pod Security Standard.

## The Solution

Applied proper SecurityContext:
```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  allowPrivilegeEscalation: false
  capabilities:
    drop: [ALL]
```

## Key Concepts

### SecurityContext
Controls security settings for pods and containers...

## Real-World Scenario

**Incident**: Container escape in production (March 2023)
**Impact**: $5.4M in cryptomining charges
**Cause**: Pod running as root with privilege escalation
**Resolution**: Enforced restricted Pod Security Standard

[Continue with full debrief...]
```

**Aim for 2,000-5,000 words of comprehensive educational content.**

### 6-8. hint-{1,2,3}.txt

Progressive hints that unlock gradually. Each should build on the previous.

**hint-1.txt** - Initial observations and investigation commands:
```
💡 Hint 1: Initial Investigation

The pod is failing to start. Let's investigate:

1. Check pod status:
   kubectl get pod web-app -n k8squest
   
2. Look for events:
   kubectl describe pod web-app -n k8squest
   
3. Check for security-related errors in events

Look for admission controller rejection messages!
```

**hint-2.txt** - Point toward the solution area:
```
💡 Hint 2: Security Context

The pod is being rejected by the Pod Security admission controller.

The issue is in the SecurityContext configuration:
- Check runAsUser value
- Check allowPrivilegeEscalation setting
- Check capability restrictions

What values would meet the "restricted" security standard?
```

**hint-3.txt** - Near-complete solution:
```
💡 Hint 3: The Fix

You need to configure SecurityContext to:

1. Run as non-root:
   runAsNonRoot: true
   runAsUser: 1000

2. Prevent privilege escalation:
   allowPrivilegeEscalation: false

3. Drop all capabilities:
   capabilities:
     drop: [ALL]

Apply these in both pod-level and container-level securityContext!
```

**Progression:**
- Hint 1: "Where to look"
- Hint 2: "What to focus on"
- Hint 3: "How to fix it"

## 🌍 Defining a World (`world.yaml`)

Every world is a directory under `worlds/` containing a `world.yaml` and its `level-*` subdirectories. The engine finds worlds by globbing `worlds/*/world.yaml`, sorts them by `order`, and computes the level count and XP total from the `mission.yaml` files on disk. Nothing else lists worlds, so adding a world means adding a directory.

```yaml
order: 6                       # integer; play order; must be unique across worlds
title: "Cluster Architecture"  # shown as "World 6: Cluster Architecture"
description: "One sentence on what the world teaches."
cluster: kind                  # kind | kind-multinode | lima
requires: []                   # host tools levels may use, e.g. [helm, kustomize]
```

| Field | Type | Meaning |
|-------|------|---------|
| `order` | integer | Position in the game. Worlds are played in ascending order. |
| `title` | string | Short world name. |
| `description` | string | One-sentence summary. |
| `cluster` | `kind`, `kind-multinode` or `lima` | The kind of cluster the world's levels run on. |
| `requires` | list of strings | Host tools the world's levels may use (see below). Empty for kubectl-only worlds. |

Rules:
- Level directory names (`level-N-name`) must be unique across **all** worlds; discovery refuses to start otherwise. Level numbering continues across worlds (World 6 starts after the last level of World 5).
- `mission.yaml` `xp` values are summed for the total XP; don't hard-code totals anywhere.
- `utils/test-all-levels.sh` and `tests/test_discovery.py` check `world.yaml` and the 8 mandatory files for every level.
- A directory under `worlds/` whose name starts with `_` (`worlds/_shared`) holds helpers shared by several worlds. It has no `world.yaml`, so discovery ignores it, and the checks above skip it.
- `tools/create_level.sh <world-order> ...` looks up the world by its `order`.

### Multi-node worlds, `heal.sh` and `solution.sh`

- **Which cluster.** `cluster: kind` runs on the `k8squest` cluster (context `kind-k8squest`); `cluster: kind-multinode` runs on `k8squest-multinode` (1 control plane + 2 workers from `kind/multinode.yaml`, context `kind-k8squest-multinode`). The mapping lives in one place, `engine/level_reset.py` (`context_for`). Before a level starts the engine creates the multi-node cluster if it is missing (`kind create cluster --name k8squest-multinode --config kind/multinode.yaml --wait 180s`) and switches `kubectl` to the world's context; `./install.sh --multinode` creates it ahead of time. Nodes are Docker containers named `k8squest-multinode-control-plane`, `-worker` and `-worker2`.
- **Context in scripts.** The engine and the harness set `K8SQUEST_CONTEXT` for `setup.sh` and `validate.sh`. `require_game_context` (in `worlds/_shared/lib.sh`) refuses to run unless the current context is that one (default `kind-k8squest`).
- **Healthy baseline.** A level that breaks the cluster itself (nodes, control-plane manifests, DNS, CNI) must not leave the next level broken. World 7's `setup.sh` scripts call `heal_cluster` before they inject their fault, and `worlds/world-7-troubleshooting/heal.sh` runs the same function before the engine's own reset (the reset needs a working API server). Keep a pristine copy of every node file you edit under `/root/k8squest-pristine/` on the node, taken once from the healthy cluster, and restore from it.
- **`solution.sh`.** When the fix is a node-side or command action that `kubectl apply -f solution.yaml` cannot express, add an executable `solution.sh` next to `solution.yaml`. `tests/level_harness.py` runs it (cwd = the level directory, same environment as `setup.sh`) instead of applying `solution.yaml`. The engine never runs it and the player never sees it. `solution.yaml` stays the player-facing reference and may contain only comments. A level with neither an applicable `solution.yaml` nor a `solution.sh` is reported `MANUAL` by the harness.
- **Host limits.** Two kind clusters at once (`k8squest` with 1 node and `k8squest-multinode` with 3) need `fs.inotify.max_user_instances` >= 512 on Linux; at the default of 128 `kube-proxy` and other pods fail with `fsnotify watcher init: too many open files` ([kind known issue](https://kind.sigs.k8s.io/docs/user/known-issues/#pod-errors-due-to-too-many-open-files)). `ensure_world_cluster` checks this (`inotify_preflight` in `engine/level_reset.py`, file `INOTIFY_LIMIT_FILE`, skipped when the file is missing) before it creates the multinode cluster and refuses with the sysctl commands. The harness exits non-zero when any level is SKIPPED.
- **Reaching a node.** Use `docker exec -it <node> bash`, so the world declares `requires: [docker]`. kind nodes have `systemctl`, `journalctl` and `crictl`, but not `etcdctl`; run it with `kubectl -n kube-system exec etcd-<control-plane-node> -- etcdctl ...`.
- **A world on virtual machines (`cluster: lima`, World 8).** The engine creates two Lima machines from `lima/node.yaml` (`k8squest-cp`, `k8squest-worker`), after `lima_preflight` has checked that the host can run them, and the levels build the Kubernetes cluster themselves with kubeadm. The context `k8squest-lima` always exists; until a level has built a cluster it is a placeholder, and `world_has_api("lima")` is false, which makes the engine, `engine/reset.py` and the harness skip the namespace work. A level whose `broken.yaml` has nothing to apply (no cluster, no workload) keeps a comment-only `broken.yaml`. Each `setup.sh` must work from ANY state of the machines: start with `require_game_context` and `require_vms`, then `reset_nodes` (kubeadm reset and cleanup) and build only what that level needs; reuse the machines, never recreate them. Validators run kubectl on the control plane through `kc` (never rely on the player's kubeconfig), check real state rather than that a file exists, and record facts they need later with `remember` (for example the UID of a Deployment that has to survive). Pin every version in `worlds/world-8-cluster-lifecycle/_shared/lib.sh`. Keep Lima and kubeadm behaviour to what their documentation says.
- **A fault the API server cannot see.** `validate.sh` of a level that takes the API server down must use `kubectl --request-timeout=...` and bounded retries, and fail with a message instead of hanging.

## 🚫 What NOT to Do

❌ **Don't create multi-issue challenges** (except for special finale levels)
- Each level should teach ONE concept clearly
- Multiple issues confuse learners

❌ **Don't use a tool its world doesn't declare**
- A level may only use host tools listed in its world's `world.yaml` `requires`
- `kubectl` is always available and never needs listing; Worlds 1-5 declare `requires: []`, so their levels are kubectl-only; World 6 declares `requires: [helm]`; World 7 declares `requires: [docker]`; World 8 declares `requires: [limactl]` (Kustomize needs no extra tool: it is built into `kubectl kustomize` and `kubectl apply -k`)
- If a level needs `helm`, `kustomize`, `limactl` or similar, add it to the world's `requires` first, so the tool list for each world is visible in one place
- The engine does not check declared tools generally; `requires` is the contract contributors and reviewers hold levels to. The one exception is `cluster: lima`, whose `lima_preflight` checks for `limactl` (and KVM, QEMU and RAM on Linux) before it creates anything
- World 6 levels that need cluster-wide prerequisites (cert-manager, Gateway API + Envoy Gateway, metrics-server, the VPA recommender) install them from `worlds/world-6-cluster-architecture/_shared/lib.sh`, which pins every version in one place (metrics-server lives in `worlds/_shared/lib.sh`, shared with World 7). Each `ensure_*` helper is idempotent and waits for readiness. A level with a `setup.sh` must apply `broken.yaml` itself, because the engine skips it when `setup.sh` exists. `tests/level_harness.py` proves the break/fix cycle against a kind cluster. These installers are pinned by release tag, not by image or manifest digest, and no checksums are verified.
- Every engine level start also runs `engine/level_reset.py`'s `clear_leftovers`: after `kubectl delete all` it removes quotas, limit ranges, network policies, roles, role bindings, service accounts (except `default`), config maps (except `kube-root-ca.crt`), secrets and PVCs from the namespace, and the `dedicated` taint and `accelerator` label from nodes. A level must therefore create everything it relies on itself (in `broken.yaml` or `setup.sh`) rather than inherit it from an earlier level.
- World 6 `setup.sh` scripts call `require_game_context` (refuses unless the kubectl context is the world's own, `kind-k8squest` unless `K8SQUEST_CONTEXT` says otherwise; override with `K8SQUEST_ALLOW_CONTEXT=1`), label cluster-scoped objects they create with `app.kubernetes.io/part-of=k8squest`, and delete such objects only when the label and name both match. Delete policy: cluster-scoped objects the game owns are deleted only by label plus name. The documented exceptions are exact-name deletes, all of which run only behind `require_game_context`: ClusterIssuer `selfsigned-issuer` (level 54), namespace `k8squest-backend` (level 56), and RoleBindings / ClusterRoleBindings that name a level's ServiceAccount (levels 58 and 60). A ClusterRoleBinding that names other subjects besides the game ServiceAccount is skipped and reported, never deleted. The engine-side reset (`clear_leftovers`) keeps the install-time player RBAC (`k8squest-player` ServiceAccount, `k8squest-player-role`, `k8squest-player-binding`), reports any step that failed (the engine prints a yellow warning and carries on; the harness appends it to the level's note), and only edits node taints and labels when the kubectl context is `kind-k8squest`, `k3s-k8squest`, `kind-k8squest-multinode` or `k8squest-lima` (or `K8SQUEST_ALLOW_CONTEXT=1`). Files a player edits (levels 51-53) are copied to `${K8SQUEST_WORKDIR:-$HOME/.k8squest/work}/<level-name>/` on every start.

❌ **Don't use real secrets/credentials**
- Use obviously fake values: `password123`, `fake-token`
- Never commit real credentials

❌ **Don't break multiple namespaces**
- All resources in `k8squest` namespace only
- Don't affect system namespaces

❌ **Don't make it a guessing game**
- Provide clear error messages
- Validation should guide users
- Hints should actually help

❌ **Don't skip the debrief**
- This is the most important learning moment
- Include real-world examples and incidents
- Explain the "why" not just the "how"

❌ **Don't forget to test**
- Test on a fresh cluster
- Verify both broken and fixed states
- Check all 8 files are present

## ✅ Quality Checklist

Before submitting a new level, verify:

### Files
- [ ] All 8 required files present (mission.yaml, broken.yaml, solution.yaml, validate.sh, hint-1/2/3.txt, debrief.md)
- [ ] validate.sh is executable (`chmod +x validate.sh`)
- [ ] No extra or missing files

### Content Quality
- [ ] mission.yaml has all required fields
- [ ] broken.yaml uses valid YAML syntax
- [ ] broken.yaml demonstrates clear, single issue
- [ ] solution.yaml fixes the issue completely
- [ ] validate.sh passes with solution.yaml
- [ ] validate.sh fails with broken.yaml
- [ ] Hints progress logically (investigate → identify → fix)
- [ ] debrief.md has all required sections
- [ ] debrief.md includes real-world incident example
- [ ] debrief.md is 2,000-5,000 words

### Testing
- [ ] Tested on fresh kind cluster
- [ ] Applied broken.yaml - verifies it's broken
- [ ] Applied solution.yaml - verifies it works
- [ ] Ran validate.sh with both states
- [ ] Checked for helpful error messages
- [ ] Verified namespace isolation (k8squest only)

### Best Practices
- [ ] Single, clear learning objective
- [ ] Comments in YAML explaining issues
- [ ] Clear, beginner-friendly language
- [ ] Consistent with existing level patterns
- [ ] No external tool dependencies
- [ ] Appropriate difficulty and XP reward

## 🧪 Testing Your Challenge

### Step 1: Setup Fresh Environment
```bash
# Make sure you have a clean cluster
kind delete cluster --name k8squest
kind create cluster --name k8squest --config kind/cluster.yaml

# Create k8squest namespace
kubectl create namespace k8squest
```

### Step 2: Test Broken State
```bash
# Apply the broken configuration
kubectl apply -f worlds/world-X-name/level-Y-name/broken.yaml

# Verify it's actually broken
./worlds/world-X-name/level-Y-name/validate.sh
# Should exit with code 1 and show helpful error
```

### Step 3: Test Solution
```bash
# Apply the solution
kubectl apply -f worlds/world-X-name/level-Y-name/solution.yaml

# Verify it passes validation
./worlds/world-X-name/level-Y-name/validate.sh
# Should exit with code 0 and show success message
```

### Step 4: Test Hints
```bash
# Read through each hint
cat hint-1.txt
cat hint-2.txt
cat hint-3.txt

# Verify they progress logically
# Verify hint-3 leads clearly to solution
```

### Step 5: Review Debrief
```bash
# Check debrief content
cat debrief.md

# Verify:
# - All required sections present
# - Real-world incident included
# - Best practices documented
# - 2,000+ words of content
```

## 📚 Reference Examples

### Beginner Level Examples
- `worlds/world-1-basics/level-1-pods/` - CrashLoopBackOff
- `worlds/world-1-basics/level-2-deployments/` - Zero Replicas
- `worlds/world-1-basics/level-3-imagepull/` - ImagePullBackOff

### Intermediate Level Examples
- `worlds/world-2-deployments/level-13-readiness/` - Readiness Probes
- `worlds/world-3-networking/level-24-ingress/` - Ingress Configuration
- `worlds/world-4-storage/level-32-volume-mount/` - Volume Mounts

### Advanced Level Examples
- `worlds/world-5-security/level-41-rbac-permission/` - RBAC
- `worlds/world-5-security/level-44-networkpolicy/` - NetworkPolicy
- `worlds/world-5-security/level-48-pod-security/` - Pod Security Standards

### Expert Level Example
- `worlds/world-5-security/level-50-chaos-finale/` - Multi-concept finale

## 🎯 XP Reward Guidelines

Choose XP based on difficulty and learning value:

- **100 XP**: Simple beginner concepts (single field fix)
- **150-200 XP**: Intermediate single-concept (requires understanding)
- **250-300 XP**: Advanced concepts or multi-step fixes
- **350 XP**: Complex advanced concepts
- **500 XP**: Expert finale levels combining multiple concepts

## 🌍 World Structure

Levels are organized into worlds by theme. The list of worlds is the set of `worlds/*/world.yaml` files, ordered by their `order` field (see "Defining a World" above); read the `title` and `description` there rather than a copy of the list in this document. To see the current worlds and their level counts:

```bash
grep -H "^\(order\|title\):" worlds/*/world.yaml
python3 tools/progress_tracker.py
```

New levels should fit logically into an existing world or propose a new themed world by adding a `world.yaml`.

## 🤝 Submission Process

1. **Fork the repository**
2. **Create a new branch**: `git checkout -b level-51-your-feature`
3. **Create all 8 required files**
4. **Test thoroughly** using checklist above
5. **Make validate.sh executable**: `chmod +x validate.sh`
6. **Commit with clear message**: `git commit -m "Add Level 51: Your Feature Name"`
7. **Push to your fork**: `git push origin level-51-your-feature`
8. **Open Pull Request** with:
   - Clear description of the level
   - Why this concept is important
   - What makes it unique from existing levels
   - Screenshots/examples of broken and fixed states

## 💡 Tips for Great Levels

### Make It Real
- Base scenarios on actual production incidents
- Use realistic configurations
- Include cost/impact data in debriefs

### Keep It Focused
- One concept per level (except finales)
- Clear learning objective
- Direct path from broken → fixed

### Be Educational
- Explain the "why" not just "what"
- Include mental models in debriefs
- Show how to verify the fix
- Link to official documentation

### Test Everything
- Fresh cluster validation
- Both broken and fixed states
- All hints and validation messages
- Complete playthrough as a learner

## 📞 Questions?

- Check existing levels for patterns
- Review [ARCHITECTURE.md](ARCHITECTURE.md)
- Open an issue for discussion
- Join community discussions

**Thank you for contributing to K8sQuest!** 🚀
