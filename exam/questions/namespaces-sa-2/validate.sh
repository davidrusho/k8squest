#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

kubectl get sa app-sa -n "$NS" > /dev/null 2>&1 || fail "ServiceAccount app-sa does not exist in namespace $NS"
echo "✅ ServiceAccount app-sa exists"
exit 0
