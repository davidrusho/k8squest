#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
validate_context
NAMESPACE="${NAMESPACE:-k8squest}"

echo "🔍 Stage 1: Is metrics-server still installed and Available?"
if ! kubectl --request-timeout=10s get deployment metrics-server -n kube-system >/dev/null 2>&1; then
    echo "❌ The metrics-server Deployment is gone. Repair it; do not remove it."
    exit 1
fi
AV=$(kubectl get apiservice v1beta1.metrics.k8s.io -o jsonpath='{.status.conditions[?(@.type=="Available")].status}' 2>/dev/null)
if [ "$AV" != "True" ]; then
    echo "❌ APIService v1beta1.metrics.k8s.io is not Available (Available=${AV:-unknown})"
    echo "💡 kubectl get apiservice v1beta1.metrics.k8s.io   then   kubectl get pods,logs -n kube-system -l k8s-app=metrics-server"
    exit 1
fi
echo "✅ metrics.k8s.io is Available"

echo ""
echo "🔍 Stage 2: Does kubectl top nodes work?"
if ! OUT=$(kubectl top nodes 2>&1); then
    echo "❌ kubectl top nodes: $OUT"
    exit 1
fi
LINES=$(printf '%s\n' "$OUT" | tail -n +2 | grep -c .)
if [ "$LINES" -lt 3 ]; then
    echo "❌ kubectl top nodes lists $LINES node(s); expected 3 (a node's metrics can take a scrape interval to appear)"
    exit 1
fi
echo "✅ kubectl top nodes lists $LINES nodes"

echo ""
echo "🔍 Stage 3: Does kubectl top pods work for the workload?"
if ! OUT=$(kubectl top pods -n "$NAMESPACE" 2>&1); then
    echo "❌ kubectl top pods -n $NAMESPACE: $OUT"
    exit 1
fi
if [ "$(printf '%s\n' "$OUT" | grep -c '^load-')" -lt 2 ]; then
    echo "❌ kubectl top pods does not list both load pods yet"
    exit 1
fi
echo "✅ kubectl top pods lists the load pods"

echo ""
echo "🎉 SUCCESS! The metrics pipeline works end to end."
exit 0
