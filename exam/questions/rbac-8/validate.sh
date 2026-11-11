#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

RULES=$(kubectl get role deploy-mgr -n "$NS" -o json 2>/dev/null)
[[ -n "$RULES" ]] || fail "role deploy-mgr does not exist"
[[ "$(echo "$RULES" | jq '.rules | length')" == "1" ]] || fail "role deploy-mgr must have exactly one rule"
G=$(echo "$RULES" | jq -r '.rules[0].apiGroups | sort | join(",")')
R=$(echo "$RULES" | jq -r '.rules[0].resources | sort | join(",")')
V=$(echo "$RULES" | jq -r '.rules[0].verbs | sort | join(",")')
[[ "$G" == "apps" ]] || fail "role deploy-mgr apiGroups are '$G', expected 'apps'"
[[ "$R" == "deployments" ]] || fail "role deploy-mgr resources are '$R', expected deployments"
[[ "$V" == "create,get,list" ]] || fail "role deploy-mgr verbs are '$V', expected create,get,list"
[[ "$(echo "$RULES" | jq '.rules[0] | has("resourceNames")')" == "false" ]] || fail "role deploy-mgr must not be limited to resource names"
echo "✅ Role deploy-mgr can create, get and list Deployments"
exit 0
