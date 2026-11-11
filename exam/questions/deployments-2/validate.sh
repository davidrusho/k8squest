#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

D=$(kubectl get deploy web -n "$NS" -o json 2>/dev/null)
[[ -n "$D" ]] || fail "deploy web does not exist in namespace $NS"
GOT=$(echo "$D" | jq -cS '.spec.replicas')
[[ "$GOT" == '5' ]] || fail "replicas is $GOT, expected "'5'
echo "✅ Deployment web has 5 replicas"
exit 0
