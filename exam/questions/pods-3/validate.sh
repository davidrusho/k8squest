#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

P=$(kubectl get pod bb -n "$NS" -o json 2>/dev/null)
[[ -n "$P" ]] || fail "pod bb does not exist in namespace $NS"
GOT=$(echo "$P" | jq -cS '.spec.containers[0].image | sub(":latest$";"")')
[[ "$GOT" == '"busybox"' ]] || fail "image is $GOT, expected "'"busybox"'
CMD=$(echo "$P" | jq -r '.spec.containers[0] | ((.command // []) + (.args // [])) | join(" ")')
CMD=${CMD#/bin/sh -c }; CMD=${CMD#sh -c }
[[ "$CMD" == "sleep 3600" ]] || fail "command is '$CMD', expected sleep 3600"
echo "✅ Pod bb runs sleep 3600"
exit 0
