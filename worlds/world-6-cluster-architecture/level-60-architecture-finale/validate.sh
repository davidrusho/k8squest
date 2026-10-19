#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
NAMESPACE="${NAMESPACE:-k8squest}"
FAILED=0
SA="system:serviceaccount:${NAMESPACE}:probe-sa"

echo "🔍 Area 1: TLS - is platform-cert Ready with a real issuer?"
ISSUER=$(kubectl get certificate platform-cert -n "$NAMESPACE" -o jsonpath='{.spec.issuerRef.name}' 2>/dev/null)
READY=$(kubectl get certificate platform-cert -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
if [ "$READY" = "True" ] && [ -n "$(kubectl get secret platform-cert-tls -n "$NAMESPACE" -o jsonpath='{.data.tls\.crt}' 2>/dev/null)" ]; then
    echo "✅ platform-cert is Ready (issuer: $ISSUER)"
else
    echo "❌ platform-cert is not Ready (issuerRef name: '${ISSUER:-none}')"
    echo "💡 kubectl describe certificate platform-cert -n $NAMESPACE"
    FAILED=1
fi

echo ""
echo "🔍 Area 2: Routing - is api-route attached to web-gw (unchanged) with its backend resolved?"
LISTENERS=$(kubectl get gateway web-gw -n "$NAMESPACE" -o jsonpath='{range .spec.listeners[*]}{.name}:{.port}:{.protocol} {end}' 2>/dev/null)
BACKEND=$(kubectl get httproute api-route -n "$NAMESPACE" -o jsonpath='{.spec.rules[0].backendRefs[0].name}:{.spec.rules[0].backendRefs[0].port}' 2>/dev/null)
if [ "$LISTENERS" != "http:80:HTTP " ]; then
    echo "❌ Gateway web-gw was changed (listeners: '$LISTENERS'); fix the route, not the Gateway"
    FAILED=1
elif [ "$BACKEND" != "api:80" ]; then
    echo "❌ api-route backendRef is '$BACKEND', expected api:80"
    FAILED=1
elif ROUTE_CHECK=$(route_attached "$NAMESPACE" api-route web-gw); then
    echo "✅ api-route is attached: $ROUTE_CHECK"
else
    echo "❌ api-route: $ROUTE_CHECK"
    echo "💡 kubectl describe httproute api-route -n $NAMESPACE ; kubectl get gateway web-gw -n $NAMESPACE -o yaml"
    FAILED=1
fi

echo ""
echo "🔍 Area 3: RBAC - can probe-sa read ConfigMaps, and only that?"
EXTRA=$(sa_extra_permissions "$NAMESPACE" probe-sa)
CRBS=$(sa_clusterrolebindings "$NAMESPACE" probe-sa)
if [ "$(kubectl auth can-i list configmaps --as="$SA" -n "$NAMESPACE" 2>/dev/null)" != "yes" ]; then
    echo "❌ $SA cannot list configmaps"
    echo "💡 kubectl logs probe -n $NAMESPACE ; kubectl get role settings-reader -n $NAMESPACE -o yaml"
    FAILED=1
elif [ -n "$EXTRA" ] || [ -n "$CRBS" ]; then
    echo "❌ probe-sa has more than get/list on ConfigMaps ${CRBS:+(ClusterRoleBinding: $CRBS)}:"
    echo "$EXTRA"
    FAILED=1
else
    LAST=$(kubectl logs probe -n "$NAMESPACE" --tail=1 2>/dev/null)
    case "$LAST" in
        *"HTTP 200") echo "✅ probe-sa reads ConfigMaps and nothing else ($LAST)" ;;
        *) echo "❌ the probe pod's latest call: ${LAST:-<none>} (calls repeat every 5 seconds, so retry)"; FAILED=1 ;;
    esac
fi

echo ""
if [ "$FAILED" -ne 0 ]; then
    echo "❌ At least one fault remains."
    exit 1
fi
echo "🎉 SUCCESS! WORLD 6 COMPLETE! Certificate, route and RBAC are all healthy."
exit 0
