#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

B=$(kubectl get rolebinding read-pods -n "$NS" -o json 2>/dev/null)
[[ -n "$B" ]] || fail "rolebinding read-pods does not exist"
RR=$(echo "$B" | jq -r '"\(.roleRef.apiGroup)/\(.roleRef.kind)/\(.roleRef.name)"')
[[ "$RR" == "rbac.authorization.k8s.io/Role/pod-reader" ]] || fail "rolebinding read-pods roleRef is $RR, expected Role/pod-reader"
SUBJ=$(echo "$B" | jq -c '[.subjects[]? | del(.apiGroup)]')
EXP='[{"kind":"User","name":"jane"}]'
[[ "$SUBJ" == "$EXP" ]] || fail "rolebinding read-pods subjects are $SUBJ, expected exactly $EXP"
echo "✅ RoleBinding read-pods binds Role pod-reader to user jane"
exit 0
