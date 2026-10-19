#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Heals the cluster, then changes --kubeconfig in the kube-scheduler static pod manifest to a
# path that does not exist, waits until the scheduler pod is not Ready, and deploys the
# workload (broken.yaml). The pristine manifest is in /root/k8squest-pristine/ on the node.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
need docker
heal_cluster

log "breaking the kube-scheduler manifest on $CP_NODE"
edit_node_file "$CP_NODE" "$MANIFESTS/kube-scheduler.yaml" 's#--kubeconfig=/etc/kubernetes/scheduler.conf#--kubeconfig=/etc/kubernetes/scheduler.cof#' 'scheduler.cof'
# wait until the running scheduler container is gone and its replacement is not Ready
end=$((SECONDS + 120))
until [ "$(kubectl get pods -n kube-system -l component=kube-scheduler -o jsonpath='{.items[0].status.containerStatuses[0].ready}' 2>/dev/null)" = false ]; do
    [ $SECONDS -lt $end ] || { echo "[setup] ERROR: the scheduler pod never went unready" >&2; exit 1; }
    sleep 2
done
kubectl apply -f broken.yaml
