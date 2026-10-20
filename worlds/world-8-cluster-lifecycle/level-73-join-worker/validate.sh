#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
validate_vms
fail() { echo "❌ $1"; [ -n "${2:-}" ] && echo "💡 $2"; exit 1; }

echo "🔍 Stage 1: Is the control plane still answering?"
[ "$(kc get --raw /readyz --request-timeout=10s 2>/dev/null)" = ok ] || fail "The API server does not answer" "this level starts with a working control plane; reset the level to get it back"
echo "✅ The API server is up"

echo ""
echo "🔍 Stage 2: Has the worker joined the cluster?"
kc get node "$WK_NODE" >/dev/null 2>&1 || fail "$WK_NODE is not a node of the cluster yet" "sudo kubeadm token create --print-join-command   (on k8squest-cp), then run what it prints with sudo on k8squest-worker"
vm_sh "$WK_VM" 'test -s /etc/kubernetes/kubelet.conf' || fail "The worker has no /etc/kubernetes/kubelet.conf: kubeadm join did not run on it"
[ "$(vm_sh "$WK_VM" 'systemctl is-active kubelet')" = active ] || fail "The kubelet is not running on $WK_VM" "sudo systemctl status kubelet"
echo "✅ $WK_NODE is a node of the cluster"

echo ""
echo "🔍 Stage 3: Is the worker Ready, with its pod network?"
READY=$(kc get node "$WK_NODE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
[ "$READY" = True ] || fail "$WK_NODE is not Ready yet (Ready=${READY:-unknown}); it needs about a minute after joining" "kubectl get nodes -w"
FLANNEL=$(kc -n kube-flannel get pods -o jsonpath='{range .items[*]}{.spec.nodeName}{" "}{.status.phase}{"\n"}{end}' 2>/dev/null | grep -cx "$WK_NODE Running")
[ "$FLANNEL" -ge 1 ] || fail "There is no running Flannel pod on $WK_NODE" "kubectl get pods -A -o wide"
echo "✅ $WK_NODE is Ready and runs a Flannel pod"

echo ""
echo "🔍 Stage 4: Does the cluster have exactly the two nodes?"
COUNT=$(kc get nodes --no-headers 2>/dev/null | wc -l | tr -d ' ')
[ "$COUNT" = 2 ] || fail "The cluster has $COUNT nodes, expected 2"
echo "✅ Two nodes"

echo ""
echo "🎉 SUCCESS! The worker joined the cluster."
exit 0
