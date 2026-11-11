#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

J=$(kubectl get job j1 -n "$NS" -o json 2>/dev/null)
[[ -n "$J" ]] || fail "job j1 does not exist in namespace $NS"
GOT=$(echo "$J" | jq -cS '.spec | {completions, parallelism}')
[[ "$GOT" == '{"completions":3,"parallelism":2}' ]] || fail "completions and parallelism is $GOT, expected "'{"completions":3,"parallelism":2}'
GOT=$(echo "$J" | jq -r '.spec.template.spec.containers[0].image | sub(":latest$";"")')
[[ "$GOT" == "busybox" ]] || fail "image is $GOT, expected busybox"
CMD=$(echo "$J" | jq -r '.spec.template.spec.containers[0] | ((.command // []) + (.args // [])) | join(" ")')
CMD=${CMD#/bin/sh -c }; CMD=${CMD#sh -c }
[[ "$CMD" == "sleep 10" ]] || fail "command is '$CMD', expected sleep 10"
echo "✅ Job j1 has 3 completions, 2 at a time"
exit 0
