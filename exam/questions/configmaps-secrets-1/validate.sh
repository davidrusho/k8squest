#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

C=$(kubectl get cm app-config -n "$NS" -o json 2>/dev/null)
[[ -n "$C" ]] || fail "cm app-config does not exist in namespace $NS"
GOT=$(echo "$C" | jq -cS '.data')
[[ "$GOT" == '{"APP_DEBUG":"false","APP_ENV":"prod"}' ]] || fail "data is $GOT, expected "'{"APP_DEBUG":"false","APP_ENV":"prod"}'
echo "✅ ConfigMap app-config holds APP_ENV=prod and APP_DEBUG=false"
exit 0
