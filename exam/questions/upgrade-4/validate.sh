#!/bin/bash
# kubeadm task: runs on k8s-lab as david and reaches controlplane through the root helper.
# Pods that may stay: DaemonSet Pods and mirror Pods of static Pods (owner kind Node).
fail() { echo "❌ $1"; exit 1; }

OUT=$(sudo -n /usr/local/sbin/cka-kubeadm run-on --timeout 100 controlplane 2>&1 <<'EOS'
bad() { echo "FAIL: $1"; exit 3; }
KC="kubectl --kubeconfig /etc/kubernetes/admin.conf --request-timeout=5s"
[ "$($KC get node controlplane -o jsonpath='{.spec.unschedulable}')" = true ] || bad "node controlplane is still schedulable"
LEFT=$($KC get pods -A --field-selector spec.nodeName=controlplane --no-headers -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name,OWNER:.metadata.ownerReferences[0].kind | awk '$3 != "DaemonSet" && $3 != "Node" {print $1 "/" $2}')
[ -z "$LEFT" ] || bad "Pods are still running on controlplane: $(printf '%s\n' "$LEFT" | head -n 3 | tr '\n' ' ')"
case "$($KC get node controlplane -o jsonpath='{.status.nodeInfo.kubeletVersion}')" in v1.36.*) ;; *) bad "the kubelet was upgraded already, this step is only the drain" ;; esac
echo ok
EOS
)
RC=$?
case $RC in
  0) ;;
  3) fail "$(printf '%s\n' "$OUT" | sed -n 's/^FAIL: //p' | head -n 1)" ;;
  *) fail "could not check controlplane (exit $RC): $(echo "$OUT" | tail -n 3)" ;;
esac
echo "✅ node controlplane is drained"
exit 0
