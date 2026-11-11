#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

kubectl get deploy web -n "$NS" > /dev/null 2>&1 || fail "Deployment web does not exist in namespace $NS"
SA=$(kubectl get deploy web -n "$NS" -o jsonpath='{.spec.template.spec.serviceAccountName}' 2>/dev/null)
[[ "$SA" == "app-sa" ]] || fail "Deployment web uses ServiceAccount '${SA:-default}', expected app-sa"
echo "✅ Deployment web runs as ServiceAccount app-sa"
exit 0
