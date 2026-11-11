#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

C=$(kubectl get pvc data-pvc -n "$NS" -o json 2>/dev/null)
[[ -n "$C" ]] || fail "pvc data-pvc does not exist"
GOT=$(echo "$C" | jq -cS '.spec.resources.requests.storage')
[[ "$GOT" == '"500Mi"' ]] || fail "requested storage is $GOT, expected "'"500Mi"'
GOT=$(echo "$C" | jq -cS '.spec.accessModes')
[[ "$GOT" == '["ReadWriteOnce"]' ]] || fail "accessModes is $GOT, expected "'["ReadWriteOnce"]'
SC=$(echo "$C" | jq -c '.spec.storageClassName')
[[ "$SC" == "null" || "$SC" == '"standard"' ]] || fail "storageClassName is $SC, expected unset (default class) or standard"
echo "✅ PVC data-pvc requests 500Mi ReadWriteOnce from the default class"
exit 0
