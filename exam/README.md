# CKA exam-style practice mode for K8sQuest

Everything for the practice exam lives in this directory. No existing level, `engine/` or `play.sh` is modified; levels are reused by copying them to a temp directory and rewriting the namespace there.

## Run

On the machine that runs the kind cluster, as the user whose kubeconfig holds `kind-k8squest`:

    ~/k8squest/exam/run.sh        # foreground, http://127.0.0.1:6081/, Ctrl-C stops it

From your workstation, tunnel both ports and open the UI:

    ssh -L 6081:127.0.0.1:6081 -L 6080:127.0.0.1:6080 <user>@<vm-address>
    http://localhost:6081/        (the Remote Desktop tab embeds http://localhost:6080/vnc.html)

Python 3 standard library only. Results persist in `~/.local/share/cka-exam/results.json` (every attempt: session, elapsed seconds, passed, in_time); the live session in `session.json` next to it. Override the directory with `CKA_EXAM_DATA`. No systemd unit is installed.

Tests: `cd exam && python3 -m unittest discover -s tests -t .`. They make no cluster calls: `tests/_path.py` replaces `subprocess.run` and `Popen` with a guard that refuses and records any real subprocess, and `tests/test_zzz_no_subprocess.py` fails the run if one was attempted.

Tunnel to a different local port: the server accepts an `Origin` only from `http://localhost:<port>` and `http://127.0.0.1:<port>` of the port it is bound to (6081). If you reach it through a tunnel with another local port, start it with `EXAM_EXTRA_ORIGINS=http://localhost:16081` (comma separated list).

Live proof of every pool task: `python3 exam/e2e.py --write-status` (deploys the broken state, validator must fail, applies the level's solution, validator must pass; failing tasks are written to `e2e-status.json` and dropped from the pool).

## How it works

- `levels.py` copies a level (with `worlds/_shared`) to a temp tree, rewrites the whole-token `k8squest` to `exam-<taskid>` (and per-task `renames` for cluster-scoped names), deploys it as `engine/level_reset.py deploy_level` does (fresh namespace, `setup.sh` if present, else `broken.yaml`), and runs the rewritten `validate.sh`.
- `timing.py`: per-task clock, budget 120/16 = 450 s. A clock runs only while its task is shown and the page is visible; elapsed time is computed on the server from show/hide/heartbeat events (a silent UI is capped at last heartbeat + 30 s). A pass at 450 s or less counts; later is recorded as passed over time and does not count.
- `selection.py`: 16 tasks, largest-remainder split by domain weight, capped by domain size with the surplus re-split. "Missed first" takes never-counted tasks first and only then fills from tasks that have counted.
- `session.py`, `store.py`, `server.py`: session state, JSON persistence, HTTP API (POST requires `Content-Type: application/json`; Host and Origin must be localhost).
- Starting a session runs `sudo -n /usr/local/sbin/cka-hosts-reset`, deletes every `exam-*` namespace plus the pool's cluster-scoped leftovers, then resets node state: removes the node labels `accelerator` and `gpu-type` (t45's setup adds the first) and uncordons every node, so a solved state cannot carry into the next session. Taints are never touched. Failures come back as warnings.
- Every kubectl the exam runs is pinned with `--context kind-k8squest`, and level scripts get a private temp kubeconfig holding only that context (0700 dir, 0600 file, removed at exit and on SIGTERM/SIGHUP, never printed), so a context switch by the game engine cannot redirect the exam. `hosts/cka-hosts-reset` is a revised copy of the deployed host-reset script that gives cka1 to cka3 the same pinned, minified kubeconfig; deploy it to `/usr/local/sbin/` by hand.
- `pool.py` admits a task only when `e2e-status.json` records OK for it; a missing or corrupt file stops the server with an error. Ending a session keeps the namespaces until the next start.

## Curriculum source (domains and weights)

Source: https://github.com/cncf/curriculum (README: "This is the latest version of the curriculum for the following CNCF exams: * Certified Kubernetes Administrator (CKA) ..."), which links `CKA_Curriculum_v1.37.pdf`: https://raw.githubusercontent.com/cncf/curriculum/master/CKA_Curriculum_v1.37.pdf . Quotes from the PDF (page 2, "CKA Curriculum"):

- "10% - Storage"
- "15% - Workloads and Scheduling"
- "20% - Servicing and Networking"
- "30% - Troubleshooting"
- "25% - Cluster Architecture, Installation and Configuration"

## Pool (47 tasks, all proven live)

| Domain | Weight | Tasks |
|---|---|---|
| Storage | 10% | 8 |
| Workloads and Scheduling | 15% | 17 |
| Servicing and Networking | 20% | 9 |
| Troubleshooting | 30% | 11 |
| Cluster Architecture, Installation and Configuration | 25% | 2 |

Cluster Architecture is thin: the reusable levels cover RBAC only (t41, t58). Weighted selection therefore takes at most 2 tasks from it and re-splits the other slots, so it is under-represented against its 25%.

| Task | Level | Domain |
|---|---|---|
| t01 | level-1-pods | Troubleshooting |
| t03 | level-3-imagepull | Troubleshooting |
| t04 | level-4-pending | Troubleshooting |
| t05 | level-5-labels | Troubleshooting |
| t06 | level-6-ports | Troubleshooting |
| t07 | level-7-multicontainer | Troubleshooting |
| t08 | level-8-logs | Troubleshooting |
| t09 | level-9-initcontainer | Troubleshooting |
| t12 | level-12-liveness | Troubleshooting |
| t21 | level-21-service-selector | Troubleshooting |
| t28 | level-28-endpoints | Troubleshooting |
| t02 | level-2-deployments | Workloads and Scheduling |
| t11 | level-11-rollback | Workloads and Scheduling |
| t13 | level-13-readiness | Workloads and Scheduling |
| t15 | level-15-rollout | Workloads and Scheduling |
| t16 | level-16-pdb | Workloads and Scheduling |
| t17 | level-17-bluegreen | Workloads and Scheduling |
| t18 | level-18-canary | Workloads and Scheduling |
| t19 | level-19-statefulset | Workloads and Scheduling |
| t20 | level-20-replicaset | Workloads and Scheduling |
| t36 | level-36-configmap-key | Workloads and Scheduling |
| t37 | level-37-secret-encoding | Workloads and Scheduling |
| t42 | level-42-securitycontext | Workloads and Scheduling |
| t43 | level-43-resourcequota | Workloads and Scheduling |
| t45 | level-45-node-affinity | Workloads and Scheduling |
| t47 | level-47-poddisruptionbudget | Workloads and Scheduling |
| t48 | level-48-pod-security | Workloads and Scheduling |
| t49 | level-49-priorityclass | Workloads and Scheduling |
| t22 | level-22-nodeport | Servicing and Networking |
| t23 | level-23-dns | Servicing and Networking |
| t24 | level-24-ingress | Servicing and Networking |
| t25 | level-25-networkpolicy | Servicing and Networking |
| t26 | level-26-sessionaffinity | Servicing and Networking |
| t27 | level-27-crossnamespace | Servicing and Networking |
| t29 | level-29-loadbalancer | Servicing and Networking |
| t30 | level-30-headless | Servicing and Networking |
| t44 | level-44-networkpolicy | Servicing and Networking |
| t31 | level-31-pvc-pending | Storage |
| t32 | level-32-volume-mount | Storage |
| t33 | level-33-access-mode | Storage |
| t34 | level-34-statefulset-volumes | Storage |
| t35 | level-35-storageclass | Storage |
| t38 | level-38-volume-permissions | Storage |
| t39 | level-39-reclaim-policy | Storage |
| t40 | level-40-emptydir-vs-pvc | Storage |
| t41 | level-41-rbac-permission | Cluster Architecture |
| t58 | level-58-serviceaccount-rbac | Cluster Architecture |

## Excluded levels (levels 1 to 76)

| Level(s) | Reason |
|---|---|
| 10 | `broken.yaml` hard-codes namespace `default`, outside the task namespace |
| 14 | Installs metrics-server into `kube-system`, shared cluster state |
| 46, 50 | Taint the only node `dedicated=gpu:NoSchedule`; every other task's Pods would stop scheduling |
| 51, 52, 53 | Players edit a working copy under `$HOME/.k8squest/work` on the game host; the `cka` users cannot reach it (51 also needs Helm releases) |
| 54, 55, 56, 57, 60 | `setup.sh` installs cert-manager, Gateway API CRDs / controller or VPA cluster-wide |
| 59 | Creates cluster-scoped RuntimeClass and StorageClass with fixed names |
| 61 to 70 | World 7 runs on the separate 3-node `kind-multinode` cluster and breaks kubelet, scheduler, API server and CNI |
| 71 to 76 | World 8 builds kubeadm clusters on Lima VMs (node prep, init, join, upgrade, etcd restore, drain) |

That is 29 of the 76 levels excluded (4 + 3 + 5 + 1 + 10 + 6), leaving 47 pool candidates. Level 45 is kept: its `setup.sh` only adds the label `accelerator=gpu` to the node; the label is removed at the next session start.

Shared-state notes: t22 uses node port 30080 and t30 a fixed ClusterIP (10.96.100.50); both clash only if the same level is live in the game's `k8squest` namespace at the same time. PVs, the PriorityClass, the StorageClass and the second namespace of t27 are renamed with an `exam-tNN-` prefix, so the game's own objects of the same names are never touched.

## Live proof

`python3 exam/e2e.py --write-status` was run on the VM: all 47 pool tasks show fail on the broken state, then pass after the level's solution (`e2e-status.json`). Two proof-harness notes: t20's solution needs the standalone ReplicaSet deleted (`solution_extra` in `pool.py`); t27's solution replaces the Pods through `kubectl replace --force`. Re-run the command after changing any level or the rewrite rules; a task that fails is dropped from the pool automatically.
