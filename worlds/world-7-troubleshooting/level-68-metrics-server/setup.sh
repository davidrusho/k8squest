#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Heals the cluster, makes sure metrics-server v0.9.0 is installed (worlds/_shared/lib.sh), deploys
# the workload (broken.yaml), then removes --kubelet-insecure-tls from metrics-server. The pod is
# scaled to 0 and back, because a rolling update would keep the old, working pod serving until
# the new one is Ready (and it never would be). heal_cluster puts the argument back.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
need docker
heal_cluster
ensure_metrics_server

kubectl apply -f broken.yaml

log "removing --kubelet-insecure-tls from metrics-server"
ARGS=$(kubectl -n kube-system get deployment metrics-server -o jsonpath='{range .spec.template.spec.containers[0].args[*]}{@}{"\n"}{end}')
IDX=$(printf '%s\n' "$ARGS" | grep -n -x -e '--kubelet-insecure-tls' | head -1 | cut -d: -f1)
[ -n "$IDX" ] || { echo "[setup] ERROR: --kubelet-insecure-tls is not in the metrics-server args" >&2; exit 1; }
kubectl -n kube-system scale deployment metrics-server --replicas=0 >/dev/null
kubectl -n kube-system patch deployment metrics-server --type=json \
    -p "[{\"op\":\"remove\",\"path\":\"/spec/template/spec/containers/0/args/$((IDX - 1))\"}]" >/dev/null
kubectl -n kube-system scale deployment metrics-server --replicas=1 >/dev/null
# the APIService turns unavailable once the pod is gone and the new one is not Ready
end=$((SECONDS + 120))
until ! kubectl top nodes >/dev/null 2>&1; do
    [ $SECONDS -lt $end ] || { echo "[setup] ERROR: kubectl top still works" >&2; exit 1; }
    sleep 3
done
