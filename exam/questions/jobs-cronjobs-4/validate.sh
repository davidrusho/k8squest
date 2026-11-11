#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

J=$(kubectl get job manual-run -n "$NS" -o json 2>/dev/null)
[[ -n "$J" ]] || fail "job manual-run does not exist in namespace $NS"
GOT=$(echo "$J" | jq -cS '[.metadata.ownerReferences[]? | select(.kind=="CronJob" and .name=="backup")] | length')
[[ "$GOT" == '1' ]] || fail "ownerReferences to CronJob backup is $GOT, expected "'1'
GOT=$(echo "$J" | jq -cS '.metadata.annotations["cronjob.kubernetes.io/instantiate"]')
[[ "$GOT" == '"manual"' ]] || fail "instantiate annotation is $GOT, expected "'"manual"'
echo "✅ Job manual-run was created from CronJob backup"
exit 0
