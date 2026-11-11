#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

B=$(kubectl get rolebinding read-pods-sa -n "$NS" -o json 2>/dev/null)
[[ -n "$B" ]] || fail "rolebinding read-pods-sa does not exist"
RR=$(echo "$B" | jq -r '"\(.roleRef.apiGroup)/\(.roleRef.kind)/\(.roleRef.name)"')
[[ "$RR" == "rbac.authorization.k8s.io/Role/pod-reader" ]] || fail "rolebinding read-pods-sa roleRef is $RR, expected Role/pod-reader"
SUBJ=$(echo "$B" | jq -c '[.subjects[]? | del(.apiGroup)]')
EXP='[{"kind":"ServiceAccount","name":"app-sa","namespace":"'"$NS"'"}]'
[[ "$SUBJ" == "$EXP" ]] || fail "rolebinding read-pods-sa subjects are $SUBJ, expected exactly $EXP"
echo "✅ RoleBinding read-pods-sa binds Role pod-reader to ServiceAccount app-sa"
exit 0
