#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Heals the cluster, deploys the workload (broken.yaml) while the API server still works, then
# changes --etcd-servers in the kube-apiserver static pod manifest to a port nothing listens on
# and waits until the API server stops answering. The pristine manifest is in /root/k8squest-pristine/.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
need docker
heal_cluster

kubectl apply -f broken.yaml
kubectl wait --for=condition=Available deployment/status-page -n "${NAMESPACE:-k8squest}" --timeout=120s >/dev/null

log "breaking the kube-apiserver manifest on $CP_NODE"
edit_node_file "$CP_NODE" "$MANIFESTS/kube-apiserver.yaml" 's#--etcd-servers=https://127.0.0.1:2379#--etcd-servers=https://127.0.0.1:2397#' 'etcd-servers=https://127.0.0.1:2397'
wait_api_down 120 || { echo "[setup] ERROR: the API server never stopped answering" >&2; exit 1; }
sleep 10
if api_ok; then echo "[setup] ERROR: the API server is answering again" >&2; exit 1; fi
