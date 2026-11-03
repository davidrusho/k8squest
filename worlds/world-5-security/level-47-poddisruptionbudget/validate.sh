#!/bin/bash

NAMESPACE="k8squest"
DEPLOYMENT="web-app"
PDB_NAME="web-pdb"

echo "🔍 VALIDATION STAGE 1: Checking if deployment exists..."
if ! kubectl get deployment $DEPLOYMENT -n $NAMESPACE &>/dev/null; then
    echo "❌ FAILED: Deployment '$DEPLOYMENT' not found"
    exit 1
fi
echo "✅ Deployment exists"

echo ""
echo "🔍 VALIDATION STAGE 2: Checking if PodDisruptionBudget exists..."
if ! kubectl get pdb $PDB_NAME -n $NAMESPACE &>/dev/null; then
    echo "❌ FAILED: PodDisruptionBudget '$PDB_NAME' not found"
    exit 1
fi
echo "✅ PodDisruptionBudget exists"

echo ""
echo "🔍 VALIDATION STAGE 3: Checking deployment replica count..."
REPLICAS=$(kubectl get deployment $DEPLOYMENT -n $NAMESPACE -o jsonpath='{.spec.replicas}')
if [ "$REPLICAS" -lt 2 ]; then
    echo "❌ FAILED: Deployment has $REPLICAS replica(s), need at least 2"
    exit 1
fi
echo "✅ Deployment has $REPLICAS replicas"

echo ""
echo "🔍 VALIDATION STAGE 4: Verifying PDB configuration..."
MIN_AVAILABLE=$(kubectl get pdb $PDB_NAME -n $NAMESPACE -o jsonpath='{.spec.minAvailable}')
MAX_UNAVAILABLE=$(kubectl get pdb $PDB_NAME -n $NAMESPACE -o jsonpath='{.spec.maxUnavailable}')

# A PDB value is a number or a percentage; percentages round up
to_pods() {
    if [[ "$1" == *"%"* ]]; then
        echo $(( (${1%\%} * REPLICAS + 99) / 100 ))
    else
        echo "$1"
    fi
}

if [ -n "$MIN_AVAILABLE" ]; then
    echo "PDB minAvailable: $MIN_AVAILABLE"
    KEEP_PODS=$(to_pods "$MIN_AVAILABLE")
elif [ -n "$MAX_UNAVAILABLE" ]; then
    echo "PDB maxUnavailable: $MAX_UNAVAILABLE"
    KEEP_PODS=$((REPLICAS - $(to_pods "$MAX_UNAVAILABLE")))
else
    echo "❌ FAILED: PDB has neither minAvailable nor maxUnavailable"
    exit 1
fi
if [ "$KEEP_PODS" -gt "$REPLICAS" ]; then
    echo "❌ FAILED: the PDB keeps $KEEP_PODS pods available, but there are only $REPLICAS replicas"
    echo "💡 Hint: minAvailable must be ≤ replicas"
    exit 1
fi
if [ "$KEEP_PODS" -le 0 ]; then
    echo "❌ FAILED: the PDB protects nothing - it lets all $REPLICAS replicas be evicted at once"
    echo "💡 Hint: Keep at least one pod available while allowing evictions"
    exit 1
fi
echo "✅ PDB configuration is valid"

echo ""
echo "🔍 VALIDATION STAGE 5: Checking PDB status..."
ALLOWED_DISRUPTIONS=$(kubectl get pdb $PDB_NAME -n $NAMESPACE -o jsonpath='{.status.disruptionsAllowed}')
if [ -z "$ALLOWED_DISRUPTIONS" ]; then
    echo "⚠️  PDB status not yet available (pods may still be starting)"
    sleep 5
    ALLOWED_DISRUPTIONS=$(kubectl get pdb $PDB_NAME -n $NAMESPACE -o jsonpath='{.status.disruptionsAllowed}')
fi

if [ -z "$ALLOWED_DISRUPTIONS" ] || [ "$ALLOWED_DISRUPTIONS" = "0" ]; then
    echo "❌ FAILED: No disruptions allowed (disruptionsAllowed: ${ALLOWED_DISRUPTIONS:-0})"
    echo "   This means node drain would be blocked"
    echo "💡 Hint: Increase replicas or reduce minAvailable"
    exit 1
else
    echo "✅ Disruptions allowed: $ALLOWED_DISRUPTIONS"
fi

echo ""
echo "🔍 VALIDATION STAGE 6: Verifying pods are running..."
READY_REPLICAS=$(kubectl get deployment $DEPLOYMENT -n $NAMESPACE -o jsonpath='{.status.readyReplicas}')
if [ "$READY_REPLICAS" != "$REPLICAS" ]; then
    echo "⚠️  Only $READY_REPLICAS/$REPLICAS pods ready"
else
    echo "✅ All $REPLICAS pods are ready"
fi

echo ""
echo "🎉 SUCCESS! PodDisruptionBudget configured correctly!"
echo ""
echo "PDB Status:"
kubectl get pdb $PDB_NAME -n $NAMESPACE
echo ""
echo "Configuration allows $ALLOWED_DISRUPTIONS voluntary disruption(s)"
echo "This enables node maintenance while maintaining availability!"
