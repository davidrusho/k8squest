#!/bin/bash

# Check PDB configuration
MIN_AVAILABLE=$(kubectl get pdb db-proxy-pdb -n k8squest -o jsonpath='{.spec.minAvailable}' 2>/dev/null)
MAX_UNAVAILABLE=$(kubectl get pdb db-proxy-pdb -n k8squest -o jsonpath='{.spec.maxUnavailable}' 2>/dev/null)
REPLICAS=$(kubectl get deployment database-proxy -n k8squest -o jsonpath='{.spec.replicas}' 2>/dev/null)

# Check if PDB allows evictions
ALLOWED=$(kubectl get pdb db-proxy-pdb -n k8squest -o jsonpath='{.status.disruptionsAllowed}' 2>/dev/null)
ALLOWED=${ALLOWED:-0}

# A PDB value is a number or a percentage; percentages round up
to_pods() {
    if [[ "$1" == *"%"* ]]; then
        echo $(( (${1%\%} * REPLICAS + 99) / 100 ))
    else
        echo "$1"
    fi
}

# Pods that must stay up, however the budget is written
if [ -n "$MIN_AVAILABLE" ]; then
    MIN_PODS=$(to_pods "$MIN_AVAILABLE")
    BUDGET="minAvailable: $MIN_AVAILABLE"
elif [ -n "$MAX_UNAVAILABLE" ]; then
    MIN_PODS=$((REPLICAS - $(to_pods "$MAX_UNAVAILABLE")))
    BUDGET="maxUnavailable: $MAX_UNAVAILABLE"
else
    echo "❌ PDB has neither minAvailable nor maxUnavailable"
    exit 1
fi

if [ "$MIN_PODS" -ge "$REPLICAS" ]; then
    echo "❌ PDB is too restrictive!"
    echo "   $BUDGET keeps $MIN_PODS of $REPLICAS replicas up"
    echo "   This blocks ALL evictions - node drains will fail!"
    exit 1
fi

if [ "$MIN_PODS" -le 0 ]; then
    echo "❌ PDB protects nothing!"
    echo "   $BUDGET lets every replica ($REPLICAS) be evicted at once"
    echo "   Keep at least one pod available while allowing evictions"
    exit 1
fi

if [ "$ALLOWED" -gt 0 ]; then
    echo "✅ PDB allows evictions"
    echo "   $BUDGET (keeps $MIN_PODS pods running)"
    echo "   Replicas: $REPLICAS"
    echo "   Disruptions allowed: $ALLOWED"
    exit 0
else
    echo "❌ PDB currently blocks all disruptions"
    echo "   Disruptions allowed: $ALLOWED"
    exit 1
fi
