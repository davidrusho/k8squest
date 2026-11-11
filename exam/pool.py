"""The task pool: K8sQuest levels re-worded as CKA exam tasks.

Each task:
  id            stable id, t<level number>; its namespace is exam-<id> (e.g. exam-t11)
  level         path under worlds/ of the K8sQuest level whose broken state and validator it reuses
  domain        CKA curriculum domain (selection.DOMAIN_WEIGHTS)
  text          the task wording; {ns} is the task namespace, plus any rename below by its new name
  renames       old -> new names (cluster-scoped objects, a second namespace) rewritten in the level
  node_reset    True when the level's setup changes node state (labels): Drill resets it before deploying
  cluster_objects  kubectl "kind/name" objects outside the namespace that the task may leave behind

The wording states every condition the level's validate.sh checks and none it does not.
A task is admitted to the pool only when e2e-status.json records a passing live proof (exam/e2e.py) for it.
A missing or corrupt status file is an error, not "admit everything".
"""
import json
import os
import re
from pathlib import Path

from selection import DOMAIN_WEIGHTS

ST, WL, NET, TS, CA = list(DOMAIN_WEIGHTS)
HERE = Path(__file__).resolve().parent
W1, W2, W3, W4, W5, W6 = ("world-1-basics", "world-2-deployments", "world-3-networking",
                          "world-4-storage", "world-5-security", "world-6-cluster-architecture")


def T(id, level, domain, text, renames=None, cluster_objects=(), solution_extra=(), node_reset=False):
    # solution_extra: kubectl argument lists the e2e proof runs before the level's solution.yaml
    return {"id": id, "level": level, "domain": domain, "text": text.strip(),
            "renames": renames or {}, "cluster_objects": list(cluster_objects),
            "solution_extra": [list(c) for c in solution_extra],
            "node_reset": node_reset}


ALL_TASKS = [
    # ---------------------------------------------------------------- Troubleshooting (30%)
    T("t01", f"{W1}/level-1-pods", TS, """
In namespace {ns}, Pod `nginx-broken` does not start.

Fix it so that the Pod is Running and its container is Ready. The container's command must not be `nginxzz`.
"""),
    T("t03", f"{W1}/level-3-imagepull", TS, """
In namespace {ns}, Pod `web-app` does not start.

Fix it so that the Pod is Running and its container is Ready.
"""),
    T("t04", f"{W1}/level-4-pending", TS, """
In namespace {ns}, Pod `hungry-app` stays in Pending.

Fix it so that the Pod is Running and its container is Ready.
"""),
    T("t05", f"{W1}/level-5-labels", TS, """
In namespace {ns}, Service `backend-service` has no endpoints, although Pod `backend-app` is running.

Fix the problem so that the Pod is Running and Ready and `backend-service` has at least one endpoint address.
"""),
    T("t06", f"{W1}/level-6-ports", TS, """
In namespace {ns}, requests to Service `web-service` never reach Pod `web-server`.

Fix the problem so that the Pod is Running and Ready, `web-service` has at least one endpoint address, and the first port of the Service has targetPort 80.
"""),
    T("t07", f"{W1}/level-7-multicontainer", TS, """
In namespace {ns}, Pod `app-with-logging` has two containers, `main-app` and `log-sidecar`. The Pod does not stay healthy.

Fix it so that the Pod is Running and both of its containers are Ready.
"""),
    T("t08", f"{W1}/level-8-logs", TS, """
In namespace {ns}, Pod `database-app` keeps failing. Use the container's logs to find out why.

Fix it so that the Pod is Running and Ready with a restart count of 0, and the environment variable `POSTGRES_PASSWORD` is set for its container (directly, or from a ConfigMap or Secret through `envFrom`).
"""),
    T("t09", f"{W1}/level-9-initcontainer", TS, """
In namespace {ns}, Pod `web-with-init` is stuck while its init container runs.

Fix it so that the Pod is Running and Ready, and its first init container has terminated with exit code 0.
"""),
    T("t12", f"{W2}/level-12-liveness", TS, """
In namespace {ns}, Deployment `api-server` has two replicas whose containers keep restarting.

Fix it so that the Deployment's rollout is complete (every replica updated and Ready, two Pods Running) and the Pods have restarted fewer than 3 times in total. The container must keep a liveness probe with an `httpGet` path that returns a success status code.
"""),
    T("t21", f"{W3}/level-21-service-selector", TS, """
In namespace {ns}, Service `backend-service` does not route traffic to Pod `backend-pod`.

Fix it so that the Service has at least one endpoint address and an HTTP request to `http://backend-service` from Pod `test-client` returns status 200.
"""),
    T("t28", f"{W3}/level-28-endpoints", TS, """
In namespace {ns}, Service `web-service` selects Pods `web-app-1` and `web-app-2`. Traffic can reach a Pod before the application in it is ready.

Fix it so that the first container of every `web-app` Pod has a readiness probe (httpGet, tcpSocket or exec), both Pods are Running and Ready (1/1), and the Service's endpoint addresses are exactly the Ready Pods.
"""),

    # ---------------------------------------------------------------- Workloads and Scheduling (15%)
    T("t02", f"{W1}/level-2-deployments", WL, """
In namespace {ns}, Deployment `web` has no running Pods.

Fix it so that at least one replica of the Deployment is Ready.
"""),
    T("t11", f"{W2}/level-11-rollback", WL, """
In namespace {ns}, Deployment `web-app` was just updated to an image that cannot be pulled.

Recover the Deployment so that it has 2 replicas, all updated, Ready and available, the rollout is complete, and the container image no longer contains the word `nonexistent`.
"""),
    T("t13", f"{W2}/level-13-readiness", WL, """
In namespace {ns}, Deployment `slow-startup-app` has 3 replicas. The application needs about 20 seconds to start, but Pods are considered ready immediately.

Add a readiness probe to the container, and make sure the rollout is complete: every replica updated and Ready.
"""),
    T("t15", f"{W2}/level-15-rollout", WL, """
In namespace {ns}, Deployment `critical-api` (3 replicas) can lose all its Pods at once during a rolling update.

Fix its update strategy so that the strategy type is RollingUpdate and `maxUnavailable` is lower than 100% and allows fewer Pods than the replica count to be unavailable. All 3 replicas must be Ready.
"""),
    T("t16", f"{W2}/level-16-pdb", WL, """
In namespace {ns}, Deployment `database-proxy` has 3 replicas. PodDisruptionBudget `db-proxy-pdb` blocks every voluntary eviction.

Fix the PodDisruptionBudget so that it still demands at least one available Pod, but fewer than the 3 replicas, and its status shows disruptionsAllowed greater than 0.
"""),
    T("t17", f"{W2}/level-17-bluegreen", WL, """
In namespace {ns}, Deployments `app-blue` and `app-green` are both running. Service `app-service` still sends traffic to the blue Pods.

Switch the Service to the green Pods: its selector must have `version: green`, and it must have at least one endpoint address.
"""),
    T("t18", f"{W2}/level-18-canary", WL, """
In namespace {ns}, Deployments `app-stable` and `app-canary` are both selected by Service `app-service`. The canary receives about half of the traffic.

Change the replica counts so that, of all Ready replicas of the two Deployments, the canary's share (rounded down to a whole percent) is between 8% and 12%.
"""),
    T("t19", f"{W2}/level-19-statefulset", WL, """
In namespace {ns}, `database` is a Deployment, but the workload needs stable Pod identities.

Run it as a StatefulSet named `database` (3 replicas, Pods labelled `app=database`, Service `database-service` is the existing headless Service) so that all of its replicas are Ready.
"""),
    T("t20", f"{W2}/level-20-replicaset", WL, """
In namespace {ns}, `web-app-rs` is a bare ReplicaSet.

Replace it with a Deployment named `web-app` with at least one replica, all of them Ready. After the change, no ReplicaSet that the Deployment `web-app` does not own may have replicas.
""", solution_extra=[["delete", "rs", "web-app-rs", "-n", "{ns}"]]),
    T("t36", f"{W4}/level-36-configmap-key", WL, """
In namespace {ns}, Pod `web-app` reads its settings from ConfigMap `app-config` and exits because `DATABASE_HOST` is not set.

Fix it so that the ConfigMap has a non-empty key `database_host`, the Pod is Running, its `DATABASE_HOST` environment variable is non-empty, and its log contains `App started successfully`.
"""),
    T("t37", f"{W4}/level-37-secret-encoding", WL, """
In namespace {ns}, Pod `database-client` reads its credentials from Secret `db-credentials` and exits.

Fix it so that the Pod is Running, its log contains `Connected successfully`, and `DB_USER` inside the Pod equals the base64-decoded value of `username` in the Secret.
"""),
    T("t42", f"{W5}/level-42-securitycontext", WL, """
In namespace {ns}, Pod `web-app` must run as a non-root user but does not start.

Fix it so that the Pod is Running, `runAsNonRoot` is true (Pod or container level), a non-zero `runAsUser` is set (Pod or container level), the container has `allowPrivilegeEscalation: false`, and `id -u` inside the container prints a number other than 0.
"""),
    T("t43", f"{W5}/level-43-resourcequota", WL, """
In namespace {ns}, ResourceQuota `compute-quota` is set and Deployment `resource-hungry-app` creates no Pods.

Fix it so that the quota still exists, the Deployment's container has CPU and memory requests, its CPU request is not larger than the quota's `requests.cpu`, and at least one replica is Ready.
"""),
    T("t45", f"{W5}/level-45-node-affinity", WL, """
In namespace {ns}, Pod `gpu-workload` stays Pending. The cluster's node carries the label `accelerator=gpu`.

Fix it so that the Pod is Running and still has a `nodeAffinity` rule.
""", node_reset=True),
    T("t47", f"{W5}/level-47-poddisruptionbudget", WL, """
In namespace {ns}, Deployment `web-app` has 2 replicas and PodDisruptionBudget `web-pdb` can never be satisfied.

Fix it so that the Deployment keeps at least 2 replicas, the PodDisruptionBudget still exists, it requires at least one Pod to stay available (but not more Pods than replicas), and its status shows `disruptionsAllowed` greater than 0.
"""),
    T("t48", f"{W5}/level-48-pod-security", WL, """
Namespace {ns} enforces the `restricted` Pod Security Standard. Deployment `secure-app` cannot start its Pod.

Fix the Deployment so that: the Pod or container has `runAsNonRoot: true`; a non-zero `runAsUser` is set; the container has `allowPrivilegeEscalation: false`; the container drops capability `ALL`; the seccomp profile type is `RuntimeDefault` (or `Localhost`); and at least one replica is Ready.
"""),
    T("t49", f"{W5}/level-49-priorityclass", WL, """
In namespace {ns}, Pods `dev-workload-1` and `critical-api` run with the default priority.

Create a PriorityClass named `exam-t49-high-priority` with a positive value that does not disable preemption, and make Pod `critical-api` use it, so that `critical-api` is Running and its priority is higher than that of `dev-workload-1`.
""", renames={"high-priority": "exam-t49-high-priority", "low-priority": "exam-t49-low-priority"},
      cluster_objects=["priorityclass/exam-t49-high-priority", "priorityclass/exam-t49-low-priority"]),

    # ---------------------------------------------------------------- Servicing and Networking (20%)
    T("t22", f"{W3}/level-22-nodeport", NET, """
In namespace {ns}, Service `web-nodeport` should expose Pod `web-app` on node port 30080.

Fix it so that the Service has type NodePort, the first port has nodePort 30080, and the Service has at least one endpoint address.
"""),
    T("t23", f"{W3}/level-23-dns", NET, """
In namespace {ns}, Pod `app-client` runs `pg_isready -h database -p 5432` in a loop. It cannot connect to PostgreSQL, which is served by Service `database-service`.

Fix it so that the Pod is Running and the host in its `pg_isready` command is the name of an existing Service of this namespace (short name, or `<service>.{ns}[.svc[.cluster.local]]`, not an IP address, and no `hostAliases`). The name must resolve inside the Pod and `pg_isready` run in the Pod must report `accepting connections`.
"""),
    T("t24", f"{W3}/level-24-ingress", NET, """
In namespace {ns}, Ingress `web-ingress` for host `myapp.local` must send every request path to Service `web-service` on port 80.

Fix it so that its first path is `/` with pathType Prefix or Exact, and the backend is Service `web-service`, port number 80.
"""),
    T("t25", f"{W3}/level-25-networkpolicy", NET, """
In namespace {ns}, Pod `frontend` calls Service `backend-service` (Pod `backend`, TCP 8080) but NetworkPolicy `backend-network-policy` blocks it.

Fix that policy so that Pods labelled `app=frontend` are allowed in. Both Pods must be Running and the logs of `frontend` must contain `API Response: Success`.
"""),
    T("t26", f"{W3}/level-26-sessionaffinity", NET, """
In namespace {ns}, Service `session-service` spreads each client's requests over several Pods (`app=session-app`).

Configure the Service so that a client keeps reaching the same Pod: `sessionAffinity` must be `ClientIP`. At least two `session-app` Pods must be Running.
"""),
    T("t27", f"{W3}/level-27-crossnamespace", NET, """
Pod `frontend-app` in namespace {ns} calls `http://api-service`, but Service `api-service` lives in namespace `exam-t27-backend`.

Fix the Pod so that its `wget` or `curl` call uses the Service name qualified with that namespace (`api-service.exam-t27-backend`, optionally followed by `.svc` or `.svc.cluster.local`). The shell script must stay the third element of the container's `command`. The Pod must be Running, and `wget -O- http://api-service.exam-t27-backend.svc.cluster.local` run inside it must print `API Response from exam-t27-backend`.
""", renames={"backend-ns": "exam-t27-backend"}, cluster_objects=["namespace/exam-t27-backend"]),
    T("t29", f"{W3}/level-29-loadbalancer", NET, """
In namespace {ns}, Service `web-service` has type LoadBalancer, which this cluster cannot provision.

Change it to a Service of type NodePort (with a node port assigned) that has at least one endpoint address. Pod `web-app` must be Running.
"""),
    T("t30", f"{W3}/level-30-headless", NET, """
In namespace {ns}, StatefulSet `web` (3 replicas, `serviceName: web-cluster`) needs a DNS name per Pod: `web-<n>.web-cluster.{ns}.svc.cluster.local`.

Fix the setup so that Service `web-cluster` is headless (`clusterIP: None`), every Pod is Ready, each of those DNS names resolves to the IP of its Pod from inside another Pod, and the Service has one endpoint address per Pod. Do not use `hostAliases`, and keep `serviceName: web-cluster`.
"""),
    T("t44", f"{W5}/level-44-networkpolicy", NET, """
In namespace {ns}, NetworkPolicy `deny-all` blocks all ingress and egress. Pod `backend` must reach Service `database` (Pod `database`, TCP 5432).

Add NetworkPolicies so that: the namespace has a policy whose name contains `allow`; one policy selects Pods with label `app=database`; one policy selects Pods with label `app=backend`; and `nc -vz database 5432 -w 5` run inside Pod `backend` succeeds. Both Pods must be Running and the Service `database` must have endpoints.
"""),

    # ---------------------------------------------------------------- Storage (10%)
    T("t31", f"{W4}/level-31-pvc-pending", ST, """
In namespace {ns}, PersistentVolumeClaim `app-storage-claim` stays Pending, so Pod `database-pod` cannot start. A PersistentVolume `exam-t31-app-storage` exists.

Fix it so that the claim is Bound to a PersistentVolume that is Bound, and Pod `database-pod` is Running with the claim mounted at `/data` (`ls /data` must work).
""", renames={"app-storage": "exam-t31-app-storage"}, cluster_objects=["pv/exam-t31-app-storage"]),
    T("t32", f"{W4}/level-32-volume-mount", ST, """
In namespace {ns}, Pod `web-app` exits because its application expects the file `/app/config/app.conf`. An init container writes that file to the volume backed by PersistentVolumeClaim `config-pvc`.

Fix the Pod so that it is Running, the first volume mount of its first container has mountPath `/app/config`, and `/app/config/app.conf` exists and is not empty.
""", renames={"config-storage": "exam-t32-config-storage"}, cluster_objects=["pv/exam-t32-config-storage"]),
    T("t33", f"{W4}/level-33-access-mode", ST, """
In namespace {ns}, Deployment `web-servers` (3 replicas) shares PersistentVolumeClaim `shared-pvc`, backed by PersistentVolume `exam-t33-shared-storage`. The replicas cannot all start.

Fix it so that both the PersistentVolume and the claim list `ReadWriteMany` in their access modes, the claim is Bound, and all 3 replicas are updated, Ready and available.
""", renames={"shared-storage": "exam-t33-shared-storage"}, cluster_objects=["pv/exam-t33-shared-storage"]),
    T("t34", f"{W4}/level-34-statefulset-volumes", ST, """
In namespace {ns}, StatefulSet `postgres-cluster` (3 replicas) makes all Pods share one PersistentVolumeClaim, `database-storage`.

Fix it so that every replica gets its own claim from a `volumeClaimTemplates` entry named `database-storage` (claims `database-storage-postgres-cluster-0`, `-1` and `-2`, all Bound, labelled `app=postgres`), each Pod uses its own claim, and all 3 replicas are Ready.
"""),
    T("t35", f"{W4}/level-35-storageclass", ST, """
In namespace {ns}, PersistentVolumeClaim `app-storage` requests StorageClass `exam-t35-premium-ssd`, so Pod `data-processor` cannot start.

Fix it so that the claim names a StorageClass that exists and is Bound, and Pod `data-processor` is Running with the claim mounted at `/data`.
""", renames={"premium-ssd": "exam-t35-premium-ssd"}, cluster_objects=["storageclass/exam-t35-premium-ssd"]),
    T("t38", f"{W4}/level-38-volume-permissions", ST, """
In namespace {ns}, Pod `writer-app` runs as user and group 1000 and cannot write to its volume, PersistentVolumeClaim `app-data`, mounted at `/data`.

Fix it so that the claim is Bound, the Pod has a Pod-level `fsGroup`, its first container keeps a `runAsUser` and is Running, its log contains `Write successful`, and `/data/test.txt` contains `test data`.
"""),
    T("t39", f"{W4}/level-39-reclaim-policy", ST, """
In namespace {ns}, PersistentVolume `exam-t39-important-data` holds important data and would be deleted along with its claim `data-claim`.

Fix it so that the PersistentVolume's reclaim policy is `Retain`, claim `data-claim` is Bound to that PersistentVolume, and Pod `data-writer` is Running with `Data written successfully` in its log and a non-empty `/data/important.txt`.
""", renames={"important-data": "exam-t39-important-data"}, cluster_objects=["pv/exam-t39-important-data"]),
    T("t40", f"{W4}/level-40-emptydir-vs-pvc", ST, """
In namespace {ns}, Pod `data-app` keeps its data in an emptyDir volume, so it is lost when the Pod is deleted.

Create PersistentVolumeClaim `app-data` and make the Pod use it as its first volume instead. The claim must be Bound, the Pod Running, and a file written to `/data` in the Pod must be readable.
"""),

    # ---------------------------------------------------------------- Cluster Architecture, Installation and Configuration (25%)
    T("t41", f"{W5}/level-41-rbac-permission", CA, """
In namespace {ns}, Pod `pod-lister` uses ServiceAccount `pod-reader` and is not allowed to list Pods.

Grant the permission with a Role named `pod-reader-role` (whose first rule includes the verb `list`) and a RoleBinding named `pod-reader-binding` that binds that Role to ServiceAccount `pod-reader`. Pod `pod-lister` must be Running with `Success! Can list pods` in its log, and `kubectl auth can-i list pods --as=system:serviceaccount:{ns}:pod-reader -n {ns}` must answer yes.
"""),
    T("t58", f"{W6}/level-58-serviceaccount-rbac", CA, """
In namespace {ns}, Pod `reports-pod` uses ServiceAccount `reports-sa` to list ConfigMaps through the API and gets HTTP 403, although a Role and a RoleBinding exist.

Fix it so that `reports-sa` can list ConfigMaps in {ns} and has no permission beyond `get` and `list` on ConfigMaps (beyond what every authenticated user has). No ClusterRoleBinding may name the ServiceAccount. The Pod must be Running and the last line of its log must end in `HTTP 200` (it makes a call every 5 seconds).
"""),
]

BY_ID_ALL = {t["id"]: t for t in ALL_TASKS}
assert len(BY_ID_ALL) == len(ALL_TASKS), "duplicate task id"


def namespace(task_id, kind="exam"):
    """Task namespace: exam-<id> for the mock exam, drill-<id> for Drill mode."""
    return f"{kind}-{task_id}"


def _retag(name, task_id, kind):
    """Rename an exam-prefixed object to the prefix of `kind`: exam-t31-app-storage -> drill-t31-app-storage."""
    old = f"exam-{task_id}-"
    return f"{kind}-{task_id}-" + name[len(old):] if name.startswith(old) else name


def renames_for(task, kind="exam"):
    """The task's old->new renames, with the new names under the `kind` prefix (drill and exam objects never share names)."""
    return {old: _retag(new, task["id"], kind) for old, new in task.get("renames", {}).items()}


def cluster_objects_for(task, kind="exam"):
    """The task's cluster-scoped objects ("pv/exam-t31-x") under the `kind` prefix."""
    out = []
    for obj in task.get("cluster_objects", ()):
        k, _, name = obj.partition("/")
        out.append(f"{k}/{_retag(name, task['id'], kind)}")
    return out


STATUS_FILE = HERE / "e2e-status.json"


def load_status(path=None):
    """The recorded e2e verdicts. Raises RuntimeError when the file is missing or corrupt."""
    path = Path(path) if path else STATUS_FILE
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise RuntimeError(f"{path} is missing or unreadable ({type(e).__name__}); run "
                           "`python3 exam/e2e.py --write-status` on the VM to prove the pool") from None
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} is corrupt: expected a JSON object")
    return data


def select_pool(status, tasks=None):
    """Tasks whose recorded verdict is OK. A task with no entry is not proven and is left out."""
    return [t for t in (tasks if tasks is not None else ALL_TASKS)
            if isinstance(status.get(t["id"]), dict) and status[t["id"]].get("verdict") == "OK"]


def _pool():
    if os.environ.get("EXAM_ALLOW_UNPROVEN") == "1":      # only e2e.py sets this
        return list(ALL_TASKS)
    return select_pool(load_status())


POOL = _pool()
BY_ID = {t["id"]: t for t in POOL}


def render_text(task, host, kind="exam"):
    ns = namespace(task["id"], kind)
    body = task["text"].replace("{ns}", ns)
    if kind != "exam":
        body = body.replace(f"exam-{task['id']}-", f"{kind}-{task['id']}-")
    return {"host": host, "ssh": f"ssh {host}", "body": body, "domain": task["domain"]}


def drill_title(task, kind="drill"):
    """Short title for the Drill picker: the first sentence of the exam text, namespace phrase stripped.

    Built from the exam text only. mission.yaml's name/description/concepts name the cause and are never used."""
    para = task["text"].split("\n\n", 1)[0]
    end, tick = len(para), False
    for i, c in enumerate(para):          # first '.' outside a `code span` that ends a sentence
        if c == "`":
            tick = not tick
        elif c == "." and not tick and (i + 1 == len(para) or para[i + 1].isspace()):
            end = i + 1
            break
    s = " ".join(para[:end].split())
    s = re.sub(r"^In namespace \{ns\},? ", "", s)
    s = re.sub(r"^Namespace \{ns\} ", "The namespace ", s)
    s = re.sub(r" in namespace \{ns\}", "", s)
    s = s.replace("{ns}", namespace(task["id"], kind)).replace(f"exam-{task['id']}-", f"{kind}-{task['id']}-")
    return s[:1].upper() + s[1:]


def solution_extra_text(task, kind="exam"):
    """Manual steps the level's solution.yaml cannot express (e.g. delete the old ReplicaSet), as kubectl lines."""
    ns = namespace(task["id"], kind)
    return ["kubectl " + " ".join(a.replace("{ns}", ns) for a in cmd) for cmd in task.get("solution_extra", ())]
