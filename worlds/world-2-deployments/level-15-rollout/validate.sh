#!/bin/bash

# Check rollout strategy
MAX_UNAVAILABLE=$(kubectl get deployment critical-api -n k8squest -o jsonpath='{.spec.strategy.rollingUpdate.maxUnavailable}' 2>/dev/null)

# Recreate stops every pod before starting new ones: that is the outage this level is about
STRATEGY_TYPE=$(kubectl get deployment critical-api -n k8squest -o jsonpath='{.spec.strategy.type}' 2>/dev/null)
if [ "$STRATEGY_TYPE" != "RollingUpdate" ]; then
    echo "❌ Strategy type is '${STRATEGY_TYPE:-unknown}', it must be RollingUpdate"
    echo "   Recreate takes down ALL pods before the new ones start!"
    exit 1
fi

# Omitted maxUnavailable means the Kubernetes default, 25% (RollingUpdate only)
MAX_UNAVAILABLE=${MAX_UNAVAILABLE:-25%}

REPLICAS=$(kubectl get deployment critical-api -n k8squest -o jsonpath='{.spec.replicas}' 2>/dev/null)

# maxUnavailable may be a number or a percentage (percentages round down, as the Deployment controller does)
if [[ "$MAX_UNAVAILABLE" == *"%"* ]]; then
    PERCENT=${MAX_UNAVAILABLE%\%}
    if [ "$PERCENT" -ge 100 ]; then
        echo "❌ maxUnavailable is set to $MAX_UNAVAILABLE (too dangerous!)"
        echo "   This can take down ALL pods simultaneously during updates!"
        exit 1
    fi
    UNAVAILABLE_PODS=$((PERCENT * REPLICAS / 100))
else
    UNAVAILABLE_PODS=$MAX_UNAVAILABLE
fi

# Check if it's a safe number (for 3 replicas, max 1 or 2 unavailable is safe)
if [ "$UNAVAILABLE_PODS" -ge "$REPLICAS" ]; then
    echo "❌ maxUnavailable ($MAX_UNAVAILABLE) >= replicas ($REPLICAS)"
    echo "   This can take down ALL pods simultaneously!"
    exit 1
fi

# Check all pods are ready
READY=$(kubectl get deployment critical-api -n k8squest -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
DESIRED=$(kubectl get deployment critical-api -n k8squest -o jsonpath='{.spec.replicas}' 2>/dev/null)

if [ "$READY" = "$DESIRED" ] && [ "$UNAVAILABLE_PODS" -lt "$REPLICAS" ]; then
    echo "✅ Rollout strategy is safe"
    echo "   maxUnavailable: $MAX_UNAVAILABLE (ensures at least $((REPLICAS - UNAVAILABLE_PODS)) pods always running)"
    echo "   All $READY/$DESIRED pods are ready"
    exit 0
else
    echo "⏳ Waiting for rollout to complete"
    echo "   Ready: $READY/$DESIRED"
    exit 1
fi
