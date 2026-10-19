#!/bin/bash

NAMESPACE="k8squest"
DEPLOYMENT="resource-hungry-app"
QUOTA_NAME="compute-quota"

echo "🔍 VALIDATION STAGE 1: Checking if ResourceQuota exists..."
if ! kubectl get resourcequota $QUOTA_NAME -n $NAMESPACE &>/dev/null; then
    echo "❌ FAILED: ResourceQuota '$QUOTA_NAME' not found"
    exit 1
fi
echo "✅ ResourceQuota exists"

echo ""
echo "🔍 VALIDATION STAGE 2: Checking if Deployment exists..."
if ! kubectl get deployment $DEPLOYMENT -n $NAMESPACE &>/dev/null; then
    echo "❌ FAILED: Deployment '$DEPLOYMENT' not found"
    exit 1
fi
echo "✅ Deployment exists"

echo ""
echo "🔍 VALIDATION STAGE 3: Verifying CPU request in the Pod template is within quota..."

CPU_REQUEST=$(kubectl get deployment $DEPLOYMENT -n $NAMESPACE -o jsonpath='{.spec.template.spec.containers[0].resources.requests.cpu}')
QUOTA_CPU=$(kubectl get resourcequota $QUOTA_NAME -n $NAMESPACE -o jsonpath='{.spec.hard.requests\.cpu}')

if [ -z "$CPU_REQUEST" ]; then
    echo "❌ FAILED: No CPU request set on container"
    echo "💡 Hint: Add resources.requests.cpu to the Pod template"
    exit 1
fi
MEM_REQUEST=$(kubectl get deployment $DEPLOYMENT -n $NAMESPACE -o jsonpath='{.spec.template.spec.containers[0].resources.requests.memory}')
if [ -z "$MEM_REQUEST" ]; then
    echo "❌ FAILED: No memory request set on container"
    echo "💡 Hint: Add resources.requests.memory to the Pod template"
    exit 1
fi

# Convert both to millicores for comparison
to_millicores() {
    local val="$1"
    if [[ $val == *m ]]; then
        echo "${val%m}"
    else
        echo $((val * 1000))
    fi
}

CPU_REQUEST_MILLI=$(to_millicores "$CPU_REQUEST")
QUOTA_CPU_MILLI=$(to_millicores "$QUOTA_CPU")

if [ "$CPU_REQUEST_MILLI" -gt "$QUOTA_CPU_MILLI" ]; then
    echo "❌ FAILED: CPU request ($CPU_REQUEST) exceeds quota ($QUOTA_CPU)"
    echo "💡 Hint: The ReplicaSet cannot create the Pod: kubectl describe rs -n $NAMESPACE"
    echo "💡 Hint: Reduce resources.requests.cpu in the Pod template to fit within quota"
    exit 1
fi
echo "✅ CPU request ($CPU_REQUEST) within quota ($QUOTA_CPU)"

echo ""
echo "🔍 VALIDATION STAGE 4: Checking that the Deployment has a running Pod..."
READY=$(kubectl get deployment $DEPLOYMENT -n $NAMESPACE -o jsonpath='{.status.readyReplicas}')
if [ -z "$READY" ] || [ "$READY" -lt 1 ]; then
    echo "❌ FAILED: Deployment has no ready Pods"
    echo "💡 Hint: Check ReplicaSet events: kubectl describe rs -n $NAMESPACE"
    echo "💡 Hint: Check quota: kubectl describe resourcequota $QUOTA_NAME -n $NAMESPACE"
    exit 1
fi
echo "✅ Pod is Running ($READY ready)"

echo ""
echo "🔍 VALIDATION STAGE 5: Checking quota status..."
QUOTA_USED=$(kubectl get resourcequota $QUOTA_NAME -n $NAMESPACE -o jsonpath='{.status.used}')
if [ -z "$QUOTA_USED" ]; then
    echo "❌ FAILED: Quota not tracking usage properly"
    exit 1
fi
echo "✅ Quota tracking usage correctly"

echo ""
echo "🎉 SUCCESS! All quota validations passed!"
echo "Your Pod is running within namespace resource quotas:"
kubectl describe resourcequota $QUOTA_NAME -n $NAMESPACE | grep -A 6 "Resource"
