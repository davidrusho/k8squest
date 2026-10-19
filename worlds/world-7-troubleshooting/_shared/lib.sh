#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
#
# Shared helpers for World 7 scripts. Not a level: discovery only reads level-*
# directories. Source it from a level with:
#   . "$(dirname "$0")/../_shared/lib.sh"
#
# World 7 runs on the 3-node kind cluster k8squest-multinode (kind/multinode.yaml).
# Its levels break the cluster itself (kubelets, static-pod manifests, CoreDNS,
# kindnet, metrics-server), so every setup.sh calls heal_cluster FIRST: it puts
# back anything an earlier level, a replay or the player left broken, and only then
# does the level inject its own fault. heal.sh (next to world.yaml) runs the same
# function before the engine resets a level.
#
# "Pristine" copies of the files the levels edit live ON THE NODES in
# /root/k8squest-pristine/, captured once from the freshly created, healthy cluster.

. "$(dirname "${BASH_SOURCE[0]}")/../../_shared/lib.sh"

# World 7 runs on the multi-node cluster. The engine and the harness export K8SQUEST_CONTEXT;
# a script run by hand must not default to the main cluster, because these levels edit
# CoreDNS, kindnet, metrics-server and the nodes of whatever cluster kubectl points at.
: "${K8SQUEST_CONTEXT:=kind-k8squest-multinode}"
export K8SQUEST_CONTEXT

CLUSTER_NAME="${K8SQUEST_KIND_CLUSTER:-k8squest-multinode}"
CP_NODE="${CLUSTER_NAME}-control-plane"
WORKER1="${CLUSTER_NAME}-worker"
WORKER2="${CLUSTER_NAME}-worker2"
ALL_NODES="$CP_NODE $WORKER1 $WORKER2"
PRISTINE=/root/k8squest-pristine
MANIFESTS=/etc/kubernetes/manifests
SNAPSHOT_PATH=/var/lib/etcd/k8squest-snapshot.db   # level 70

# One file per row: <node-kind>:<live path>:<pristine name>. node-kind "all" = every node, "cp" = control plane.
PRISTINE_FILES="
all:/var/lib/kubelet/config.yaml:kubelet-config.yaml
all:/var/lib/kubelet/kubeadm-flags.env:kubeadm-flags.env
cp:$MANIFESTS/kube-apiserver.yaml:kube-apiserver.yaml
cp:$MANIFESTS/kube-controller-manager.yaml:kube-controller-manager.yaml
cp:$MANIFESTS/kube-scheduler.yaml:kube-scheduler.yaml
"

# node_sh <node> <shell command...>: run a command inside a kind node container
node_sh() {
    local node=$1
    shift
    docker exec "$node" bash -c "$*"
}

# kubectl with a client timeout, for the code that must not hang when the API server is down
kq() { kubectl --request-timeout=10s "$@"; }

api_ok() { kubectl --request-timeout=5s get --raw /readyz >/dev/null 2>&1; }

# wait_api <seconds>
wait_api() {
    local end=$((SECONDS + $1))
    while [ $SECONDS -lt $end ]; do
        api_ok && return 0
        sleep 2
    done
    return 1
}

# wait_api_down <seconds>: wait until the API server stops answering
wait_api_down() {
    local end=$((SECONDS + $1))
    while [ $SECONDS -lt $end ]; do
        api_ok || return 0
        sleep 2
    done
    return 1
}

node_ready() { [ "$(kq get node "$1" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)" = "True" ]; }

# wait_node_state <node> <Ready|NotReady> <seconds>
wait_node_state() {
    local node=$1 want=$2 end=$((SECONDS + $3))
    while [ $SECONDS -lt $end ]; do
        if node_ready "$node"; then
            [ "$want" = Ready ] && return 0
        else
            [ "$want" = NotReady ] && return 0
        fi
        sleep 3
    done
    return 1
}

# wait_nodes_ready <seconds>: all three nodes Ready
wait_nodes_ready() {
    local end=$((SECONDS + $1)) n ok
    while [ $SECONDS -lt $end ]; do
        ok=1
        for n in $ALL_NODES; do node_ready "$n" || ok=0; done
        [ $ok = 1 ] && return 0
        sleep 3
    done
    return 1
}

# wait_pod_ready <namespace> <selector> <seconds>
wait_pod_ready() {
    local end=$((SECONDS + $3))
    while [ $SECONDS -lt $end ]; do
        kq wait --for=condition=Ready pod -l "$2" -n "$1" --timeout=5s >/dev/null 2>&1 && return 0
        sleep 3
    done
    return 1
}

# ---------------------------------------------------------------- pristine copies

# for_each_pristine_file <function> : calls <function> <node> <live path> <pristine name>
for_each_pristine_file() {
    local fn=$1 row kind path name node
    for row in $PRISTINE_FILES; do
        kind=${row%%:*}
        path=${row#*:}; path=${path%%:*}
        name=${row##*:}
        for node in $ALL_NODES; do
            if [ "$kind" = all ] || { [ "$kind" = cp ] && [ "$node" = "$CP_NODE" ]; }; then
                "$fn" "$node" "$path" "$name"
            fi
        done
    done
}

_capture_one() { node_sh "$1" "mkdir -p $PRISTINE && cp -n $2 $PRISTINE/$3" ; }

# The pristine copies are taken once, from a healthy cluster. Taking them from a broken
# one would make the fault the baseline, so refuse (the fix is a fresh cluster).
capture_pristine() {
    local n have=1
    for n in $ALL_NODES; do
        node_sh "$n" "test -e $PRISTINE/.complete" 2>/dev/null || have=0
    done
    [ $have = 1 ] && return 0
    if ! api_ok || ! wait_nodes_ready 60 || ! kq get pods -n kube-system >/dev/null 2>&1; then
        echo "[setup] ERROR: no pristine copies exist yet and the cluster is not healthy, so a baseline cannot be taken." >&2
        echo "[setup] Recreate the cluster: kind delete cluster --name $CLUSTER_NAME (the engine creates it again)" >&2
        return 1
    fi
    log "capturing the pristine node files in $PRISTINE (first run on this cluster)"
    for_each_pristine_file _capture_one || return 1
    # CoreDNS Corefile and replica count (level 66)
    kq -n kube-system get configmap coredns -o jsonpath='{.data.Corefile}' | docker exec -i "$CP_NODE" bash -c "mkdir -p $PRISTINE && cat > $PRISTINE/Corefile" || return 1
    kq -n kube-system get deploy coredns -o jsonpath='{.spec.replicas}' | docker exec -i "$CP_NODE" bash -c "cat > $PRISTINE/coredns-replicas" || return 1
    for n in $ALL_NODES; do
        node_sh "$n" "touch $PRISTINE/.complete" || return 1
    done
}

_restore_one() {
    local node=$1 path=$2 name=$3
    if ! node_sh "$node" "cmp -s $PRISTINE/$name $path"; then
        node_sh "$node" "cp -p $PRISTINE/$name $path" || return 1
        log "restored $path on $node"
        case "$path" in
            /var/lib/kubelet/*) RESTART_KUBELET="$RESTART_KUBELET $node" ;;
        esac
    fi
}

# ---------------------------------------------------------------- the heal step

# heal_cluster: put the cluster back to the healthy baseline. Idempotent and cheap when
# nothing is broken. Order: node files and services first (they work with the API
# server down), then wait for the API server, then the Kubernetes objects.
heal_cluster() {
    need docker || return 1
    local n
    for n in $ALL_NODES; do
        docker inspect -f '{{.State.Running}}' "$n" 2>/dev/null | grep -qx true \
            || { echo "[setup] ERROR: node container $n is not running (is the k8squest-multinode cluster up?)" >&2; return 1; }
    done
    capture_pristine || return 1

    # 1. node files (kubelet config + flags, control-plane manifests)
    RESTART_KUBELET=""
    for_each_pristine_file _restore_one || return 1
    for n in $RESTART_KUBELET; do
        node_sh "$n" "systemctl restart kubelet" || return 1
    done
    # 2. kubelet enabled and running on every node (level 61 stops and disables it)
    for n in $ALL_NODES; do
        node_sh "$n" "systemctl is-enabled --quiet kubelet || systemctl enable kubelet >/dev/null 2>&1; systemctl is-active --quiet kubelet || { systemctl reset-failed kubelet 2>/dev/null; systemctl start kubelet; }" \
            || { echo "[setup] ERROR: could not start the kubelet on $n" >&2; return 1; }
    done
    # 3. the API server, then everything that needs it
    wait_api 180 || { echo "[setup] ERROR: the API server did not come back after the heal step" >&2; return 1; }
    # Anything that can hold a node NotReady is healed BEFORE we wait for Ready: a node whose
    # CNI is gone (level 67) never becomes Ready until kindnet is put back. The kubelet and
    # its config were restored above (levels 61, 62, 70).
    heal_kindnet || return 1
    wait_nodes_ready 180 || { echo "[setup] ERROR: not every node became Ready after the heal step" >&2; return 1; }
    for n in $ALL_NODES; do
        [ "$(kq get node "$n" -o jsonpath='{.spec.unschedulable}' 2>/dev/null)" = true ] && kq uncordon "$n" >/dev/null
    done
    heal_coredns || return 1
    heal_metrics_server || return 1
    # 4. control-plane static pods Ready (their mirror pods can lag a restored manifest)
    local c
    for c in kube-apiserver kube-controller-manager kube-scheduler etcd; do
        wait_pod_ready kube-system "component=$c" 150 \
            || { echo "[setup] ERROR: $c is not Ready after the heal step" >&2; return 1; }
    done
    return 0
}

# kindnet: DaemonSet back to its stock nodeSelector, the level-67 node label removed, and a
# kindnet pod on every node (it writes the node's CNI config when it starts).
heal_kindnet() {
    local n
    if kq -n kube-system get ds kindnet -o jsonpath='{.spec.template.spec.nodeSelector}' | grep -q 'k8squest.io'; then
        log "restoring the kindnet DaemonSet nodeSelector"
        kq -n kube-system patch ds kindnet --type=json \
            -p '[{"op":"remove","path":"/spec/template/spec/nodeSelector/k8squest.io~1cni"}]' >/dev/null || return 1
        # the template changed, so the DaemonSet rolls its pods; wait for that to finish
        kubectl --request-timeout=60s -n kube-system rollout status ds/kindnet --timeout=150s >/dev/null || return 1
    fi
    kq label nodes --all k8squest.io/cni- >/dev/null 2>&1
    retry 60 3 kindnet_ready || { echo "[setup] ERROR: kindnet is not Ready on every node" >&2; return 1; }
    # kindnet writes a node's CNI config when its pod starts. A config removed by hand is not
    # noticed by the runtime until the file is written again, so restart that node's pod.
    local fixed=0
    for n in $ALL_NODES; do
        if ! retry 10 3 node_sh "$n" "test -s /etc/cni/net.d/10-kindnet.conflist" >/dev/null 2>&1; then
            log "kindnet CNI config missing on $n; restarting its kindnet pod"
            kq -n kube-system delete pod -l app=kindnet --field-selector "spec.nodeName=$n" --wait=false >/dev/null 2>&1
            fixed=1
        fi
    done
    [ $fixed = 1 ] && { retry 60 3 kindnet_ready || return 1; }
    wait_nodes_ready 120 || { echo "[setup] ERROR: a node is not Ready after the kindnet heal" >&2; return 1; }
}

kindnet_ready() {
    local want have
    want=$(kq get nodes --no-headers 2>/dev/null | wc -l | tr -d ' ')
    have=$(kq -n kube-system get ds kindnet -o jsonpath='{.status.numberReady}' 2>/dev/null)
    [ -n "$want" ] && [ "$want" -gt 0 ] && [ "$have" = "$want" ]
}

# CoreDNS: stock Corefile and replica count (level 66)
heal_coredns() {
    local want_replicas have cur changed=0
    want_replicas=$(node_sh "$CP_NODE" "cat $PRISTINE/coredns-replicas")
    cur=$(kq -n kube-system get configmap coredns -o jsonpath='{.data.Corefile}')
    if [ "$cur" != "$(node_sh "$CP_NODE" "cat $PRISTINE/Corefile")" ]; then
        log "restoring the CoreDNS Corefile"
        node_sh "$CP_NODE" "cat $PRISTINE/Corefile" > "${TMPDIR:-/tmp}/k8squest-Corefile.$$" || return 1
        kubectl --request-timeout=20s -n kube-system create configmap coredns \
            --from-file=Corefile="${TMPDIR:-/tmp}/k8squest-Corefile.$$" --dry-run=client -o yaml \
            | kubectl --request-timeout=20s replace -f - >/dev/null
        local rc=$?
        rm -f "${TMPDIR:-/tmp}/k8squest-Corefile.$$"
        [ $rc = 0 ] || return 1
        changed=1
    fi
    have=$(kq -n kube-system get deploy coredns -o jsonpath='{.spec.replicas}')
    if [ "$have" != "$want_replicas" ]; then
        log "scaling CoreDNS back to $want_replicas replicas"
        kq -n kube-system scale deploy coredns --replicas="$want_replicas" >/dev/null || return 1
    fi
    [ $changed = 1 ] && { kq -n kube-system rollout restart deploy/coredns >/dev/null || return 1; }
    kubectl --request-timeout=60s -n kube-system rollout status deploy/coredns --timeout=120s >/dev/null \
        || { echo "[setup] ERROR: CoreDNS did not become ready" >&2; return 1; }
}

# metrics-server (level 68): when it is installed, it must have --kubelet-insecure-tls
# (kind's kubelet serves a certificate the cluster CA did not sign) and one replica.
heal_metrics_server() {
    kq -n kube-system get deploy metrics-server >/dev/null 2>&1 || return 0
    if ! kq -n kube-system get deploy metrics-server -o jsonpath='{.spec.template.spec.containers[0].args}' | grep -q kubelet-insecure-tls; then
        log "restoring --kubelet-insecure-tls on metrics-server"
        kq -n kube-system patch deploy metrics-server --type=json \
            -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]' >/dev/null || return 1
    fi
    [ "$(kq -n kube-system get deploy metrics-server -o jsonpath='{.spec.replicas}')" = 1 ] \
        || kq -n kube-system scale deploy metrics-server --replicas=1 >/dev/null
    kubectl --request-timeout=60s -n kube-system rollout status deploy/metrics-server --timeout=150s >/dev/null || return 1
}

# ---------------------------------------------------------------- helpers for the levels

# edit_node_file <node> <file> <sed expression> <grep pattern that must match afterwards>
# Edits a file on a node and refuses to carry on if the edit did not take.
edit_node_file() {
    local node=$1 file=$2 expr=$3 pat=$4
    node_sh "$node" "sed -i '$expr' $file" || return 1
    node_sh "$node" "grep -q -- '$pat' $file" \
        || { echo "[setup] ERROR: editing $file on $node did not produce the expected fault ($pat)" >&2; return 1; }
}

# pod_rows <namespace> <label selector>: one "name|node|phase|deletionTimestamp" row per pod
# (a jsonpath filter on a missing deletionTimestamp matches nothing, so filter in awk)
pod_rows() {
    kq get pods -n "$1" -l "$2" -o jsonpath='{range .items[*]}{.metadata.name}{"|"}{.spec.nodeName}{"|"}{.status.phase}{"|"}{.metadata.deletionTimestamp}{"\n"}{end}' 2>/dev/null
}

# pod_nodes <namespace> <label selector>: "name node" for every pod that is not Terminating
pod_nodes() { pod_rows "$@" | awk -F'|' '$4 == "" {print $1 " " $2}'; }

# running_nodes <namespace> <label selector>: the node of every Running pod that is not Terminating
running_nodes() { pod_rows "$@" | awk -F'|' '$4 == "" && $3 == "Running" {print $2}'; }

# Validate scripts: stop with a clear message when the cluster is not the world's own.
validate_context() {
    local want="${K8SQUEST_CONTEXT:-kind-k8squest-multinode}" ctx
    ctx=$(kubectl config current-context 2>/dev/null || true)
    if [ "$ctx" != "$want" ]; then
        echo "❌ kubectl context is '${ctx:-none}', but World 7 runs on '$want'."
        echo "💡 kubectl config use-context $want"
        exit 1
    fi
}
