#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Puts the machines into the state before level 76: a working two-node cluster at
# v1.37.1 where the control plane may run workloads, the web Deployment (4 replicas,
# some of them on the worker) and its PodDisruptionBudget running. The UIDs of the web
# pods that run on the worker are recorded: the level is done when none of them exists.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
require_vms
NS="${NAMESPACE:-k8squest}"
ensure_packages "$K8S_NEW_MINOR" "$K8S_NEW_PKG" "$K8S_NEW"
log "resetting both machines"
reset_nodes
prep_nodes
log "building the cluster"
cluster_up "$K8S_NEW"
# https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/create-cluster-kubeadm/#control-plane-node-isolation
kc taint node "$CP_NODE" node-role.kubernetes.io/control-plane- >/dev/null
ensure_namespace
apply_workload broken.yaml
kc -n "$NS" rollout status deployment/web --timeout=180s >/dev/null
worker_pods() {
    kc -n "$NS" get pods -l app=web -o jsonpath='{range .items[*]}{.spec.nodeName}{" "}{.metadata.uid}{"\n"}{end}' 2>/dev/null \
        | awk -v n="$WK_NODE" '$1 == n {print $2}'
}
# the level needs web pods on the worker
for attempt in 1 2 3 4 5; do
    [ -n "$(worker_pods)" ] && break
    log "no web pod on $WK_NODE yet; restarting the Deployment"
    kc -n "$NS" rollout restart deployment/web >/dev/null
    kc -n "$NS" rollout status deployment/web --timeout=180s >/dev/null
done
[ -n "$(worker_pods)" ] || { echo "[setup] ERROR: the scheduler placed no web pod on $WK_NODE" >&2; exit 1; }
remember 76-worker-pod-uids "$(worker_pods | tr '\n' ' ')"
log "web runs on both nodes; $(worker_pods | wc -l | tr -d ' ') pod(s) on $WK_NODE"
