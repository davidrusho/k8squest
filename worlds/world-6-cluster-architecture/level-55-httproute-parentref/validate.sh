#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
NAMESPACE="${NAMESPACE:-k8squest}"
ROUTE="echo-route"

echo "🔍 Stage 1: Does the HTTPRoute exist?"
if ! kubectl get httproute "$ROUTE" -n "$NAMESPACE" >/dev/null 2>&1; then
    echo "❌ HTTPRoute '$ROUTE' not found"
    exit 1
fi
echo "✅ HTTPRoute exists"

echo ""
echo "🔍 Stage 2: Does it still attach to the web-gw Gateway?"
PARENT=$(kubectl get httproute "$ROUTE" -n "$NAMESPACE" -o jsonpath='{.spec.parentRefs[0].name}')
if [ "$PARENT" != "web-gw" ]; then
    echo "❌ parentRef is '$PARENT', the Gateway is web-gw"
    echo "💡 kubectl get gateway -n $NAMESPACE"
    exit 1
fi
echo "✅ parentRef web-gw"

echo ""
echo "🔍 Stage 3: Does the route still send traffic to Service echo on port 80?"
B_NAME=$(kubectl get httproute "$ROUTE" -n "$NAMESPACE" -o jsonpath='{.spec.rules[0].backendRefs[0].name}')
B_PORT=$(kubectl get httproute "$ROUTE" -n "$NAMESPACE" -o jsonpath='{.spec.rules[0].backendRefs[0].port}')
if [ "$B_NAME" != "echo" ] || [ "$B_PORT" != "80" ]; then
    echo "❌ backendRef is $B_NAME:$B_PORT; it must be the echo Service on its real port, 80"
    echo "💡 kubectl get svc echo -n $NAMESPACE"
    exit 1
fi
echo "✅ backendRef echo:80"

echo ""
echo "🔍 Stage 4: Is the route Accepted with its references resolved (for its current spec)?"
if ! DIAG=$(route_attached "$NAMESPACE" "$ROUTE" web-gw); then
    echo "❌ $DIAG"
    echo "💡 kubectl describe httproute $ROUTE -n $NAMESPACE (the controller may need a few seconds)"
    exit 1
fi
echo "✅ $DIAG"

echo ""
echo "🎉 SUCCESS! The route is attached and its backend resolves."
exit 0
