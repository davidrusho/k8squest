#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

P=$(kubectl get pod tol -n "$NS" -o json 2>/dev/null)
[[ -n "$P" ]] || fail "Pod tol does not exist in namespace $NS"
[[ "$(echo "$P" | jq -r '.spec.containers[0].image | sub(":latest$";"")')" == "nginx" ]] || fail "Pod tol must run image nginx"
TOL=$(echo "$P" | jq '[.spec.tolerations[]? | select(
    ((.key // "") == "dedicated" and ((.operator // "Equal") == "Exists" or ((.operator // "Equal") == "Equal" and .value == "gpu")) and ((.effect // "NoSchedule") == "NoSchedule"))
    or ((.key // "") == "" and .operator == "Exists"))] | length')
[[ "$TOL" -ge 1 ]] || fail "Pod tol has no toleration for dedicated=gpu:NoSchedule"
[[ "$(echo "$P" | jq -r '.spec.nodeName // ""')" == "k8squest-control-plane" ]] || fail "Pod tol is not scheduled onto the node yet"
echo "✅ Pod tol tolerates dedicated=gpu:NoSchedule and is scheduled onto the node"
exit 0
