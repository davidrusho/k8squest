#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

J=$(kubectl get job hello -n "$NS" -o json 2>/dev/null)
[[ -n "$J" ]] || fail "job hello does not exist in namespace $NS"
GOT=$(echo "$J" | jq -r '.spec.template.spec.containers[0].image | sub(":latest$";"")')
[[ "$GOT" == "busybox" ]] || fail "image is $GOT, expected busybox"
CMD=$(echo "$J" | jq -r '.spec.template.spec.containers[0] | ((.command // []) + (.args // [])) | join(" ")')
CMD=${CMD#/bin/sh -c }; CMD=${CMD#sh -c }
[[ "$CMD" == "echo hello" ]] || fail "command is '$CMD', expected echo hello"
SUCC=$(echo "$J" | jq '.status.succeeded // 0')
[[ "$SUCC" -ge 1 ]] || fail "Job hello has not completed yet (succeeded: $SUCC)"
echo "✅ Job hello ran echo hello and completed"
exit 0
