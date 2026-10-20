#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Puts the machines into the state before level 74: a two-node cluster at Kubernetes
# v1.36.5 (kubeadm, kubelet and kubectl v1.36.5 on both machines, the apt repository on
# v1.36), Flannel installed, and the orders Deployment running.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
require_vms
# the v1.37 images are pulled first, so the upgrade the player runs does not download them
ensure_packages "$K8S_NEW_MINOR" "$K8S_NEW_PKG" "$K8S_NEW"
log "installing Kubernetes $K8S_OLD on both machines"
ensure_packages "$K8S_OLD_MINOR" "$K8S_OLD_PKG" "$K8S_OLD" no-etcd-tools
log "resetting both machines"
reset_nodes
prep_nodes
log "building a $K8S_OLD cluster"
cluster_up "$K8S_OLD"
ensure_namespace
apply_workload broken.yaml
kc -n "${NAMESPACE:-k8squest}" rollout status deployment/orders --timeout=180s >/dev/null
remember 74-orders-uid "$(kc -n "${NAMESPACE:-k8squest}" get deployment orders -o jsonpath='{.metadata.uid}')"
log "the cluster is at $K8S_OLD with the orders workload"
