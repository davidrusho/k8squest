#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Installs cert-manager (once) and deploys the broken Issuer/Certificate pair.
set -e
cd "$(dirname "$0")"
. ../_shared/lib.sh
require_game_context
NS="${NAMESPACE:-k8squest}"
need kubectl

ensure_cert_manager

# Certificates, Issuers and the Secret cert-manager writes are not removed by
# the engine's `kubectl delete all`, so clear any earlier attempt.
kubectl delete certificate web-cert -n "$NS" --ignore-not-found >/dev/null
kubectl delete issuer selfsigned-issuer -n "$NS" --ignore-not-found >/dev/null
kubectl delete secret web-cert-tls -n "$NS" --ignore-not-found >/dev/null
# a ClusterIssuer of this exact name is what a "fix" by creating one leaves behind
kubectl delete clusterissuer selfsigned-issuer --ignore-not-found >/dev/null

retry 12 5 kubectl apply -f broken.yaml
