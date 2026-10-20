#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
validate_vms
NAMESPACE="${NAMESPACE:-k8squest}"
fail() { echo "❌ $1"; [ -n "${2:-}" ] && echo "💡 $2"; exit 1; }

echo "🔍 Stage 1: Does the API server answer?"
wait_admin 90 || fail "The API server does not answer (it restarts during the upgrade)" "give it a minute; kubectl get nodes"
echo "✅ The API server is up"

echo ""
echo "🔍 Stage 2: Is the control plane at $K8S_NEW?"
for c in kube-apiserver kube-controller-manager kube-scheduler; do
    IMG=$(kc -n kube-system get pods -l "component=$c" -o jsonpath='{.items[0].spec.containers[0].image}' 2>/dev/null)
    case "$IMG" in *":$K8S_NEW") ;; *) fail "$c runs ${IMG:-nothing}, not $K8S_NEW" "sudo kubeadm upgrade apply $K8S_NEW   (on the control plane)" ;; esac
done
echo "✅ apiserver, controller-manager and scheduler run $K8S_NEW"

echo ""
echo "🔍 Stage 3: Are both kubelets at $K8S_NEW and the nodes Ready?"
for n in "$CP_NODE" "$WK_NODE"; do
    V=$(kc get node "$n" -o jsonpath='{.status.nodeInfo.kubeletVersion}' 2>/dev/null)
    [ "$V" = "$K8S_NEW" ] || fail "$n runs kubelet ${V:-?}, not $K8S_NEW" "upgrade its kubelet package and restart the kubelet"
    [ "$(kc get node "$n" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)" = True ] \
        || fail "$n is not Ready" "kubectl get nodes"
done
echo "✅ Both nodes are Ready at $K8S_NEW"

echo ""
echo "🔍 Stage 4: Are the packages on both machines at $K8S_NEW and the repository on $K8S_NEW_MINOR?"
for vm in "$CP_VM" "$WK_VM"; do
    V=$(vm_sh "$vm" 'kubeadm version -o short; kubectl version --client -o yaml | sed -n "s/^  gitVersion: //p"' | tr '\n' ' ')
    [ "$V" = "$K8S_NEW $K8S_NEW " ] || fail "On $vm kubeadm/kubectl report: ${V:-nothing}" "upgrade the kubeadm and kubectl packages there"
    vm_sh "$vm" "grep -q 'stable:/$K8S_NEW_MINOR/' /etc/apt/sources.list.d/kubernetes.list" \
        || fail "The apt repository on $vm is not on $K8S_NEW_MINOR" "/etc/apt/sources.list.d/kubernetes.list"
done
echo "✅ kubeadm and kubectl are $K8S_NEW on both machines"

echo ""
echo "🔍 Stage 5: Are both nodes schedulable again?"
for n in "$CP_NODE" "$WK_NODE"; do
    [ "$(kc get node "$n" -o jsonpath='{.spec.unschedulable}' 2>/dev/null)" != true ] \
        || fail "$n is still cordoned" "kubectl uncordon $n"
done
echo "✅ Neither node is cordoned"

echo ""
echo "🔍 Stage 6: Is the orders workload the same one, running?"
UID_NOW=$(kc -n "$NAMESPACE" get deployment orders -o jsonpath='{.metadata.uid}' 2>/dev/null)
[ -n "$UID_NOW" ] || fail "The orders Deployment is gone" "an upgrade does not touch workloads; reset the level and upgrade in place"
[ "$UID_NOW" = "$(recall 74-orders-uid)" ] || fail "The orders Deployment is not the original one (it was recreated)" "this level is an in-place upgrade; reset the level and try again"
AV=$(kc -n "$NAMESPACE" get deployment orders -o jsonpath='{.status.availableReplicas}' 2>/dev/null)
[ "${AV:-0}" = 3 ] || fail "${AV:-0} of 3 orders replicas are available (they start once the worker is schedulable again)" "kubectl get pods -n $NAMESPACE -o wide"
echo "✅ orders is the original Deployment with 3 replicas available"

echo ""
echo "🎉 SUCCESS! The cluster runs $K8S_NEW on both machines and nothing was lost."
exit 0
