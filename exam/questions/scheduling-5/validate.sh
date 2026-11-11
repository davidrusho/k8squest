#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

P=$(kubectl get pod pinned -n "$NS" -o json 2>/dev/null)
[[ -n "$P" ]] || fail "pod pinned does not exist in namespace $NS"
GOT=$(echo "$P" | jq -cS '.spec.containers[0].image | sub(":latest$";"")')
[[ "$GOT" == '"nginx"' ]] || fail "image is $GOT, expected "'"nginx"'
GOT=$(echo "$P" | jq -cS '.spec.nodeName')
[[ "$GOT" == '"k8squest-control-plane"' ]] || fail "nodeName is $GOT, expected "'"k8squest-control-plane"'
GOT=$(echo "$P" | jq -cS '[.spec.nodeSelector, .spec.affinity] | map(select(. != null)) | length')
[[ "$GOT" == "0" ]] || fail "Pod pinned must be placed by nodeName only, without nodeSelector or affinity"
echo "✅ Pod pinned is bound to node k8squest-control-plane by nodeName"
exit 0
