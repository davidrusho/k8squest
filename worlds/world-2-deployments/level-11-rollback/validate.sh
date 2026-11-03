#!/bin/bash

# Check if deployment is healthy: the current spec has fully rolled out, so pods of the
# previous ReplicaSet cannot satisfy the ready count
READY_REPLICAS=$(kubectl get deployment web-app -n k8squest -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
DESIRED_REPLICAS=$(kubectl get deployment web-app -n k8squest -o jsonpath='{.spec.replicas}' 2>/dev/null)
GENERATION=$(kubectl get deployment web-app -n k8squest -o jsonpath='{.metadata.generation}' 2>/dev/null)
OBSERVED=$(kubectl get deployment web-app -n k8squest -o jsonpath='{.status.observedGeneration}' 2>/dev/null)
UPDATED=$(kubectl get deployment web-app -n k8squest -o jsonpath='{.status.updatedReplicas}' 2>/dev/null)
TOTAL=$(kubectl get deployment web-app -n k8squest -o jsonpath='{.status.replicas}' 2>/dev/null)
AVAILABLE=$(kubectl get deployment web-app -n k8squest -o jsonpath='{.status.availableReplicas}' 2>/dev/null)

# Also check that we're not on the broken image
CURRENT_IMAGE=$(kubectl get deployment web-app -n k8squest -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null)

if [ "$READY_REPLICAS" = "$DESIRED_REPLICAS" ] && [ "${READY_REPLICAS:-0}" -gt 0 ] && [[ ! "$CURRENT_IMAGE" =~ "nonexistent" ]] \
    && [ "$OBSERVED" = "$GENERATION" ] && [ "$UPDATED" = "$DESIRED_REPLICAS" ] \
    && [ "$TOTAL" = "$DESIRED_REPLICAS" ] && [ "$AVAILABLE" = "$DESIRED_REPLICAS" ]; then
    echo "✅ Deployment is healthy with $READY_REPLICAS/$DESIRED_REPLICAS ready replicas"
    echo "   Image successfully rolled back to: $CURRENT_IMAGE"
    exit 0
else
    echo "❌ Deployment not healthy"
    echo "   Ready replicas: $READY_REPLICAS, Desired: $DESIRED_REPLICAS"
    echo "   Updated (current spec): ${UPDATED:-0}, Total: ${TOTAL:-0}, Available: ${AVAILABLE:-0}"
    echo "   Current image: $CURRENT_IMAGE"
    if [[ "$CURRENT_IMAGE" =~ "nonexistent" ]]; then
        echo "   ⚠️  Still using the broken image!"
    fi
    exit 1
fi
