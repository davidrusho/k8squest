#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
validate_context
NAMESPACE="${NAMESPACE:-k8squest}"
NODE="k8squest-multinode-worker2"

echo "🔍 Stage 1: Is the kubelet on $NODE running?"
if [ "$(docker exec "$NODE" systemctl is-active kubelet 2>/dev/null)" != "active" ]; then
    echo "❌ kubelet is not active on $NODE"
    echo "💡 docker exec $NODE journalctl -u kubelet --no-pager -n 20"
    exit 1
fi
echo "✅ kubelet is active"

echo ""
echo "🔍 Stage 2: Does the configuration point at files that exist?"
CA=$(docker exec "$NODE" sed -n 's/^ *clientCAFile: *//p' /var/lib/kubelet/config.yaml 2>/dev/null | head -1)
if [ -z "$CA" ] || ! docker exec "$NODE" test -s "$CA" 2>/dev/null; then
    echo "❌ clientCAFile in /var/lib/kubelet/config.yaml is '${CA:-missing}', which is not a readable file"
    exit 1
fi
echo "✅ clientCAFile: $CA"

echo ""
echo "🔍 Stage 3: Is $NODE Ready?"
READY=$(kubectl --request-timeout=10s get node "$NODE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
if [ "$READY" != "True" ]; then
    echo "❌ $NODE is not Ready (Ready=${READY:-unknown})"
    echo "💡 kubectl describe node $NODE"
    exit 1
fi
echo "✅ Node is Ready"

echo ""
echo "🔍 Stage 4: Are the pinned reports pods running?"
SEL=$(kubectl get deployment reports -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.nodeSelector.kubernetes\.io/hostname}' 2>/dev/null)
if [ "$SEL" != "$NODE" ]; then
    echo "❌ The reports Deployment's nodeSelector was changed (found: '${SEL:-none}'). The workload was fine; fix the node."
    exit 1
fi
RUNNING=$(kubectl get pods -n "$NAMESPACE" -l app=reports --field-selector "spec.nodeName=$NODE,status.phase=Running" --no-headers 2>/dev/null | wc -l | tr -d ' ')
if [ "$RUNNING" -lt 2 ]; then
    echo "❌ $RUNNING of 2 reports pods are Running on $NODE"
    exit 1
fi
echo "✅ 2 reports pods are Running on $NODE"

echo ""
echo "🎉 SUCCESS! The kubelet configuration is valid and the node is back."
exit 0
