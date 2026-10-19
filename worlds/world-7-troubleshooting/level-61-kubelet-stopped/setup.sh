#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Heals the cluster, then stops and disables the kubelet on the first worker and waits
# until the node is NotReady, then deploys the pinned workload (broken.yaml).
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
need docker
heal_cluster

log "stopping and disabling the kubelet on $WORKER1"
node_sh "$WORKER1" "systemctl disable --now kubelet" >/dev/null 2>&1
# The node controller marks the node NotReady after its grace period (about 50 seconds).
wait_node_state "$WORKER1" NotReady 150 || { echo "[setup] ERROR: $WORKER1 never became NotReady" >&2; exit 1; }
kubectl apply -f broken.yaml
