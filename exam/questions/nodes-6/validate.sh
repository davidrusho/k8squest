#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

N=$(kubectl get node k8squest-control-plane -o json 2>/dev/null)
[[ "$(echo "$N" | jq -r .metadata.name)" == "k8squest-control-plane" ]] || fail "could not read node k8squest-control-plane"
[[ "$(echo "$N" | jq '[.spec.taints[]? | select(.key == "dedicated")] | length')" == "0" ]] || fail "the dedicated taint is still on the node"
BASE=$(kubectl get cm node-baseline -n "$NS" -o jsonpath='{.data.taints}' 2>/dev/null) || fail "the baseline ConfigMap node-baseline is missing"
CUR=$(echo "$N" | jq -c '[.spec.taints[]? | select(.key | startswith("node.kubernetes.io/") | not)]')
[[ "$CUR" == "$BASE" ]] || fail "the node's other taints changed: now '$CUR', were '$BASE'"
echo "✅ the dedicated taint is gone and the other taints are unchanged"
exit 0
