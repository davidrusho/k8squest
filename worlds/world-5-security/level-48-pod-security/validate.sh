#!/bin/bash

NAMESPACE="k8squest"
DEPLOYMENT="secure-app"

echo "🔍 VALIDATION STAGE 1: Checking namespace security labels..."
PSS_ENFORCE=$(kubectl get namespace $NAMESPACE -o jsonpath='{.metadata.labels.pod-security\.kubernetes\.io/enforce}')
if [ "$PSS_ENFORCE" != "restricted" ]; then
    echo "⚠️  Namespace doesn't enforce 'restricted' standard"
    echo "   This level works best with restricted enforcement"
fi
echo "✅ Namespace checked"

echo ""
echo "🔍 VALIDATION STAGE 2: Checking if Deployment exists..."
if ! kubectl get deployment $DEPLOYMENT -n $NAMESPACE &>/dev/null; then
    echo "❌ FAILED: Deployment '$DEPLOYMENT' not found"
    exit 1
fi
echo "✅ Deployment exists"

T='.spec.template.spec'

echo ""
echo "🔍 VALIDATION STAGE 3: Checking runAsNonRoot..."
RUN_AS_NON_ROOT=$(kubectl get deployment $DEPLOYMENT -n $NAMESPACE -o jsonpath="{$T.containers[0].securityContext.runAsNonRoot}")
POD_RUN_AS_NON_ROOT=$(kubectl get deployment $DEPLOYMENT -n $NAMESPACE -o jsonpath="{$T.securityContext.runAsNonRoot}")
if [ "$RUN_AS_NON_ROOT" != "true" ] && [ "$POD_RUN_AS_NON_ROOT" != "true" ]; then
    echo "❌ FAILED: runAsNonRoot not set to true"
    exit 1
fi
echo "✅ runAsNonRoot: true"

echo ""
echo "🔍 VALIDATION STAGE 4: Checking runAsUser (must be non-zero)..."
RUN_AS_USER=$(kubectl get deployment $DEPLOYMENT -n $NAMESPACE -o jsonpath="{$T.containers[0].securityContext.runAsUser}")
if [ -z "$RUN_AS_USER" ]; then
    RUN_AS_USER=$(kubectl get deployment $DEPLOYMENT -n $NAMESPACE -o jsonpath="{$T.securityContext.runAsUser}")
fi
if [ -z "$RUN_AS_USER" ] || [ "$RUN_AS_USER" = "0" ]; then
    echo "❌ FAILED: runAsUser is 0 (root) or not set"
    exit 1
fi
echo "✅ runAsUser: $RUN_AS_USER (non-root)"

echo ""
echo "🔍 VALIDATION STAGE 5: Checking allowPrivilegeEscalation..."
ALLOW_PRIV=$(kubectl get deployment $DEPLOYMENT -n $NAMESPACE -o jsonpath="{$T.containers[0].securityContext.allowPrivilegeEscalation}")
if [ "$ALLOW_PRIV" != "false" ]; then
    echo "❌ FAILED: allowPrivilegeEscalation not set to false"
    exit 1
fi
echo "✅ allowPrivilegeEscalation: false"

echo ""
echo "🔍 VALIDATION STAGE 6: Checking capabilities dropped..."
CAPS_DROP=$(kubectl get deployment $DEPLOYMENT -n $NAMESPACE -o jsonpath="{$T.containers[0].securityContext.capabilities.drop}")
if ! echo "$CAPS_DROP" | grep -q "ALL"; then
    echo "❌ FAILED: capabilities.drop does not include ALL"
    exit 1
fi
echo "✅ capabilities dropped: ALL"

echo ""
echo "🔍 VALIDATION STAGE 7: Checking seccompProfile..."
SECCOMP=$(kubectl get deployment $DEPLOYMENT -n $NAMESPACE -o jsonpath="{$T.securityContext.seccompProfile.type}")
if [ -z "$SECCOMP" ]; then
    SECCOMP=$(kubectl get deployment $DEPLOYMENT -n $NAMESPACE -o jsonpath="{$T.containers[0].securityContext.seccompProfile.type}")
fi
if [ "$SECCOMP" != "RuntimeDefault" ] && [ "$SECCOMP" != "Localhost" ]; then
    echo "❌ FAILED: seccompProfile must be RuntimeDefault or Localhost (required by the restricted standard)"
    exit 1
fi
echo "✅ seccompProfile: $SECCOMP"

echo ""
echo "🔍 VALIDATION STAGE 8: Checking that the admitted Pod is Running..."
READY=$(kubectl get deployment $DEPLOYMENT -n $NAMESPACE -o jsonpath='{.status.readyReplicas}')
if [ -z "$READY" ] || [ "$READY" -lt 1 ]; then
    echo "❌ FAILED: Deployment has no ready Pods"
    echo "💡 Hint: Pods may have been rejected by admission: kubectl describe rs -n $NAMESPACE"
    echo "💡 Hint: Check events: kubectl get events -n $NAMESPACE"
    exit 1
fi
echo "✅ Pod is Running ($READY ready)"

echo ""
echo "🎉 SUCCESS! Pod meets restricted Pod Security Standards!"
echo ""
echo "Security configuration:"
echo "  • runAsNonRoot: true"
echo "  • runAsUser: $RUN_AS_USER"
echo "  • allowPrivilegeEscalation: false"
echo "  • capabilities: drop ALL"
echo "  • seccompProfile: $SECCOMP"
echo ""
echo "This pod follows security best practices! 🔒"
