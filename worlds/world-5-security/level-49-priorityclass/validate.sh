#!/bin/bash

NAMESPACE="k8squest"

echo "🔍 VALIDATION STAGE 1: Checking PriorityClasses exist..."
if ! kubectl get priorityclass high-priority &>/dev/null; then
    echo "❌ FAILED: PriorityClass 'high-priority' not found"
    exit 1
fi
echo "✅ PriorityClasses exist"

echo ""
echo "🔍 VALIDATION STAGE 2: Checking critical pod..."
if ! kubectl get pod critical-api -n $NAMESPACE &>/dev/null; then
    echo "❌ FAILED: Pod 'critical-api' not found"
    exit 1
fi
echo "✅ Critical pod exists"

echo ""
echo "🔍 VALIDATION STAGE 3: Verifying priority assignment..."
PRIORITY_CLASS=$(kubectl get pod critical-api -n $NAMESPACE -o jsonpath='{.spec.priorityClassName}')
if [ "$PRIORITY_CLASS" != "high-priority" ]; then
    echo "❌ FAILED: Critical pod doesn't have high-priority class"
    exit 1
fi
echo "✅ Priority assigned correctly"

echo ""
echo "🔍 VALIDATION STAGE 4: Checking the priority is meaningful..."
CRITICAL_PRIORITY=$(kubectl get pod critical-api -n $NAMESPACE -o jsonpath='{.spec.priority}')
CRITICAL_PRIORITY=${CRITICAL_PRIORITY:-0}
# The dev pod may be gone (preempted); a pod without a class has priority 0
DEV_PRIORITY=$(kubectl get pod dev-workload-1 -n $NAMESPACE -o jsonpath='{.spec.priority}' 2>/dev/null)
DEV_PRIORITY=${DEV_PRIORITY:-0}
PREEMPTION=$(kubectl get priorityclass high-priority -o jsonpath='{.preemptionPolicy}')
if [ "$CRITICAL_PRIORITY" -le 0 ] || [ "$CRITICAL_PRIORITY" -le "$DEV_PRIORITY" ]; then
    echo "❌ FAILED: critical-api priority ($CRITICAL_PRIORITY) must be above the dev workload ($DEV_PRIORITY) and above the default (0)"
    echo "💡 Hint: A higher value means a higher priority"
    exit 1
fi
if [ "$PREEMPTION" = "Never" ]; then
    echo "❌ FAILED: PriorityClass 'high-priority' has preemptionPolicy Never, so it can't preempt lower priority pods"
    exit 1
fi
echo "✅ Priority $CRITICAL_PRIORITY is above the dev workload ($DEV_PRIORITY)"

echo ""
echo "🔍 VALIDATION STAGE 5: Checking pod status..."
POD_STATUS=$(kubectl get pod critical-api -n $NAMESPACE -o jsonpath='{.status.phase}')
if [ "$POD_STATUS" != "Running" ]; then
    echo "❌ FAILED: critical-api is $POD_STATUS, not Running"
    echo "💡 Hint: Check pod events: kubectl describe pod critical-api -n $NAMESPACE"
    exit 1
fi
echo "✅ Pod is $POD_STATUS"

echo ""
echo "🎉 SUCCESS! PriorityClass configured!"
kubectl get priorityclass
