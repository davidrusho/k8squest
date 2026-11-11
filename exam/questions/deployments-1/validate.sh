#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

D=$(kubectl get deploy web -n "$NS" -o json 2>/dev/null)
[[ -n "$D" ]] || fail "deploy web does not exist in namespace $NS"
GOT=$(echo "$D" | jq -cS '.spec.template.spec.containers[0].image | sub(":latest$";"")')
[[ "$GOT" == '"nginx"' ]] || fail "image is $GOT, expected "'"nginx"'
GOT=$(echo "$D" | jq -cS '.spec.replicas')
[[ "$GOT" == '3' ]] || fail "replicas is $GOT, expected "'3'
echo "✅ Deployment web runs nginx with 3 replicas"
exit 0
