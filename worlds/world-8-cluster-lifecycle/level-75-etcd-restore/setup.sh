#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Puts the machines into the state before level 75: a working two-node cluster at
# v1.37.1 running the ledger Deployment and ConfigMap, no snapshot, and the identity of
# the etcd cluster recorded (a restore gives it a new one).
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
require_vms
ensure_packages "$K8S_NEW_MINOR" "$K8S_NEW_PKG" "$K8S_NEW"
log "resetting both machines"
reset_nodes
prep_nodes
log "building the cluster"
cluster_up "$K8S_NEW"
ensure_namespace
apply_workload broken.yaml
kc -n "${NAMESPACE:-k8squest}" rollout status deployment/ledger --timeout=180s >/dev/null
remember 75-ledger-uid "$(kc -n "${NAMESPACE:-k8squest}" get deployment ledger -o jsonpath='{.metadata.uid}')"
ID=$(etcd_cluster_id)
[ -n "$ID" ] || { echo "[setup] ERROR: could not read the etcd cluster ID" >&2; exit 1; }
remember 75-etcd-cluster-id "$ID"
vm_sh "$CP_VM" 'mkdir -p /var/backups/etcd'
log "the ledger is running; etcd cluster $ID has no backup"
