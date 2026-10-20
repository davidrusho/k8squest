#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
#
# Shared helpers for World 8 scripts. Not a level: discovery only reads level-*
# directories. Source it from a level with:
#   . "$(dirname "$0")/../_shared/lib.sh"
#
# World 8 runs on two Lima virtual machines, k8squest-cp and k8squest-worker, that share
# the user-v2 network (lima/node.yaml). Levels 71-73 build a cluster on them from nothing,
# so the machines are plain Ubuntu with kubeadm, kubelet and kubectl installed and NOTHING
# else done. Every setup.sh puts both machines into the exact state that precedes its level
# no matter what state they are in (kubeadm reset first), and the machines themselves are
# reused, never recreated. Script files that run INSIDE the machines are in guest/.
#
# kubectl: levels 71 and 72 start with no cluster, so the kubectl context k8squest-lima
# exists (the engine creates it) but points at nothing until the cluster is initialised.
# export_kubeconfig points it at the real cluster. Validators use kc, which runs kubectl as
# root on the control plane with its admin.conf, so they work whether or not the player
# ever set up kubectl on the host.

. "$(dirname "${BASH_SOURCE[0]}")/../../_shared/lib.sh"

# The engine and the harness export K8SQUEST_CONTEXT; a script run by hand must not
# default to the main cluster.
: "${K8SQUEST_CONTEXT:=k8squest-lima}"
export K8SQUEST_CONTEXT

GUEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/guest" && pwd)"

CP_VM=k8squest-cp
WK_VM=k8squest-worker
CP_NODE=lima-k8squest-cp          # the Kubernetes node names are the machines' host names
WK_NODE=lima-k8squest-worker
API_HOST_PORT=16443                # lima/node.yaml forwards the guest's 6443 here

# Pinned. The package version is what apt installs, the Kubernetes version what kubeadm reports.
K8S_NEW_MINOR=v1.37 K8S_NEW_PKG=1.37.1-1.1 K8S_NEW=v1.37.1
K8S_OLD_MINOR=v1.36 K8S_OLD_PKG=1.36.5-1.1 K8S_OLD=v1.36.5
FLANNEL_VERSION=v0.28.9
FLANNEL_URL="https://github.com/flannel-io/flannel/releases/download/${FLANNEL_VERSION}/kube-flannel.yml"
# sha256 of that exact manifest (checked when it was pinned); a different file is refused
FLANNEL_SHA256=1c06a15a771009c263bdb1f51c928af46f7606fe969f3963652167938d536aaa
# The kubectl context World 8 owns. Fixed on purpose: export_kubeconfig overwrites it, so it must
# not follow an environment variable that could name somebody else's context.
LIMA_CONTEXT=k8squest-lima

# ---------------------------------------------------------------- talking to the machines

# vm_sh <vm> <shell command>: run a command as root inside a machine (stdout is the command's)
vm_sh() { limactl shell --workdir /tmp "$1" sudo bash -c "$2"; }

# vm_script <vm> <guest script> [args...]: run guest/<script> as root inside a machine
vm_script() {
    local vm=$1 script=$2
    shift 2
    limactl shell --workdir /tmp "$vm" sudo bash -s -- "$@" < "$GUEST_DIR/$script"
}

# kc <kubectl args>: kubectl as root on the control plane, with the cluster's own admin.conf
kc() { limactl shell --workdir /tmp "$CP_VM" sudo kubectl --kubeconfig /etc/kubernetes/admin.conf "$@"; }

# wait_admin [seconds]: wait until the API server answers AND authorizes the admin credentials.
# Right after an API server restart (a kubeadm upgrade, a kubelet upgrade that restarts the
# static pods) the server answers "forbidden" for a few seconds before it has loaded the RBAC
# bindings, which a plain "is it up" check does not see.
wait_admin() {
    local end=$((SECONDS + ${1:-120})) out
    while [ $SECONDS -lt $end ]; do
        # a failing command substitution must not end a caller running under set -e: the server is
        # expected to be unreachable for a while after a restart
        out=$(kc auth can-i get nodes 2>/dev/null || echo no)
        [ "$out" = yes ] && return 0
        sleep 2
    done
    return 1
}

# on_both <guest script> [args...]: run a guest script on both machines at once
on_both() {
    local pids=() rc=0 vm p
    for vm in "$CP_VM" "$WK_VM"; do
        vm_script "$vm" "$@" &
        pids+=($!)
    done
    for p in "${pids[@]}"; do wait "$p" || rc=1; done
    return $rc
}

# require_vms: both machines exist and are running (the engine and the harness create them)
require_vms() {
    need limactl || return 1
    local vm
    for vm in "$CP_VM" "$WK_VM"; do
        limactl list --format '{{.Name}} {{.Status}}' 2>/dev/null | grep -qx "$vm Running" && continue
        echo "[setup] ERROR: the Lima machine $vm is missing or not running." >&2
        echo "[setup] Start the level from the game, which creates and starts it. By hand: limactl list ; limactl start $vm" >&2
        return 1
    done
}

# ---------------------------------------------------------------- machine states

# ensure_packages <minor> <package version> <kubernetes version> [no-etcd-tools]: kubelet/kubeadm/kubectl
# at exactly that version (held), containerd installed but not configured, the images that version's
# kubeadm init needs, and (unless told otherwise) the etcdctl/etcdutl matching that version's etcd on the
# control plane. Level 74 passes no-etcd-tools for the OLD version, so the tools always match the
# etcd of the cluster level 75 builds. Quick when it was done before.
ensure_packages() {
    on_both k8s-packages.sh "$1" "$2" || return 1
    local tools=cp
    [ "${4:-}" = no-etcd-tools ] && tools=cp-no-etcd
    vm_script "$CP_VM" base.sh "$3" "$tools" &
    local p=$!
    vm_script "$WK_VM" base.sh "$3" worker || { wait "$p"; return 1; }
    wait "$p"
}

reset_nodes() { on_both reset-node.sh; }
prep_nodes() { on_both prep-node.sh; }

# nodes_ready <count> <seconds>
wait_nodes_ready() {
    local end=$((SECONDS + $2)) ready
    while [ $SECONDS -lt $end ]; do
        ready=$(kc get nodes --no-headers 2>/dev/null | awk '$2 == "Ready"' | wc -l | tr -d ' ')
        [ "$ready" = "$1" ] && return 0
        sleep 3
    done
    return 1
}

# control_plane_up <kubernetes version>: kubeadm init, flannel, wait until the node and CoreDNS are up
control_plane_up() {
    vm_script "$CP_VM" init-cp.sh "$1" || return 1
    install_flannel || return 1
    wait_nodes_ready 1 240 || { echo "[setup] ERROR: the control-plane node never became Ready" >&2; return 1; }
    kc -n kube-system rollout status deploy/coredns --timeout=240s >/dev/null || return 1
}

# install_flannel: download the pinned manifest on the control plane, refuse it unless its sha256
# matches FLANNEL_SHA256, then apply that file
install_flannel() {
    vm_sh "$CP_VM" "curl -fsSL '$FLANNEL_URL' -o /tmp/kube-flannel.yml && echo '$FLANNEL_SHA256  /tmp/kube-flannel.yml' | sha256sum -c - >/dev/null" \
        || { echo "[setup] ERROR: could not download the Flannel manifest, or its sha256 does not match the pinned value" >&2; return 1; }
    kc apply -f /tmp/kube-flannel.yml >/dev/null
}

# join_worker: a fresh token from the control plane, then kubeadm join on the worker
join_worker() {
    local cmd
    cmd=$(vm_sh "$CP_VM" 'kubeadm token create --print-join-command') || return 1
    [ -n "$cmd" ] || return 1
    vm_sh "$WK_VM" "$cmd" >/dev/null 2>&1 || { echo "[setup] ERROR: kubeadm join failed on $WK_VM" >&2; return 1; }
    wait_nodes_ready 2 240 || { echo "[setup] ERROR: the worker never became Ready" >&2; return 1; }
}

# give_player_kubectl: kubectl for the player on the control plane (what the kubeadm init output
# tells them to do in level 72), for the levels that start with a cluster already built
give_player_kubectl() { vm_script "$CP_VM" player-kubeconfig.sh; }

# cluster_up <kubernetes version>: a working two-node cluster, kubectl ready for the player
cluster_up() {
    control_plane_up "$1" || return 1
    join_worker || return 1
    give_player_kubectl || return 1
    export_kubeconfig
}

ensure_namespace() {
    kc create namespace "${NAMESPACE:-k8squest}" --dry-run=client -o yaml | kc apply -f - >/dev/null
}

# apply_workload [file]: apply the level's broken.yaml (the workload) from the host
apply_workload() { kc apply -f - < "${1:-broken.yaml}" >/dev/null; }

# remember <name> <value>: a fact the validator needs later, kept on the control plane
remember() { vm_sh "$CP_VM" "mkdir -p /var/lib/k8squest && printf '%s' '$2' > /var/lib/k8squest/level-$1"; }
recall() { vm_sh "$CP_VM" "cat /var/lib/k8squest/level-$1 2>/dev/null"; }

# etcdctl_cp <etcdctl args>: etcdctl on the control plane with the endpoint and the TLS files of
# the kubeadm-managed etcd
etcdctl_cp() {
    vm_sh "$CP_VM" "etcdctl --endpoints=https://127.0.0.1:2379 --cacert=/etc/kubernetes/pki/etcd/ca.crt --cert=/etc/kubernetes/pki/etcd/server.crt --key=/etc/kubernetes/pki/etcd/server.key $*"
}

# etcd_cluster_id: the ID of the etcd cluster. etcdutl snapshot restore gives the restored
# member a NEW cluster ID, which is how level 75 tells a restore from a no-op.
etcd_cluster_id() { etcdctl_cp endpoint status -w json | grep -o '"cluster_id":[0-9]*' | head -1 | cut -d: -f2; }

# ---------------------------------------------------------------- the host's kubeconfig

# export_kubeconfig: put the cluster's admin credentials into the host kubeconfig under the
# context k8squest-lima, and select it. The API server's port is forwarded to
# 127.0.0.1:16443; its certificate does not list 127.0.0.1, so the connection checks it
# against the name "kubernetes", which every kubeadm API server certificate carries.
export_kubeconfig() {
    need kubectl || return 1
    local tmp ctx=$LIMA_CONTEXT
    tmp=$(mktemp -d) || return 1
    vm_sh "$CP_VM" 'cat /etc/kubernetes/admin.conf' > "$tmp/admin.conf" || { rm -rf "$tmp"; return 1; }
    local f
    for f in "certificate-authority-data:ca.crt:clusters" "client-certificate-data:client.crt:users" "client-key-data:client.key:users"; do
        local key=${f%%:*} rest=${f#*:}
        local file=${rest%%:*} kind=${rest#*:}
        local path
        if [ "$kind" = clusters ]; then path="{.clusters[0].cluster.$key}"; else path="{.users[0].user.$key}"; fi
        kubectl --kubeconfig "$tmp/admin.conf" config view --raw -o jsonpath="$path" | base64 --decode > "$tmp/$file"
    done
    [ -s "$tmp/ca.crt" ] && [ -s "$tmp/client.crt" ] && [ -s "$tmp/client.key" ] \
        || { echo "[setup] ERROR: could not read the credentials from admin.conf" >&2; rm -rf "$tmp"; return 1; }
    kubectl config set-cluster "$ctx" --server="https://127.0.0.1:${API_HOST_PORT}" --tls-server-name=kubernetes \
        --certificate-authority="$tmp/ca.crt" --embed-certs=true >/dev/null
    kubectl config set-credentials "${ctx}-admin" --client-certificate="$tmp/client.crt" --client-key="$tmp/client.key" \
        --embed-certs=true >/dev/null
    kubectl config set-context "$ctx" --cluster="$ctx" --user="${ctx}-admin" >/dev/null
    rm -rf "$tmp"
}

# ---------------------------------------------------------------- validators

# validate_vms: stop with a clear message when the machines are not there
validate_vms() {
    if ! require_vms 2>/dev/null; then
        echo "❌ The Lima machines $CP_VM and $WK_VM are not both running."
        echo "💡 limactl list    (start them with: limactl start $CP_VM ; limactl start $WK_VM)"
        exit 1
    fi
}
