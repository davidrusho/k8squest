#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
NAMESPACE="${NAMESPACE:-k8squest}"
DEPLOY="shop-web"
WORK=$(level_workdir level-52-kustomize-overlay)
OVERLAY="$WORK/kustomize/overlays/prod"

echo "🔍 Stage 1: Does your working copy of the overlay exist and render?"
if [ ! -d "$OVERLAY" ]; then
    echo "❌ $OVERLAY not found; start the level again so setup.sh recreates it"
    exit 1
fi
if ! RENDERED=$(kubectl kustomize "$OVERLAY" 2>&1); then
    echo "❌ kubectl kustomize failed:"
    echo "$RENDERED"
    exit 1
fi
echo "✅ Overlay renders"

echo ""
echo "🔍 Stage 2: Does the rendered Deployment have 3 replicas and LOG_LEVEL=info?"
# one line per rendered object: kind/replicas/LOG_LEVEL
LINE=$(echo "$RENDERED" | kubectl create --dry-run=client -f - -o jsonpath='{.kind}/{.spec.replicas}/{.spec.template.spec.containers[0].env[?(@.name=="LOG_LEVEL")].value}{"\n"}' 2>/dev/null | grep '^Deployment/')
R_REPLICAS=$(echo "$LINE" | cut -d/ -f2)
R_LOG=$(echo "$LINE" | cut -d/ -f3)
if [ "$R_REPLICAS" != "3" ] || [ "$R_LOG" != "info" ]; then
    echo "❌ The overlay renders replicas='$R_REPLICAS' LOG_LEVEL='$R_LOG'; the prod overlay should give 3 and info"
    echo "💡 kubectl kustomize $OVERLAY"
    exit 1
fi
echo "✅ The overlay renders replicas=3 LOG_LEVEL=info"

echo ""
echo "🔍 Stage 3: Is the cluster running what the overlay renders?"
if ! kubectl get deployment "$DEPLOY" -n "$NAMESPACE" >/dev/null 2>&1; then
    echo "❌ Deployment '$DEPLOY' not found in $NAMESPACE"
    exit 1
fi
L_REPLICAS=$(kubectl get deployment "$DEPLOY" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}')
L_LOG=$(kubectl get deployment "$DEPLOY" -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[?(@.name=="web")].env[?(@.name=="LOG_LEVEL")].value}')
if [ "$L_REPLICAS" != "$R_REPLICAS" ] || [ "$L_LOG" != "$R_LOG" ]; then
    echo "❌ Cluster has replicas=$L_REPLICAS LOG_LEVEL=$L_LOG, the overlay renders replicas=$R_REPLICAS LOG_LEVEL=$R_LOG"
    echo "💡 Apply the overlay: kubectl apply -k $OVERLAY"
    exit 1
fi
echo "✅ Cluster matches the rendered overlay"

echo ""
echo "🔍 Stage 4: Are all replicas ready?"
if ! kubectl rollout status deployment/"$DEPLOY" -n "$NAMESPACE" --timeout=5s >/dev/null 2>&1; then
    echo "❌ Rollout not finished yet"
    exit 1
fi
echo "✅ Rollout complete"

echo ""
echo "🎉 SUCCESS! The prod overlay does what it says, and the cluster runs it."
exit 0
