#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

P=$(kubectl get pod pvcpod -n "$NS" -o json 2>/dev/null)
[[ -n "$P" ]] || fail "pod pvcpod does not exist"
GOT=$(echo "$P" | jq -cS '.spec.containers[0].image | sub(":latest$";"")')
[[ "$GOT" == '"nginx"' ]] || fail "image is $GOT, expected "'"nginx"'
GOT=$(echo "$P" | jq -cS '[.spec.volumes[]? | select(.persistentVolumeClaim.claimName=="data-pvc") | .name] as $v | [.spec.containers[0].volumeMounts[]? | select(.mountPath=="/data" and (.name as $n | any($v[]; . == $n)))] | length')
[[ "$GOT" == '1' ]] || fail "mounts of PVC data-pvc at /data is $GOT, expected "'1'
echo "✅ Pod pvcpod mounts PVC data-pvc at /data"
exit 0
