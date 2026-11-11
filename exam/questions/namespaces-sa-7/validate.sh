#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

if kubectl get ns devns > /dev/null 2>&1; then
  TS=$(kubectl get ns devns -o jsonpath='{.metadata.deletionTimestamp}' 2>/dev/null)
  [[ -n "$TS" ]] || fail "Namespace devns still exists"
fi
echo "✅ namespace devns is deleted"
exit 0
