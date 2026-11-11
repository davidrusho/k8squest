#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

D=$(kubectl get deploy web -n "$NS" -o json 2>/dev/null)
[[ -n "$D" ]] || fail "deploy web does not exist in namespace $NS"
GOT=$(echo "$D" | jq -cS '.spec.template.spec.containers | map(select(.name=="nginx") | .image)')
[[ "$GOT" == '["nginx:1.27-alpine"]' ]] || fail "image of container nginx is $GOT, expected "'["nginx:1.27-alpine"]'
echo "✅ container nginx of Deployment web uses nginx:1.27-alpine"
exit 0
