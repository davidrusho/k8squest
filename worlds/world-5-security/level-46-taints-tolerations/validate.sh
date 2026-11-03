#!/bin/bash

NAMESPACE="k8squest"
POD_NAME="regular-app"

echo "🔍 VALIDATION STAGE 1: Checking that the setup taint is still on a node..."
# Read-only: setup.sh puts the taint on the node; the validator never changes the cluster.
# The node name is not hardcoded (it depends on the cluster name), it is derived from the taint.
TAINTED_NODES=$(kubectl get nodes -o json | jq -r '.items[] | select(any(.spec.taints[]?; .key=="dedicated" and .value=="gpu" and .effect=="NoSchedule")) | .metadata.name')
if [ -z "$TAINTED_NODES" ]; then
    echo "❌ FAILED: No node has the taint dedicated=gpu:NoSchedule"
    echo "💡 Hint: Don't remove the taint - the pod must tolerate it. Restart the level to put it back"
    exit 1
fi
echo "✅ Node has taint: dedicated=gpu (${TAINTED_NODES//$'\n'/, })"

echo ""
echo "🔍 VALIDATION STAGE 2: Checking if pod exists..."
if ! kubectl get pod $POD_NAME -n $NAMESPACE &>/dev/null; then
    echo "❌ FAILED: Pod '$POD_NAME' not found"
    exit 1
fi
echo "✅ Pod exists"

echo ""
echo "🔍 VALIDATION STAGE 3: Checking if pod is Running (not Pending)..."
POD_STATUS=$(kubectl get pod $POD_NAME -n $NAMESPACE -o jsonpath='{.status.phase}')
if [ "$POD_STATUS" = "Pending" ]; then
    echo "❌ FAILED: Pod is still Pending"
    echo "💡 Hint: Check pod events: kubectl describe pod $POD_NAME -n $NAMESPACE"
    echo "💡 Hint: Pod needs toleration matching node taint"
    exit 1
fi
if [ "$POD_STATUS" != "Running" ]; then
    echo "❌ FAILED: Pod is in '$POD_STATUS' state"
    exit 1
fi
echo "✅ Pod is Running"

echo ""
echo "🔍 VALIDATION STAGE 4: Verifying pod has tolerations configured..."
TOLERATIONS=$(kubectl get pod $POD_NAME -n $NAMESPACE -o jsonpath='{.spec.tolerations}')
if [ -z "$TOLERATIONS" ] || [ "$TOLERATIONS" = "null" ]; then
    echo "❌ FAILED: No tolerations configured on pod"
    echo "💡 Hint: Add tolerations to spec.tolerations"
    exit 1
fi
echo "✅ Tolerations are configured"

echo ""
echo "🔍 VALIDATION STAGE 5: Checking toleration matches taint..."
TOLERATION_KEY=$(kubectl get pod $POD_NAME -n $NAMESPACE -o jsonpath='{.spec.tolerations[?(@.key=="dedicated")].key}')
if [ "$TOLERATION_KEY" != "dedicated" ]; then
    echo "❌ FAILED: Toleration key doesn't match taint key 'dedicated'"
    echo "💡 Hint: Toleration key must match taint key exactly"
    exit 1
fi
echo "✅ Toleration key matches taint"

echo ""
echo "🔍 VALIDATION STAGE 6: Verifying pod scheduled on tainted node..."
SCHEDULED_NODE=$(kubectl get pod $POD_NAME -n $NAMESPACE -o jsonpath='{.spec.nodeName}')
if ! echo "$TAINTED_NODES" | grep -qxF "$SCHEDULED_NODE"; then
    echo "❌ FAILED: Pod is on node '$SCHEDULED_NODE', which does not carry the dedicated=gpu taint"
    exit 1
fi
echo "✅ Pod scheduled on node: $SCHEDULED_NODE"

echo ""
echo "🎉 SUCCESS! Pod tolerates node taint and is running!"
echo ""
echo "Taint details:"
kubectl get node $SCHEDULED_NODE -o jsonpath='{.spec.taints[?(@.key=="dedicated")]}' | jq '.'
echo ""
echo "Toleration details:"
kubectl get pod $POD_NAME -n $NAMESPACE -o jsonpath='{.spec.tolerations[?(@.key=="dedicated")]}' | jq '.'
