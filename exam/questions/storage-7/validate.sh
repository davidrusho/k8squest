#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

V=$(kubectl get pv pv1 -o json 2>/dev/null)
[[ -n "$V" ]] || fail "pv pv1 does not exist"
GOT=$(echo "$V" | jq -cS '.spec.persistentVolumeReclaimPolicy')
[[ "$GOT" == '"Retain"' ]] || fail "reclaim policy is $GOT, expected "'"Retain"'
GOT=$(echo "$V" | jq -cS '.spec.capacity.storage')
[[ "$GOT" == '"1Gi"' ]] || fail "capacity is $GOT, expected "'"1Gi"'
GOT=$(echo "$V" | jq -cS '.spec.accessModes')
[[ "$GOT" == '["ReadWriteOnce"]' ]] || fail "accessModes is $GOT, expected "'["ReadWriteOnce"]'
GOT=$(echo "$V" | jq -cS '.spec.storageClassName')
[[ "$GOT" == '"manual"' ]] || fail "storageClassName is $GOT, expected "'"manual"'
GOT=$(echo "$V" | jq -cS '.spec.hostPath.path')
[[ "$GOT" == '"/mnt/data"' ]] || fail "hostPath path is $GOT, expected "'"/mnt/data"'
echo "✅ PersistentVolume pv1 has reclaim policy Retain and is otherwise unchanged"
exit 0
