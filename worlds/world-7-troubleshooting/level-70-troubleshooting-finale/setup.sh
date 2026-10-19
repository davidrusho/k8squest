#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Heals the cluster, removes an old snapshot, deploys the marker ConfigMap and the shop
# (broken.yaml), makes sure some shop pods run on the first worker, then stops (not disables)
# that worker's kubelet and waits for NotReady. heal_cluster starts it again for the next level.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
need docker
heal_cluster
NS="${NAMESPACE:-k8squest}"

node_sh "$CP_NODE" "rm -f $SNAPSHOT_PATH $SNAPSHOT_PATH.part"
kubectl apply -f broken.yaml
kubectl rollout status deployment/shop -n "$NS" --timeout=120s >/dev/null
# the finale needs shop pods on the worker that is about to be lost
for attempt in 1 2 3 4 5; do
    pod_nodes "$NS" app=shop | grep -q " $WORKER1\$" && break
    log "no shop pod on $WORKER1 yet; restarting the shop"
    kubectl rollout restart deployment/shop -n "$NS" >/dev/null
    kubectl rollout status deployment/shop -n "$NS" --timeout=120s >/dev/null
done
pod_nodes "$NS" app=shop | grep -q " $WORKER1\$" || { echo "[setup] ERROR: the scheduler placed no shop pod on $WORKER1" >&2; exit 1; }

log "stopping the kubelet on $WORKER1"
node_sh "$WORKER1" "systemctl stop kubelet" >/dev/null 2>&1
wait_node_state "$WORKER1" NotReady 150 || { echo "[setup] ERROR: $WORKER1 never became NotReady" >&2; exit 1; }
