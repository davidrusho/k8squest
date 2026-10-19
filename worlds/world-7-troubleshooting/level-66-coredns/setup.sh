#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Heals the cluster, deploys the workload (broken.yaml), then breaks CoreDNS twice: the zone in
# the Corefile's kubernetes plugin is mistyped (cluster.local -> cluster.locl) and the
# Deployment is scaled to 0. The stock Corefile and replica count are in /root/k8squest-pristine/.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
need docker
heal_cluster

kubectl apply -f broken.yaml
kubectl wait --for=condition=Ready pod/dns-client -n "${NAMESPACE:-k8squest}" --timeout=120s >/dev/null

log "breaking CoreDNS"
COREFILE=$(kubectl -n kube-system get configmap coredns -o jsonpath='{.data.Corefile}')
BAD=$(printf '%s\n' "$COREFILE" | sed 's/kubernetes cluster\.local /kubernetes cluster.locl /')
[ "$BAD" != "$COREFILE" ] || { echo "[setup] ERROR: could not edit the Corefile" >&2; exit 1; }
TMP=$(mktemp)
printf '%s\n' "$BAD" > "$TMP"
kubectl -n kube-system create configmap coredns --from-file=Corefile="$TMP" --dry-run=client -o yaml | kubectl replace -f - >/dev/null
rm -f "$TMP"
kubectl -n kube-system scale deployment coredns --replicas=0 >/dev/null
end=$((SECONDS + 90))
until [ "$(kubectl -n kube-system get pods -l k8s-app=kube-dns --no-headers 2>/dev/null | wc -l | tr -d ' ')" = 0 ]; do
    [ $SECONDS -lt $end ] || { echo "[setup] ERROR: CoreDNS pods did not go away" >&2; exit 1; }
    sleep 2
done
