#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
validate_context
NAMESPACE="${NAMESPACE:-k8squest}"

echo "🔍 Stage 1: Is the kube-scheduler pod Ready?"
READY=$(kubectl --request-timeout=10s get pods -n kube-system -l component=kube-scheduler -o jsonpath='{.items[0].status.containerStatuses[0].ready}' 2>/dev/null)
if [ "$READY" != "true" ]; then
    echo "❌ kube-scheduler is not Ready"
    echo "💡 kubectl get pods -n kube-system   and   kubectl logs -n kube-system -l component=kube-scheduler"
    exit 1
fi
echo "✅ kube-scheduler is Ready"

echo ""
echo "🔍 Stage 2: Is the checkout Deployment scheduled by the scheduler (not pinned by hand)?"
if [ -n "$(kubectl get deployment checkout -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.nodeName}' 2>/dev/null)" ]; then
    echo "❌ The Deployment sets spec.nodeName, which skips the scheduler. Repair the scheduler instead."
    exit 1
fi
READYR=$(kubectl get deployment checkout -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
if [ "${READYR:-0}" != "3" ]; then
    echo "❌ ${READYR:-0} of 3 checkout pods are Ready (they are scheduled a few seconds after the scheduler is back)"
    echo "💡 kubectl get pods -n $NAMESPACE -o wide"
    exit 1
fi
NODELESS=$(kubectl get pods -n "$NAMESPACE" -l app=checkout -o jsonpath='{range .items[*]}{.spec.nodeName}{"\n"}{end}' | grep -c '^$')
if [ "$NODELESS" != "0" ]; then
    echo "❌ $NODELESS checkout pod(s) have no node"
    exit 1
fi
echo "✅ 3 checkout pods are Ready, all scheduled"

echo ""
echo "🎉 SUCCESS! The scheduler is back and the pending pods found nodes."
exit 0
