#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

N=$(kubectl get node k8squest-control-plane -o json 2>/dev/null)
[[ "$(echo "$N" | jq -r .metadata.name)" == "k8squest-control-plane" ]] || fail "could not read node k8squest-control-plane"
GOT=$(echo "$N" | jq -cS '[.spec.taints[]? | select(.key == "dedicated")]')
[[ "$GOT" == '[{"effect":"NoSchedule","key":"dedicated","value":"gpu"}]' ]] || fail "taints with key dedicated are $GOT, expected exactly dedicated=gpu:NoSchedule"
echo "✅ node k8squest-control-plane is tainted dedicated=gpu:NoSchedule"
exit 0
