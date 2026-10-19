#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
validate_context
NAMESPACE="${NAMESPACE:-k8squest}"

echo "🔍 Stage 1: Is the kube-controller-manager pod Ready?"
READY=$(kubectl --request-timeout=10s get pods -n kube-system -l component=kube-controller-manager -o jsonpath='{.items[0].status.containerStatuses[0].ready}' 2>/dev/null)
if [ "$READY" != "true" ]; then
    echo "❌ kube-controller-manager is not Ready"
    echo "💡 kubectl get pods -n kube-system   and   kubectl describe pod -n kube-system -l component=kube-controller-manager"
    exit 1
fi
echo "✅ kube-controller-manager is Ready"

echo ""
echo "🔍 Stage 2: Does the orders Deployment have its ReplicaSet and pods?"
RS=$(kubectl get replicasets -n "$NAMESPACE" -l app=orders --no-headers 2>/dev/null | wc -l | tr -d ' ')
if [ "$RS" = "0" ]; then
    echo "❌ The orders Deployment has no ReplicaSet yet (the controller creates it a few seconds after it is back)"
    echo "💡 kubectl get deployment,replicaset,pods -n $NAMESPACE"
    exit 1
fi
READYR=$(kubectl get deployment orders -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
if [ "${READYR:-0}" != "3" ]; then
    echo "❌ ${READYR:-0} of 3 orders pods are Ready"
    exit 1
fi
echo "✅ 3 orders pods are Ready"

echo ""
echo "🎉 SUCCESS! The controller manager is running again and the Deployment is rolled out."
exit 0
