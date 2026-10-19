#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
validate_context
NAMESPACE="${NAMESPACE:-k8squest}"

echo "🔍 Stage 1: Is the pod running with both containers?"
POD=$(kubectl get pods -n "$NAMESPACE" -l app=invoice-api --field-selector status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -z "$POD" ]; then
    echo "❌ No running invoice-api pod"
    echo "💡 kubectl get pods -n $NAMESPACE"
    exit 1
fi
NAMES=$(kubectl get pod "$POD" -n "$NAMESPACE" -o jsonpath='{.spec.containers[*].name}')
if [ "$NAMES" != "log-shipper invoice-api" ]; then
    echo "❌ The pod's containers are '$NAMES'; both log-shipper and invoice-api must stay"
    exit 1
fi
READY=$(kubectl get pod "$POD" -n "$NAMESPACE" -o jsonpath='{range .status.containerStatuses[*]}{.ready}{" "}{end}')
if [ "$READY" != "true true " ]; then
    echo "❌ $POD is not 2/2 Ready (containers ready: $READY)"
    echo "💡 kubectl logs $POD -n $NAMESPACE -c invoice-api --previous"
    exit 1
fi
echo "✅ $POD is 2/2 Ready"

echo ""
echo "🔍 Stage 2: Did invoice-api start properly?"
if ! kubectl logs "$POD" -n "$NAMESPACE" -c invoice-api 2>/dev/null | grep -q '^connected to database at '; then
    echo "❌ invoice-api's log does not show a database connection"
    exit 1
fi
echo "✅ invoice-api connected to its database"

echo ""
echo "🎉 SUCCESS! The configuration is fixed and the application is up."
exit 0
