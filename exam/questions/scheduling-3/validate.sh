#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

P=$(kubectl get pod pref -n "$NS" -o json 2>/dev/null)
[[ -n "$P" ]] || fail "pod pref does not exist in namespace $NS"
GOT=$(echo "$P" | jq -cS '.spec.containers[0].image | sub(":latest$";"")')
[[ "$GOT" == '"nginx"' ]] || fail "image is $GOT, expected "'"nginx"'
GOT=$(echo "$P" | jq -cS '.spec.affinity.nodeAffinity | keys')
[[ "$GOT" == '["preferredDuringSchedulingIgnoredDuringExecution"]' ]] || fail "nodeAffinity fields is $GOT, expected "'["preferredDuringSchedulingIgnoredDuringExecution"]'
GOT=$(echo "$P" | jq -cS '.spec.affinity.nodeAffinity.preferredDuringSchedulingIgnoredDuringExecution | map(.preference)')
[[ "$GOT" == '[{"matchExpressions":[{"key":"disk","operator":"In","values":["ssd"]}]}]' ]] || fail "preferred terms is $GOT, expected "'[{"matchExpressions":[{"key":"disk","operator":"In","values":["ssd"]}]}]'
GOT=$(echo "$P" | jq -cS '.spec.nodeSelector // {}')
[[ "$GOT" == '{}' ]] || fail "nodeSelector is $GOT, expected "'{}'
echo "✅ Pod pref prefers nodes with disk=ssd"
exit 0
