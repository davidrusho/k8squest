#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
validate_context
NAMESPACE="${NAMESPACE:-k8squest}"
NODE="k8squest-multinode-worker2"

echo "🔍 Stage 1: Is $NODE Ready?"
READY=$(kubectl --request-timeout=10s get node "$NODE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
if [ "$READY" != "True" ]; then
    echo "❌ $NODE is not Ready (Ready=${READY:-unknown})"
    echo "💡 kubectl describe node $NODE   (read the Ready condition's message)"
    exit 1
fi
echo "✅ Node is Ready"

echo ""
echo "🔍 Stage 2: Does the CNI DaemonSet run on every node?"
NODES=$(kubectl get nodes --no-headers | wc -l | tr -d ' ')
DESIRED=$(kubectl get ds kindnet -n kube-system -o jsonpath='{.status.desiredNumberScheduled}' 2>/dev/null)
NREADY=$(kubectl get ds kindnet -n kube-system -o jsonpath='{.status.numberReady}' 2>/dev/null)
if [ "$DESIRED" != "$NODES" ] || [ "$NREADY" != "$NODES" ]; then
    echo "❌ kindnet: desired=${DESIRED:-?} ready=${NREADY:-?}, but the cluster has $NODES nodes"
    echo "💡 kubectl get ds kindnet -n kube-system -o wide"
    exit 1
fi
if ! docker exec "$NODE" test -s /etc/cni/net.d/10-kindnet.conflist 2>/dev/null; then
    echo "❌ $NODE has no CNI configuration in /etc/cni/net.d"
    exit 1
fi
echo "✅ kindnet runs on all $NODES nodes and $NODE has its CNI config"

echo ""
echo "🔍 Stage 3: Do pods on $NODE get a network?"
SEL=$(kubectl get deployment edge-cache -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.nodeSelector.kubernetes\.io/hostname}' 2>/dev/null)
if [ "$SEL" != "$NODE" ]; then
    echo "❌ The edge-cache Deployment's nodeSelector was changed (found: '${SEL:-none}'). The workload was fine; fix the cluster."
    exit 1
fi
CIDR=$(kubectl get node "$NODE" -o jsonpath='{.spec.podCIDR}')
OKPODS=0
for ip in $(kubectl get pods -n "$NAMESPACE" -l app=edge-cache --field-selector "spec.nodeName=$NODE,status.phase=Running" -o jsonpath='{.items[*].status.podIP}'); do
    case "$ip" in "${CIDR%.*/*}".*) OKPODS=$((OKPODS + 1)) ;; esac
done
if [ "$OKPODS" -lt 2 ]; then
    echo "❌ $OKPODS of 2 edge-cache pods are Running with an IP from $NODE's pod CIDR ($CIDR)"
    exit 1
fi
echo "✅ 2 edge-cache pods are Running with pod IPs from $CIDR"

echo ""
echo "🎉 SUCCESS! The node has its pod network and the workload is running."
exit 0
