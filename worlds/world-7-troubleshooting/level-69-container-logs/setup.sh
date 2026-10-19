#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Heals the cluster, deploys the broken application (broken.yaml) and waits until the
# invoice-api container has crashed at least once.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
need docker
heal_cluster

kubectl apply -f broken.yaml
NS="${NAMESPACE:-k8squest}"
end=$((SECONDS + 120))
until [ "$(kubectl get pods -n "$NS" -l app=invoice-api -o jsonpath='{.items[0].status.containerStatuses[?(@.name=="invoice-api")].restartCount}' 2>/dev/null)" -ge 1 ] 2>/dev/null; do
    [ $SECONDS -lt $end ] || { echo "[setup] ERROR: invoice-api never crashed" >&2; exit 1; }
    sleep 2
done
