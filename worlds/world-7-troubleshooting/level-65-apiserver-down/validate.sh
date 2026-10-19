#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
validate_context
NAMESPACE="${NAMESPACE:-k8squest}"

echo "🔍 Stage 1: Does the API server answer?"
ok=0
for i in 1 2 3 4 5 6 7 8; do
    if kubectl --request-timeout=5s get --raw /readyz >/dev/null 2>&1; then ok=1; break; fi
    sleep 3
done
if [ $ok != 1 ]; then
    echo "❌ The API server is not answering (kubectl --request-timeout=5s get --raw /readyz failed for ~40 seconds)"
    echo "💡 You cannot use kubectl logs now. On the node: crictl ps -a, crictl logs <container-id>"
    exit 1
fi
echo "✅ /readyz answers"

echo ""
echo "🔍 Stage 2: Can it reach etcd?"
if ! kubectl --request-timeout=10s get --raw '/readyz/etcd' >/dev/null 2>&1; then
    echo "❌ /readyz/etcd fails: the API server is up but cannot reach etcd"
    exit 1
fi
echo "✅ /readyz/etcd is ok"

echo ""
echo "🔍 Stage 3: Are the nodes and the workload fine?"
NOT_READY=$(kubectl --request-timeout=10s get nodes --no-headers 2>/dev/null | awk '$2 != "Ready"' | wc -l | tr -d ' ')
if [ "$NOT_READY" != "0" ]; then
    echo "❌ $NOT_READY node(s) not Ready yet (they report in a few seconds after the API server is back)"
    exit 1
fi
AV=$(kubectl --request-timeout=10s get deployment status-page -n "$NAMESPACE" -o jsonpath='{.status.availableReplicas}' 2>/dev/null)
if [ "${AV:-0}" != "2" ]; then
    echo "❌ status-page has ${AV:-0} of 2 available replicas"
    exit 1
fi
echo "✅ all nodes Ready, status-page 2/2"

echo ""
echo "🎉 SUCCESS! The API server is back and talking to etcd."
exit 0
