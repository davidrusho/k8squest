#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

C=$(kubectl get cronjob backup -n "$NS" -o json 2>/dev/null)
[[ -n "$C" ]] || fail "cronjob backup does not exist in namespace $NS"
GOT=$(echo "$C" | jq -cS '.spec.suspend')
[[ "$GOT" == 'true' ]] || fail "spec.suspend is $GOT, expected "'true'
echo "✅ CronJob backup is suspended"
exit 0
