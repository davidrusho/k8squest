#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

P=$(kubectl get pod web -n "$NS" -o json 2>/dev/null)
[[ -n "$P" ]] || fail "pod web does not exist in namespace $NS"
GOT=$(echo "$P" | jq -cS '.spec.containers[0].image | sub(":latest$";"")')
[[ "$GOT" == '"nginx"' ]] || fail "image is $GOT, expected "'"nginx"'
GOT=$(echo "$P" | jq -cS '.spec.containers | length')
[[ "$GOT" == '1' ]] || fail "number of containers is $GOT, expected "'1'
echo "✅ Pod web runs nginx"
exit 0
