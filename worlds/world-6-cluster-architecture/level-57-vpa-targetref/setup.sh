#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Installs metrics-server and the Vertical Pod Autoscaler recommender (once), then
# deploys the workload and the VPA that points at the wrong target.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
NS="${NAMESPACE:-k8squest}"

ensure_vpa

# VPA objects are not covered by `kubectl delete all`
kubectl delete vpa --all -n "$NS" --ignore-not-found >/dev/null
kubectl apply -f broken.yaml
