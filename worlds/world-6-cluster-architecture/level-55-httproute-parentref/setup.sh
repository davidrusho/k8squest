#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Installs Gateway API CRDs + Envoy Gateway (once), makes sure the shared Gateway
# web-gw exists, then deploys the broken HTTPRoute.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
NS="${NAMESPACE:-k8squest}"

ensure_gateway

kubectl delete httproute --all -n "$NS" --ignore-not-found >/dev/null
kubectl delete referencegrant --all -n "$NS" --ignore-not-found >/dev/null
kubectl apply -f broken.yaml
