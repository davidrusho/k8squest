#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
validate_vms
fail() { echo "❌ $1"; [ -n "${2:-}" ] && echo "💡 $2"; exit 1; }

echo "🔍 Stage 1: Has kubeadm init created a control plane that answers?"
vm_sh "$CP_VM" 'test -s /etc/kubernetes/admin.conf' || fail "There is no /etc/kubernetes/admin.conf: kubeadm init has not completed" "sudo kubeadm init --pod-network-cidr=10.244.0.0/16"
[ "$(kc get --raw /readyz --request-timeout=10s 2>/dev/null)" = ok ] || fail "The API server does not answer" "sudo crictl ps -a ; sudo journalctl -u kubelet --no-pager -n 20"
echo "✅ The API server is up"

# the cluster exists now: let kubectl on this computer reach it too (context k8squest-lima)
export_kubeconfig 2>/dev/null || true

echo ""
echo "🔍 Stage 2: Is it the Kubernetes version this world installs?"
VER=$(kc get node "$CP_NODE" -o jsonpath='{.status.nodeInfo.kubeletVersion}' 2>/dev/null)
case "$VER" in "$K8S_NEW"*) ;; *) fail "The control-plane node runs ${VER:-no kubelet}, not $K8S_NEW" ;; esac
echo "✅ $CP_NODE runs $VER"

echo ""
echo "🔍 Stage 3: Is the control-plane node Ready?"
READY=$(kc get node "$CP_NODE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
if [ "$READY" != "True" ]; then
    echo "$(kc get node "$CP_NODE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].message}' 2>/dev/null)" | cut -c1-160
    fail "$CP_NODE is not Ready (Ready=${READY:-unknown})" "kubectl describe node $CP_NODE   (the Ready condition says what is missing)"
fi
echo "✅ The node is Ready"

echo ""
echo "🔍 Stage 4: Does the pod network work (CoreDNS running)?"
vm_sh "$CP_VM" 'ls /etc/cni/net.d/*.conf* >/dev/null 2>&1' || fail "There is no CNI configuration in /etc/cni/net.d" "install a pod network add-on with kubectl apply"
# the pods need a few seconds after the node turns Ready
for i in $(seq 1 20); do
    DNS=$(kc -n kube-system get pods -l k8s-app=kube-dns --field-selector status.phase=Running --no-headers 2>/dev/null | awk '$2 == "1/1"' | wc -l | tr -d ' ')
    [ "${DNS:-0}" -ge 1 ] && break
    sleep 3
done
[ "${DNS:-0}" -ge 1 ] || fail "CoreDNS is not running (it stays Pending until a pod network exists)" "kubectl get pods -A"
echo "✅ CoreDNS is running, so pods get a network"

echo ""
echo "🎉 SUCCESS! You bootstrapped a control plane. kubectl context k8squest-lima now points at it."
exit 0
