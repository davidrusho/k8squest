#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Heals the cluster, then changes the image tag in the kube-controller-manager static pod
# manifest to one that does not exist, waits until the controller-manager pod is not Ready,
# and deploys the workload (broken.yaml). The pristine manifest is in /root/k8squest-pristine/.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
need docker
heal_cluster

log "breaking the kube-controller-manager manifest on $CP_NODE"
edit_node_file "$CP_NODE" "$MANIFESTS/kube-controller-manager.yaml" 's#kube-controller-manager:v1\.37\.0#kube-controller-manager:v1.73.0#' 'kube-controller-manager:v1.73.0'
end=$((SECONDS + 120))
until [ "$(kubectl get pods -n kube-system -l component=kube-controller-manager -o jsonpath='{.items[0].status.containerStatuses[0].ready}' 2>/dev/null)" = false ]; do
    [ $SECONDS -lt $end ] || { echo "[setup] ERROR: the controller-manager pod never went unready" >&2; exit 1; }
    sleep 2
done
kubectl apply -f broken.yaml
