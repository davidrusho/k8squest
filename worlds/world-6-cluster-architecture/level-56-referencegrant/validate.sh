#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
NAMESPACE="${NAMESPACE:-k8squest}"
BACKEND_NS="k8squest-backend"
ROUTE="shop-route"

echo "🔍 Stage 1: Does the route still point at the Service in $BACKEND_NS?"
REF_NS=$(kubectl get httproute "$ROUTE" -n "$NAMESPACE" -o jsonpath='{.spec.rules[0].backendRefs[0].namespace}' 2>/dev/null)
if [ "$REF_NS" != "$BACKEND_NS" ]; then
    echo "❌ backendRef namespace is '${REF_NS:-unset}'; the Service must stay in $BACKEND_NS"
    exit 1
fi
if ! kubectl get service catalog -n "$BACKEND_NS" >/dev/null 2>&1; then
    echo "❌ Service catalog not found in $BACKEND_NS"
    exit 1
fi
echo "✅ Cross-namespace backendRef is in place"

echo ""
echo "🔍 Stage 2: Is there a ReferenceGrant in $BACKEND_NS for HTTPRoutes from $NAMESPACE?"
FROMS=$(kubectl get referencegrant -n "$BACKEND_NS" -o jsonpath='{range .items[*].spec.from[*]}{.kind}/{.namespace}{"\n"}{end}' 2>/dev/null)
if ! echo "$FROMS" | grep -qx "HTTPRoute/$NAMESPACE"; then
    echo "❌ No ReferenceGrant in $BACKEND_NS allows HTTPRoutes from $NAMESPACE"
    echo "💡 kubectl get referencegrant -n $BACKEND_NS -o yaml"
    exit 1
fi
echo "✅ A grant names HTTPRoute/$NAMESPACE"

echo ""
echo "🔍 Stage 3: Is the route Accepted with its references resolved (for its current spec)?"
if ! DIAG=$(route_attached "$NAMESPACE" "$ROUTE" web-gw); then
    echo "❌ $DIAG"
    echo "💡 kubectl describe httproute $ROUTE -n $NAMESPACE (the controller may need a few seconds)"
    exit 1
fi
echo "✅ $DIAG"

echo ""
echo "🎉 SUCCESS! The route may now reference the backend namespace."
exit 0
