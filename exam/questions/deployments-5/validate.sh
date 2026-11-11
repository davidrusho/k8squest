#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

D=$(kubectl get deploy web -n "$NS" -o json 2>/dev/null)
[[ -n "$D" ]] || fail "deploy web does not exist in namespace $NS"
GOT=$(echo "$D" | jq -cS '.spec.template.spec.containers | map(.image)')
[[ "$GOT" == '["nginx:1.21"]' ]] || fail "container images is $GOT, expected "'["nginx:1.21"]'
echo "✅ Deployment web matches revision 1 again"
exit 0
