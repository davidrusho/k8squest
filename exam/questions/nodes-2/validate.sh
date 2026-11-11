#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

N=$(kubectl get node k8squest-control-plane -o json 2>/dev/null)
[[ "$(echo "$N" | jq -r .metadata.name)" == "k8squest-control-plane" ]] || fail "could not read node k8squest-control-plane"
[[ "$(echo "$N" | jq '.metadata.labels | has("disk")')" == "false" ]] || fail "node still has a label named disk"
echo "✅ the label disk is gone from node k8squest-control-plane"
exit 0
