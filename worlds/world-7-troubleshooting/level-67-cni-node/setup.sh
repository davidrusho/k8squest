#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Heals the cluster, then (1) labels the control plane and worker1 k8squest.io/cni=true,
# (2) adds that label as a nodeSelector to the kindnet DaemonSet, so the DaemonSet controller
# removes the kindnet pod from worker2, and (3) removes worker2's CNI config. The node goes
# NotReady with "cni plugin not initialized". heal_cluster undoes all three.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
need docker
heal_cluster

log "removing kindnet from $WORKER2"
kubectl label node "$CP_NODE" "$WORKER1" k8squest.io/cni=true --overwrite >/dev/null
kubectl -n kube-system patch daemonset kindnet --type=merge \
    -p '{"spec":{"template":{"spec":{"nodeSelector":{"k8squest.io/cni":"true"}}}}}' >/dev/null
end=$((SECONDS + 90))
until [ -z "$(kubectl -n kube-system get pods -l app=kindnet --field-selector "spec.nodeName=$WORKER2" --no-headers 2>/dev/null)" ]; do
    [ $SECONDS -lt $end ] || { echo "[setup] ERROR: the kindnet pod on $WORKER2 did not go away" >&2; exit 1; }
    sleep 2
done
node_sh "$WORKER2" "rm -f /etc/cni/net.d/10-kindnet.conflist"
wait_node_state "$WORKER2" NotReady 90 || { echo "[setup] ERROR: $WORKER2 never became NotReady" >&2; exit 1; }
kubectl apply -f broken.yaml
