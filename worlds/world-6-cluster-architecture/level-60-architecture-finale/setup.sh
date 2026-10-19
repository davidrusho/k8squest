#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# The finale combines three World 6 components: cert-manager, the Gateway
# (Gateway API + Envoy Gateway) and RBAC. Install what is missing, clear earlier
# attempts, then deploy the broken state.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
NS="${NAMESPACE:-k8squest}"

ensure_cert_manager
ensure_gateway

kubectl delete certificate platform-cert -n "$NS" --ignore-not-found >/dev/null
kubectl delete issuer platform-issuer platform-issuer-ca -n "$NS" --ignore-not-found >/dev/null
kubectl delete secret platform-cert-tls -n "$NS" --ignore-not-found >/dev/null
kubectl delete httproute --all -n "$NS" --ignore-not-found >/dev/null
delete_sa_bindings "$NS" probe-sa
kubectl delete rolebinding probe-binding -n "$NS" --ignore-not-found >/dev/null
kubectl delete role settings-reader -n "$NS" --ignore-not-found >/dev/null
kubectl delete serviceaccount probe-sa -n "$NS" --ignore-not-found >/dev/null
kubectl delete configmap platform-settings -n "$NS" --ignore-not-found >/dev/null

retry 12 5 kubectl apply -f broken.yaml
