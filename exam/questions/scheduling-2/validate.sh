#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

P=$(kubectl get pod req -n "$NS" -o json 2>/dev/null)
[[ -n "$P" ]] || fail "pod req does not exist in namespace $NS"
GOT=$(echo "$P" | jq -cS '.spec.containers[0].image | sub(":latest$";"")')
[[ "$GOT" == '"nginx"' ]] || fail "image is $GOT, expected "'"nginx"'
GOT=$(echo "$P" | jq -cS '.spec.affinity.nodeAffinity.requiredDuringSchedulingIgnoredDuringExecution')
[[ "$GOT" == '{"nodeSelectorTerms":[{"matchExpressions":[{"key":"disk","operator":"In","values":["ssd"]}]}]}' ]] || fail "required node affinity is $GOT, expected "'{"nodeSelectorTerms":[{"matchExpressions":[{"key":"disk","operator":"In","values":["ssd"]}]}]}'
GOT=$(echo "$P" | jq -cS '.spec.affinity.nodeAffinity | keys')
[[ "$GOT" == '["requiredDuringSchedulingIgnoredDuringExecution"]' ]] || fail "nodeAffinity fields is $GOT, expected "'["requiredDuringSchedulingIgnoredDuringExecution"]'
echo "✅ Pod req requires disk In (ssd) through node affinity"
exit 0
