#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

P=$(kubectl get pod ssdpod -n "$NS" -o json 2>/dev/null)
[[ -n "$P" ]] || fail "pod ssdpod does not exist in namespace $NS"
GOT=$(echo "$P" | jq -cS '.spec.containers[0].image | sub(":latest$";"")')
[[ "$GOT" == '"nginx"' ]] || fail "image is $GOT, expected "'"nginx"'
GOT=$(echo "$P" | jq -cS '.spec.nodeSelector')
[[ "$GOT" == '{"disk":"ssd"}' ]] || fail "nodeSelector is $GOT, expected "'{"disk":"ssd"}'
echo "✅ Pod ssdpod has nodeSelector disk=ssd"
exit 0
