#!/bin/bash

echo "🔍 Checking resource namespaces..."

# Check if resources exist in k8squest namespace
POD_EXISTS=$(kubectl get pod client-app -n k8squest 2>/dev/null)
SERVICE_EXISTS=$(kubectl get service backend-service -n k8squest 2>/dev/null)

# Check if they're in wrong namespace
POD_IN_DEFAULT=$(kubectl get pod client-app -n default 2>/dev/null)
SERVICE_IN_DEFAULT=$(kubectl get service backend-service -n default 2>/dev/null)

POD_PHASE=$(kubectl get pod client-app -n k8squest -o jsonpath='{.status.phase}' 2>/dev/null)

if [[ -n "$POD_EXISTS" ]] && [[ -n "$SERVICE_EXISTS" ]] && [[ "$POD_PHASE" == "Running" ]]; then
    echo "   Pod: ✅ Found in k8squest namespace and Running"
    echo "   Service: ✅ Found in k8squest namespace"
    echo "✅ Resources correctly deployed to k8squest namespace"
    exit 0
else
    echo "❌ Resources not found in k8squest namespace"
    if [[ -n "$POD_IN_DEFAULT" ]] || [[ -n "$SERVICE_IN_DEFAULT" ]]; then
        echo "💡 Found resources in 'default' namespace - they should be in 'k8squest'"
    fi
    [[ -n "$POD_EXISTS" ]] && [[ "$POD_PHASE" != "Running" ]] && echo "💡 The pod exists in k8squest but is $POD_PHASE, not Running"
    echo "💡 Check: kubectl get all -n k8squest"
    echo "💡 Check: kubectl get all -n default"
    exit 1
fi
