#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
validate_context
NAMESPACE="${NAMESPACE:-k8squest}"
NODE="k8squest-multinode-worker"

echo "🔍 Stage 1: Is $NODE Ready?"
READY=$(kubectl --request-timeout=10s get node "$NODE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
if [ "$READY" != "True" ]; then
    echo "❌ $NODE is not Ready (Ready=${READY:-unknown})"
    echo "💡 kubectl describe node $NODE   (see Conditions and Taints)"
    exit 1
fi
echo "✅ Node is Ready"

echo ""
echo "🔍 Stage 2: Will the kubelet come back after a reboot?"
if [ "$(docker exec "$NODE" systemctl is-enabled kubelet 2>/dev/null)" != "enabled" ]; then
    echo "❌ The kubelet is running but not enabled, so it would not start again at boot"
    echo "💡 systemctl enable kubelet"
    exit 1
fi
echo "✅ kubelet is enabled"

echo ""
echo "🔍 Stage 3: Is the pinned workload still pinned, and running?"
SEL=$(kubectl get deployment inventory -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.nodeSelector.kubernetes\.io/hostname}' 2>/dev/null)
if [ "$SEL" != "$NODE" ]; then
    echo "❌ The inventory Deployment's nodeSelector was changed (found: '${SEL:-none}'). The workload was fine; fix the node."
    exit 1
fi
RUNNING=$(kubectl get pods -n "$NAMESPACE" -l app=inventory --field-selector "spec.nodeName=$NODE,status.phase=Running" --no-headers 2>/dev/null | wc -l | tr -d ' ')
if [ "$RUNNING" -lt 2 ]; then
    echo "❌ $RUNNING of 2 inventory pods are Running on $NODE (they start a few seconds after the node is Ready)"
    echo "💡 kubectl get pods -n $NAMESPACE -o wide"
    exit 1
fi
echo "✅ 2 inventory pods are Running on $NODE"

echo ""
echo "🎉 SUCCESS! The kubelet is running and enabled, and the node is back in service."
exit 0
