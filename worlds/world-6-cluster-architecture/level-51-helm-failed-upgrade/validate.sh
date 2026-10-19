#!/bin/bash
NAMESPACE="${NAMESPACE:-k8squest}"
RELEASE="webapp"
GOOD_IMAGE="nginx:1.27-alpine"

echo "🔍 Stage 1: Is the Helm release present and deployed?"
STATUS=$(helm status "$RELEASE" -n "$NAMESPACE" -o json 2>/dev/null | grep -o '"status":"[a-z-]*"' | head -1)
if [ "$STATUS" != '"status":"deployed"' ]; then
    echo "❌ Release '$RELEASE' is not in the deployed state (got: ${STATUS:-none})"
    echo "💡 helm list -n $NAMESPACE"
    exit 1
fi
echo "✅ Release is deployed"

echo ""
echo "🔍 Stage 2: Does the release's own manifest use the good image?"
MANIFEST=$(helm get manifest "$RELEASE" -n "$NAMESPACE" 2>/dev/null)
if ! echo "$MANIFEST" | grep -q "image: \"$GOOD_IMAGE\""; then
    echo "❌ The current release revision does not render image $GOOD_IMAGE"
    echo "💡 Changing the Deployment with kubectl does not change what Helm recorded."
    echo "💡 helm history $RELEASE -n $NAMESPACE ; helm get values $RELEASE -n $NAMESPACE"
    exit 1
fi
echo "✅ Release manifest uses $GOOD_IMAGE"

echo ""
echo "🔍 Stage 3: Is the rollout complete?"
if ! kubectl rollout status deployment/"$RELEASE" -n "$NAMESPACE" --timeout=5s >/dev/null 2>&1; then
    echo "❌ Deployment '$RELEASE' has not finished rolling out"
    kubectl get pods -n "$NAMESPACE" -l app="$RELEASE"
    exit 1
fi
BAD=$(kubectl get pods -n "$NAMESPACE" -l app="$RELEASE" -o jsonpath='{range .items[*]}{.spec.containers[0].image}{"\n"}{end}' | grep -vc "^$GOOD_IMAGE$")
if [ "$BAD" != "0" ]; then
    echo "❌ $BAD pod(s) are not running $GOOD_IMAGE yet"
    exit 1
fi
echo "✅ All pods run $GOOD_IMAGE and the rollout is complete"

echo ""
echo "🎉 SUCCESS! The webapp release is healthy again."
exit 0
