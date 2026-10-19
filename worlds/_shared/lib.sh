#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
#
# Helpers shared by every world's setup.sh (Worlds 6 and 7). Not a world: discovery
# only reads worlds/*/world.yaml, and this directory has none. Worlds source it from
# their own _shared/lib.sh, with a path relative to that file:
#   . "$(dirname "${BASH_SOURCE[0]}")/../../_shared/lib.sh"

METRICS_SERVER_VERSION="v0.9.0"           # https://github.com/kubernetes-sigs/metrics-server

log() { echo "[setup] $*"; }

# Setup scripts create and delete cluster-scoped objects and edit nodes, so refuse to
# run against any cluster except the one the level's world runs on. The engine and
# the harness export K8SQUEST_CONTEXT (engine/level_reset.py context_for): kind-k8squest
# for `cluster: kind` worlds, kind-k8squest-multinode for `cluster: kind-multinode`.
# Without it the default is kind-k8squest.
# (World 6 declares `cluster: kind` and is only tested on kind; under K8S_CLUSTER_TYPE=k3s the
# engine exports k3s-k8squest, which this guard therefore accepts.)
# Override (at your own risk): K8SQUEST_ALLOW_CONTEXT=1
require_game_context() {
    local ctx want="${K8SQUEST_CONTEXT:-kind-k8squest}"
    ctx=$(kubectl config current-context 2>/dev/null || true)
    if [ "$ctx" = "$want" ] || [ "${K8SQUEST_ALLOW_CONTEXT:-}" = "1" ]; then
        return 0
    fi
    echo "[setup] REFUSING to run: kubectl context is '${ctx:-none}', expected '$want'." >&2
    echo "[setup] This level creates and deletes cluster-scoped objects. Run: kubectl config use-context $want" >&2
    echo "[setup] (or set K8SQUEST_ALLOW_CONTEXT=1 to override)" >&2
    return 1
}

need() {
    command -v "$1" >/dev/null 2>&1 || { echo "[setup] ERROR: '$1' is required but not installed" >&2; return 1; }
}

# retry <attempts> <sleep-seconds> <command...>
retry() {
    local n=$1 s=$2 i
    shift 2
    for ((i = 1; i <= n; i++)); do
        "$@" && return 0
        sleep "$s"
    done
    return 1
}

# wait_available <namespace> <timeout>   (all Deployments in the namespace)
wait_available() {
    kubectl wait --for=condition=Available deployment --all -n "$1" --timeout="$2" >/dev/null
}

ensure_metrics_server() {
    if kubectl get apiservice v1beta1.metrics.k8s.io >/dev/null 2>&1 \
        && kubectl wait --for=condition=Available apiservice/v1beta1.metrics.k8s.io --timeout=5s >/dev/null 2>&1; then
        return 0
    fi
    log "installing metrics-server ${METRICS_SERVER_VERSION}"
    retry 3 5 kubectl apply -f "https://github.com/kubernetes-sigs/metrics-server/releases/download/${METRICS_SERVER_VERSION}/components.yaml" >/dev/null || return 1
    # kind's kubelet serves a certificate the cluster CA did not sign
    if ! kubectl get deployment metrics-server -n kube-system -o jsonpath='{.spec.template.spec.containers[0].args}' | grep -q kubelet-insecure-tls; then
        kubectl patch deployment metrics-server -n kube-system --type=json \
            -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]' >/dev/null || return 1
    fi
    kubectl rollout status deployment/metrics-server -n kube-system --timeout=180s >/dev/null || return 1
    kubectl wait --for=condition=Available apiservice/v1beta1.metrics.k8s.io --timeout=180s >/dev/null
}

