#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

RULES=$(kubectl get clusterrole node-reader -o json 2>/dev/null)
[[ -n "$RULES" ]] || fail "clusterrole node-reader does not exist"
[[ "$(echo "$RULES" | jq '.rules | length')" == "1" ]] || fail "clusterrole node-reader must have exactly one rule"
G=$(echo "$RULES" | jq -r '.rules[0].apiGroups | sort | join(",")')
R=$(echo "$RULES" | jq -r '.rules[0].resources | sort | join(",")')
V=$(echo "$RULES" | jq -r '.rules[0].verbs | sort | join(",")')
[[ "$G" == "" ]] || fail "clusterrole node-reader apiGroups are '$G', expected ''"
[[ "$R" == "nodes" ]] || fail "clusterrole node-reader resources are '$R', expected nodes"
[[ "$V" == "get,list,watch" ]] || fail "clusterrole node-reader verbs are '$V', expected get,list,watch"
[[ "$(echo "$RULES" | jq '.rules[0] | has("resourceNames")')" == "false" ]] || fail "clusterrole node-reader must not be limited to resource names"
B=$(kubectl get clusterrolebinding read-nodes -o json 2>/dev/null)
[[ -n "$B" ]] || fail "clusterrolebinding read-nodes does not exist"
RR=$(echo "$B" | jq -r '"\(.roleRef.apiGroup)/\(.roleRef.kind)/\(.roleRef.name)"')
[[ "$RR" == "rbac.authorization.k8s.io/ClusterRole/node-reader" ]] || fail "clusterrolebinding read-nodes roleRef is $RR, expected ClusterRole/node-reader"
SUBJ=$(echo "$B" | jq -c '[.subjects[]? | del(.apiGroup)]')
EXP='[{"kind":"User","name":"jane"}]'
[[ "$SUBJ" == "$EXP" ]] || fail "clusterrolebinding read-nodes subjects are $SUBJ, expected exactly $EXP"
echo "✅ ClusterRole node-reader can get, list and watch nodes and is bound to user jane"
exit 0
