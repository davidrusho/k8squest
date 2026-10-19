#!/bin/bash
NAMESPACE="${NAMESPACE:-k8squest}"

echo "🔍 Stage 1: Is the PVC Bound?"
PHASE=$(kubectl get pvc ledger-data -n "$NAMESPACE" -o jsonpath='{.status.phase}' 2>/dev/null)
if [ "$PHASE" != "Bound" ]; then
    echo "❌ PVC ledger-data is '${PHASE:-missing}'"
    echo "💡 kubectl describe pvc ledger-data -n $NAMESPACE ; kubectl get storageclass"
    exit 1
fi
echo "✅ PVC is Bound"

echo ""
echo "🔍 Stage 2: Does the pod still use a RuntimeClass?"
RC=$(kubectl get deployment ledger -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.runtimeClassName}' 2>/dev/null)
if [ -z "$RC" ]; then
    echo "❌ The Deployment no longer sets runtimeClassName; fix the RuntimeClass instead of dropping it"
    exit 1
fi
if ! kubectl get runtimeclass "$RC" >/dev/null 2>&1; then
    echo "❌ RuntimeClass '$RC' does not exist"
    exit 1
fi
echo "✅ runtimeClassName: $RC"

echo ""
echo "🔍 Stage 3: Is the pod Running and Ready?"
if ! kubectl wait --for=condition=Ready pod -l app=ledger -n "$NAMESPACE" --timeout=5s >/dev/null 2>&1; then
    echo "❌ The ledger pod is not Ready"
    kubectl get pods -n "$NAMESPACE" -l app=ledger
    echo "💡 kubectl describe pod -l app=ledger -n $NAMESPACE   (read the Events)"
    exit 1
fi
echo "✅ Pod is Ready"

echo ""
echo "🎉 SUCCESS! Both extension points resolve to components this cluster really has."
exit 0
