#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Needs the shared Gateway web-gw (Gateway API + Envoy Gateway), plus a second
# namespace, k8squest-backend, that this level creates and recreates from scratch.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
NS="${NAMESPACE:-k8squest}"

ensure_gateway

kubectl delete httproute --all -n "$NS" --ignore-not-found >/dev/null
kubectl delete namespace k8squest-backend --ignore-not-found --wait=true --timeout=150s >/dev/null
kubectl apply -f broken.yaml
