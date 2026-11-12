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
- Starting a session runs `sudo -n /usr/local/sbin/cka-hosts-reset`, deletes every `exam-*` namespace plus the pool's cluster-scoped leftovers, then resets node state: removes the node labels `accelerator`, `gpu-type` and `disk` (t45's setup adds the first), removes taints with key `dedicated` and uncordons every node, so a solved state cannot carry into the next session. Other taints are never touched. Failures come back as warnings.
- Every kubectl the exam runs is pinned with `--context kind-k8squest`, and level scripts get a private temp kubeconfig holding only that context (0700 dir, 0600 file, removed at exit and on SIGTERM/SIGHUP, never printed), so a context switch by the game engine cannot redirect the exam. `hosts/cka-hosts-reset` is a revised copy of the deployed host-reset script that gives cka1 to cka3 the same pinned, minified kubeconfig; deploy it to `/usr/local/sbin/` by hand. It also gives the exam hosts the kubeadm practice cluster: `/etc/hosts` lines for `controlplane` (192.168.1.226) and `node01` (192.168.1.227), an ssh client config for cka1 to cka3 (user `candidate`, their own key `~/.ssh/id_cka_nodes`, pinned host keys), and a second kubeconfig context `cluster1` with `kind-k8squest` still current; their `~/.ssh/known_hosts` and `config` are removed and `authorized_keys` is never touched. If `/etc/cka-hosts` is incomplete, or a kubeadm step fails, it warns on stderr and carries on with the kind cluster only; those warnings are not shown in the exam UI (`server.py` shows stderr only on a non-zero exit), so run `hosts/check-cka-hosts` to confirm the setup. `hosts/cka-nodes-provision` (run once as root on k8s-lab, re-run after a VM rebuild) creates that directory: one key pair per cka user, the `candidate` user and `authorized_keys` on both VMs, the cross-checked host keys and a copy of the cluster admin kubeconfig. After a VM rebuild, refresh david's known_hosts for the VM first (ssh there once as david and verify the key), because provision refuses a host key david does not already trust. `hosts/check-cka-hosts` verifies ssh, contexts and nodes for all three users, breaks cka1 on purpose, runs the reset and verifies again. The VM-side `candidate` user and `authorized_keys` are not in the snapshot `k8s-1-36-clean` until it is retaken (T-615.25).
- `pool.py` admits a task only when `e2e-status.json` records OK for it; a missing or corrupt file stops the server with an error. Ending a session keeps the namespaces until the next start.

## Drill mode

An untimed mode next to the mock exam, for working one task at a time with a hint ladder. The header has a `Drill | Mock exam` switch (last choice kept in `localStorage`). Mock exam mode is the screens described above, unchanged.

- Picker: the pool grouped by domain (heaviest exam weight first), with `x of y solved` per domain, the filters All / Not solved / Failed in an exam, and a badge per task (`not tried`, `opened`, `solved`, `failed in exam`). Row titles are the first sentence of the task's exam text with the namespace phrase removed (`pool.drill_title`); mission.yaml's name and description are never used because they name the cause. "Failed in an exam" means results.json holds attempts for the task and none counted; results.json is only read.
- Task view: client-side elapsed time (no server timing), Check (verdicts are just `Passed.` / `Not passed yet.`), then Stuck?: Hint 1, Hint 2, Hint 3, Show solution, each enabled only after the previous one; revealed hints stay on screen. After a pass or after Show solution the level's `debrief.md` appears in a collapsible section. Reset task rebuilds the broken state. The checker's output is gated behind the ladder: the level validators print what is wrong and often how to fix it, so while `hints_revealed` is 0 a failed check answers `Not passed yet.` with the output withheld (`output_withheld`, and `last_output` is null in every payload) and the UI says to press Hint 3 (the validators print "how to fix" blocks, which are solution-level). From Hint 3 on, or after a pass, the full output (ANSI stripped, capped) is shown.
- Namespace `drill-<taskid>`; cluster-scoped renames get `drill-tNN-` instead of `exam-tNN-` (`pool.renames_for`, `pool.cluster_objects_for`), so drill and exam objects never share names. Hint, solution and debrief text come from the level directory (`hint-1..3.txt`, `solution.yaml`, `debrief.md`) with the same rewrite applied (`levels.level_texts`); a missing file shows a placeholder. Only tasks in the e2e-proven pool are drillable.
- State: `drill.json` next to `results.json` (`CKA_EXAM_DATA` applies). Namespaces and cluster objects of the same task's exam run are deleted before every drill deploy (t22's node port and t30's ClusterIP are cluster-global), and the node state is reset before every drill deploy (see Node tasks below). Per task: `opened`, `deployed`, `attempts`, `solved`, `solved_at`, `hints_revealed` (0 to 4), `last_output`, `last_passed`, plus top-level `node_epoch` and `node_owner`. Nothing in it feeds exam selection or scoring.
- Endpoints (same Host/Origin/JSON rules as the exam API): `GET /api/drill/state`; `POST /api/drill/open {id}` (deploys the broken state if not deployed, returns host/ssh/body plus whatever is revealed); `POST /api/drill/check {id}`; `POST /api/drill/hint {id, n}` (n 1 to 3 hints, 4 the solution; `n > hints_revealed + 1` is a 409; returns every revealed text); `POST /api/drill/reset {id}` (deletes the drill namespace and the task's drill-prefixed cluster objects, redeploys, keeps attempts, solved and hints).
- The lock: every drill POST answers 409 while an exam session is live, enforced in the server (`Drill.guard`, also while a session start is sweeping namespaces); the UI disables Drill with a lock icon and forces Mock exam mode. A check or deploy that was running when the exam started is discarded. `e2e.py --kind drill --tasks t22,t30,t45` proves tasks under `drill-` names and does not write `e2e-status.json` (the one exception is a run whose every selected task is a question task, with `--write-status`). Starting an exam session first waits (up to 120 s) for in-flight drill operations and refuses with a 409 ("A drill task is still being prepared", or "A kubeadm cluster reset is in progress..." for a kubeadm task) if one is still running; otherwise it deletes every `drill-*` namespace and the drill-prefixed cluster objects, and clears the `deployed` flags, so a drill's solved state cannot carry into the exam.
- Question tasks: a second task source for Drill. Short kubectl questions from the drill page, each turned into a real-cluster task (ids `c01`, `c02`, ..., namespace `drill-c01`; defined in `pool.QUESTION_TASKS` with `Q(...)`). Each lives in `exam/questions/<qid>/` (qid is the drill-page id, e.g. `services-1`) with `broken.yaml` (starting state, `k8squest` namespace token), `validate.sh` (same contract as a level's), `solution.sh` (the answer as commands, used by e2e only), `hint-1.txt` (docs page title and URL), `hint-2.txt` (Ctrl+F term), `hint-3.txt` (command pattern) and `debrief.md`. They are drill-only: never in the exam pool or selection. A question task enters Drill once `e2e-status.json` has verdict OK for its id; prove one on the VM with `python3 exam/e2e.py --kind drill --tasks c01 --write-status` (`--write-status` under `--kind drill` is accepted only when every selected task is a question task; `--kind exam` refuses them). The picker has a "By domain | By pattern" switch (choice kept in `localStorage`); patterns come from `pool.PATTERNS`.
- Node tasks: the cluster has one node, shared with the K8sQuest game, and a node label, taint or cordon affects every namespace. The node has one owner at a time: `drill.json` holds `node_epoch` (bumped by every node reset) and `node_owner` (the node-dependent task whose setup the node currently holds, null when the node is clean, or `?` while a reset or setup is running or after one failed, meaning "may be dirty"). Drill calls `levels.reset_node_state` before every drill deploy (labels `accelerator`, `gpu-type`, `disk`; taints with key `dedicated`; uncordon), which also clears K8sQuest level 45's `accelerator` label and level 46's `dedicated` taint. A task flagged `node_dependent` in pool.py (its setup or grading depends on node state: t45, c74, c90 to c97) records the epoch at its deploy and becomes the owner. Leaving a node task undoes its node changes: opening or checking any other task while the owner is another task or `?` resets the node first. Reopening a node task whose setup was wiped rebuilds it (attempts and hints are kept) and says so in the `notice` field. Check on a node task refuses with 409 when it is not the owner or its epoch is stale, without running the validator and without counting an attempt: "The node no longer holds this task's setup. Press Reset task, then redo it." After a pass, or after the solution is shown while the task owns the node, Drill resets the node again and says "Node changes from this task were undone." in `notice`; reset warnings (a failed uncordon, for example) also come back in `notice`. Every node-touching sequence runs under one lock and holds `busy`, so an exam start waits for it. An exam start marks the owner `?` before its node reset and clears it after a clean reset. Checks run one at a time, because every check holds the node lock. Closing the browser while a node task is open leaves its node changes in place until the next drill action or exam start. The task text names the node `k8squest-control-plane` literally. Draining is not offered: on one node it would evict CoreDNS and every workload.
- Kubeadm tasks: a third task kind for Drill, run on the real two-VM kubeadm cluster (controlplane 192.168.1.226, Proxmox VM 111; node01 192.168.1.227, VM 112) instead of kind. They are question tasks marked `cluster="kubeadm"` in `pool.QUESTION_TASKS` (first one: `c100`, drill-page question `etcd-3`), drill-only and never in the exam pool. Task text says which node to `ssh` to from cka1 to cka3 (user `candidate`, sudo allowed). No namespace and no `broken.yaml`; the directory `exam/questions/<qid>/` holds `setup.sh` (optional; runs as root on controlplane, or on node01 when its first line is `# node: node01`), `validate.sh` (runs on k8s-lab as david and reaches the VMs with `sudo -n /usr/local/sbin/cka-kubeadm run-on --timeout 150 <node>`; same exit-code contract as every validator), `solution.sh` (e2e only, run like `setup.sh`), `hint-1..3.txt` and `debrief.md`. Ownership works like the node: `drill.json` holds `kubeadm_epoch` (bumped by every rollback) and `kubeadm_owner` (the kubeadm task whose setup the cluster holds, null at the start, or `?` while a rollback or setup is running, after a failure, after a pass, or after the solution was shown). Opening a task the cluster does not hold, or pressing Reset task, rolls both VMs back to the disk-only snapshot `k8s-1-36-clean`, starts them, waits until both nodes are Ready, applies `setup.sh` and makes the task the owner; the response `notice` says "Rolled the kubeadm cluster back to a clean snapshot (took Ns)." Reopening a task the cluster still holds does no rollback and only runs `ensure-up` (starts a stopped VM). Check refuses with 409 when the task is not the owner or its epoch is stale ("The kubeadm cluster no longer holds this task's setup. Press Reset task, then redo it."), without running the validator or counting an attempt. After a pass, or after Show solution on the owner, the cluster is only marked dirty: the rollback takes minutes, so the next kubeadm open does it, even for the same task. The rollback holds `busy`, so an exam start waits for it up to 120 s and otherwise gets the usual 409 ("A drill task is still being prepared"); an exam start during a rollback also aborts that open before its setup runs and leaves the owner `?`. An exam start marks the kubeadm cluster `?` (no rollback; the next kubeadm open rolls back), because an exam candidate can reach it too. The UI shows "Preparing the kubeadm cluster (a reset takes a few minutes)..." while an open is pending and "Resetting the kubeadm cluster, this takes a few minutes..." while a reset is. Expect 1 to 4 minutes for a rollback.
  - The helper `hosts/cka-kubeadm` (python3 standard library, run as root) is the only code that talks to Proxmox and the VMs: `ensure-up`, `rollback`, `run-on <controlplane|node01>` (script on stdin, run as root over `sudo -u david ssh ... sudo bash -s`) and `generation`. There is no kubectl subcommand: a validator that needs a cluster read goes through `run-on controlplane` and calls `kubectl --kubeconfig /etc/kubernetes/admin.conf ...` on the node. `rollback` and `ensure-up` hold a root flock (`/run/cka-kubeadm.lock`) so two callers never interleave (they wait up to 420 s for it); `run-on` waits at most 60 s. The generation is a random token in `/var/lib/cka-kubeadm/generation`, replaced atomically at the START of every rollback attempt, even one that fails (`rollback` prints `GENERATION=<token>` on success); Drill takes it from that stdout line, stores it with the owner, and a mismatch (an e2e run or another caller rolled the VMs back) makes the task stale: open rebuilds it, check refuses with 409. `run-on` gives up after 240 s of running (`--timeout N`); ssh uses ConnectTimeout 10 and keepalives. The server's timeouts exceed the helper's worst case: 900 s for rollback and ensure-up (420 lock wait + 420 run), 330 s for setup and solution (60 + 240), 240 s for a validator (60 + the 150 s its run-on asks for). It waits at most 420 s, polling every 5 s, until both VMs run, ssh works and both nodes are Ready, and prints one progress line per phase on stderr. Exit codes: 0 ok, 1 failure, 2 usage. Deploy it by hand on k8s-lab: `sudo install -m 755 exam/hosts/cka-kubeadm /usr/local/sbin/cka-kubeadm`; david's existing passwordless sudo covers it, so `sudo -n` from `server.py` works without a sudoers change. Tests drive it with fakes for Proxmox, ssh and the clock.
  - The Proxmox API token lives on k8s-lab in `/etc/cka-hosts/pve-token` (root, mode 0600, one line holding the full `Authorization` header value `PVEAPIToken=user!id=secret`). The server certificate is verified against the Proxmox root CA in `/etc/cka-hosts/pve-ca.pem` (a copy of `/etc/pve/pve-root-ca.pem` from prox, root-readable); the helper refuses to connect if that file is missing and never falls back to unverified TLS. The hostname check is off, because the node certificate's SANs do not include 192.168.1.217, so the pinned thing is the chain to that one private CA. The token is read into a request header only (a token file that is not one line `PVEAPIToken=<no spaces>` is refused as malformed; errors name only the exception type; the helper's messages are redacted for `PVEAPIToken=` before they reach the browser; redirects are never followed), never put in argv or in a child's environment, never printed; errors show the HTTP status and the PVE message. It has only VM.Audit, VM.PowerMgmt and VM.Snapshot.Rollback on `/vms/111` and `/vms/112`. The API endpoints used (`GET /cluster/resources?type=vm`, `GET .../qemu/{vmid}/status/current`, `POST .../status/start`, `POST .../snapshot/{snapname}/rollback`, `GET /nodes/{node}/tasks/{upid}/status`) were checked against the PVE API viewer.
  - Prove it with `python3 exam/e2e.py --kind drill --tasks c100 --write-status`: rollback, setup, the validator must fail, solution, the validator must pass. It shares the cluster with Drill and does not update `drill.json`, so run it while no kubeadm task is open, or press Reset task afterwards.
  - Expiry: the cluster certificates and the Proxmox token expire on 2027-11-11. Before then run `kubeadm certs renew all` on controlplane, take a fresh snapshot (replace `k8s-1-36-clean`), and issue a new token.

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
