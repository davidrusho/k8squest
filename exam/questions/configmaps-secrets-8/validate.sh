#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

P=$(kubectl get pod secpod -n "$NS" -o json 2>/dev/null)
[[ -n "$P" ]] || fail "pod secpod does not exist in namespace $NS"
GOT=$(echo "$P" | jq -cS '.spec.containers[0].image | sub(":latest$";"")')
[[ "$GOT" == '"nginx"' ]] || fail "image is $GOT, expected "'"nginx"'
GOT=$(echo "$P" | jq -cS '[.spec.volumes[]? | select(.secret.secretName=="db-creds") | .name] as $v | [.spec.containers[0].volumeMounts[]? | select(.mountPath=="/etc/creds" and (.name as $n | any($v[]; . == $n)))] | length')
[[ "$GOT" == '1' ]] || fail "mounts of Secret db-creds at /etc/creds is $GOT, expected "'1'
echo "✅ Pod secpod mounts Secret db-creds at /etc/creds"
exit 0
