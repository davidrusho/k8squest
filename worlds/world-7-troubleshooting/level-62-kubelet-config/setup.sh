#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Heals the cluster, then points authentication.x509.clientCAFile in worker2's kubelet
# config at a file that does not exist, restarts the kubelet (which now exits at start-up)
# and waits for NotReady. The pristine config is in /root/k8squest-pristine/ on the node.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
need docker
heal_cluster

log "breaking the kubelet configuration on $WORKER2"
edit_node_file "$WORKER2" /var/lib/kubelet/config.yaml 's#clientCAFile: /etc/kubernetes/pki/ca.crt$#clientCAFile: /etc/kubernetes/pki/ca.crtt#' 'ca.crtt'
node_sh "$WORKER2" "systemctl restart kubelet" >/dev/null 2>&1 || true   # it exits at start-up: the restart "fails"
wait_node_state "$WORKER2" NotReady 150 || { echo "[setup] ERROR: $WORKER2 never became NotReady" >&2; exit 1; }
kubectl apply -f broken.yaml
