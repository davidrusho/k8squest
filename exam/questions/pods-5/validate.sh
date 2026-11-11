#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

P=$(kubectl get pod envpod -n "$NS" -o json 2>/dev/null)
[[ -n "$P" ]] || fail "pod envpod does not exist in namespace $NS"
GOT=$(echo "$P" | jq -cS '.spec.containers[0].image | sub(":latest$";"")')
[[ "$GOT" == '"nginx"' ]] || fail "image is $GOT, expected "'"nginx"'
GOT=$(echo "$P" | jq -cS '[.spec.containers[0].env[]? | select(.name=="APP_ENV") | .value]')
[[ "$GOT" == '["prod"]' ]] || fail "APP_ENV values is $GOT, expected "'["prod"]'
echo "✅ Pod envpod has APP_ENV=prod"
exit 0
