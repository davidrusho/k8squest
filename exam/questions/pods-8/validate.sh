#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

# positive control: Pod web2 must still be there, so an unreachable cluster or a wiped namespace does not read as "web is gone"
kubectl get pod web2 -n "$NS" > /dev/null 2>&1 || fail "Pod web2 does not exist; it must be left running"
ERR=$(kubectl get pod web -n "$NS" 2>&1 > /dev/null)
if [[ -z "$ERR" ]]; then
  fail "Pod web still exists in namespace $NS"
fi
[[ "$ERR" == *"NotFound"* ]] || fail "could not confirm that Pod web is gone: $ERR"
echo "✅ Pod web is gone and Pod web2 is still there"
exit 0
