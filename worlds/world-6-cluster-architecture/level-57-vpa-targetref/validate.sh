#!/bin/bash
NAMESPACE="${NAMESPACE:-k8squest}"
VPA="hamster-vpa"

echo "🔍 Stage 1: Does the VPA exist?"
if ! kubectl get vpa "$VPA" -n "$NAMESPACE" >/dev/null 2>&1; then
    echo "❌ VerticalPodAutoscaler '$VPA' not found"
    exit 1
fi
echo "✅ VPA exists"

echo ""
echo "🔍 Stage 2: Does the targetRef name an existing Deployment?"
KIND=$(kubectl get vpa "$VPA" -n "$NAMESPACE" -o jsonpath='{.spec.targetRef.kind}')
NAME=$(kubectl get vpa "$VPA" -n "$NAMESPACE" -o jsonpath='{.spec.targetRef.name}')
if [ "$KIND" != "Deployment" ] || [ "$NAME" != "hamster" ]; then
    echo "❌ targetRef is $KIND/$NAME; the workload is Deployment/hamster"
    echo "💡 kubectl get deployment -n $NAMESPACE ; kubectl describe vpa $VPA -n $NAMESPACE"
    exit 1
fi
echo "✅ targetRef Deployment/hamster"

echo ""
echo "🔍 Stage 3: Is the VPA still recommendation-only?"
MODE=$(kubectl get vpa "$VPA" -n "$NAMESPACE" -o jsonpath='{.spec.updatePolicy.updateMode}')
if [ -n "$MODE" ] && [ "$MODE" != "Off" ]; then
    echo "❌ updateMode is '$MODE'; this level keeps the VPA in recommendation-only mode (Off)"
    exit 1
fi
echo "✅ updateMode Off"

echo ""
echo "🔍 Stage 4: Has the recommender published a recommendation?"
TARGET=$(kubectl get vpa "$VPA" -n "$NAMESPACE" -o jsonpath='{.status.recommendation.containerRecommendations[0].target.cpu}' 2>/dev/null)
if [ -z "$TARGET" ]; then
    echo "❌ No recommendation yet. The recommender needs a minute or two of metrics after the VPA matches its pods."
    echo "💡 kubectl describe vpa $VPA -n $NAMESPACE   (wait and retry validation)"
    exit 1
fi
echo "✅ Recommended CPU request: $TARGET"

echo ""
echo "🎉 SUCCESS! The VPA is watching the right workload and recommending requests."
exit 0
