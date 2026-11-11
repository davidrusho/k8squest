#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

D=$(kubectl get deploy web -n "$NS" -o json 2>/dev/null)
[[ -n "$D" ]] || fail "deploy web does not exist in namespace $NS"
GOT=$(echo "$D" | jq -cS '[.spec.template.spec.containers[0].env[]? | select(.name=="APP_ENV") | .value]')
[[ "$GOT" == '["prod"]' ]] || fail "APP_ENV values is $GOT, expected "'["prod"]'
echo "✅ Deployment web has APP_ENV=prod"
exit 0
