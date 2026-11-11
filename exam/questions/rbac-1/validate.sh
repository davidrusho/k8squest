#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

RULES=$(kubectl get role pod-reader -n "$NS" -o json 2>/dev/null)
[[ -n "$RULES" ]] || fail "role pod-reader does not exist"
[[ "$(echo "$RULES" | jq '.rules | length')" == "1" ]] || fail "role pod-reader must have exactly one rule"
G=$(echo "$RULES" | jq -r '.rules[0].apiGroups | sort | join(",")')
R=$(echo "$RULES" | jq -r '.rules[0].resources | sort | join(",")')
V=$(echo "$RULES" | jq -r '.rules[0].verbs | sort | join(",")')
[[ "$G" == "" ]] || fail "role pod-reader apiGroups are '$G', expected ''"
[[ "$R" == "pods" ]] || fail "role pod-reader resources are '$R', expected pods"
[[ "$V" == "get,list,watch" ]] || fail "role pod-reader verbs are '$V', expected get,list,watch"
[[ "$(echo "$RULES" | jq '.rules[0] | has("resourceNames")')" == "false" ]] || fail "role pod-reader must not be limited to resource names"
echo "✅ Role pod-reader can get, list and watch pods"
exit 0
