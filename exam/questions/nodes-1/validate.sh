#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

N=$(kubectl get node k8squest-control-plane -o json 2>/dev/null)
[[ "$(echo "$N" | jq -r .metadata.name)" == "k8squest-control-plane" ]] || fail "could not read node k8squest-control-plane"
GOT=$(echo "$N" | jq -r '.metadata.labels.disk // "unset"')
[[ "$GOT" == "ssd" ]] || fail "label disk is $GOT, expected ssd"
echo "✅ node k8squest-control-plane has the label disk=ssd"
exit 0
