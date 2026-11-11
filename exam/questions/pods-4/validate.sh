#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

P=$(kubectl get pod fe -n "$NS" -o json 2>/dev/null)
[[ -n "$P" ]] || fail "pod fe does not exist in namespace $NS"
GOT=$(echo "$P" | jq -cS '.spec.containers[0].image | sub(":latest$";"")')
[[ "$GOT" == '"nginx"' ]] || fail "image is $GOT, expected "'"nginx"'
GOT=$(echo "$P" | jq -cS '.spec.containers[0].ports | map(.containerPort)')
[[ "$GOT" == '[80]' ]] || fail "container ports is $GOT, expected "'[80]'
GOT=$(echo "$P" | jq -cS '.metadata.labels | {tier, env}')
[[ "$GOT" == '{"env":"prod","tier":"frontend"}' ]] || fail "labels tier and env is $GOT, expected "'{"env":"prod","tier":"frontend"}'
echo "✅ Pod fe has port 80 and labels tier=frontend, env=prod"
exit 0
