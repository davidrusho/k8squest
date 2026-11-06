#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔍 Validating Level 30: Headless Service for StatefulSet..."
echo ""

# Stage 1: Check if service exists
echo "📋 Stage 1: Checking if service exists..."
if ! kubectl get service web-cluster -n k8squest &>/dev/null; then
    echo -e "${RED}❌ Service 'web-cluster' not found in namespace 'k8squest'${NC}"
    echo ""
    echo "💡 Make sure to apply your fixed configuration with the service definition."
    exit 1
fi
echo -e "${GREEN}✓ Service exists${NC}"
echo ""

# Stage 2: Check if service is headless
echo "📋 Stage 2: Checking if service is headless (clusterIP: None)..."
CLUSTER_IP=$(kubectl get service web-cluster -n k8squest -o jsonpath='{.spec.clusterIP}')

if [ "$CLUSTER_IP" != "None" ]; then
    echo -e "${RED}❌ Service has ClusterIP: $CLUSTER_IP (expected: None)${NC}"
    echo ""
    echo "💡 Problem: StatefulSets need headless services for per-pod DNS"
    echo ""
    echo "📚 What's a headless service?"
    echo "   • Regular service: clusterIP assigned (e.g., 10.96.100.50)"
    echo "   • Headless service: clusterIP: None"
    echo ""
    echo "🔍 Why StatefulSets need headless services:"
    echo "   Regular ClusterIP service provides:"
    echo "   ├─ service-name.namespace.svc.cluster.local → random pod (load balanced)"
    echo "   └─ Cannot reach specific pods by name"
    echo ""
    echo "   Headless service provides:"
    echo "   ├─ pod-0.service-name.namespace.svc.cluster.local → web-0 pod"
    echo "   ├─ pod-1.service-name.namespace.svc.cluster.local → web-1 pod"
    echo "   └─ pod-2.service-name.namespace.svc.cluster.local → web-2 pod"
    echo ""
    echo "🔧 Fix: Set clusterIP to None:"
    echo "   spec:"
    echo "     clusterIP: None  # Makes it headless"
    exit 1
fi
echo -e "${GREEN}✓ Service is headless (clusterIP: None)${NC}"
echo ""

# Stage 3: Check if StatefulSet exists
echo "📋 Stage 3: Checking if StatefulSet exists..."
if ! kubectl get statefulset web -n k8squest &>/dev/null; then
    echo -e "${RED}❌ StatefulSet 'web' not found in namespace 'k8squest'${NC}"
    exit 1
fi
echo -e "${GREEN}✓ StatefulSet exists${NC}"
echo ""

# Stage 4: Check StatefulSet pods
echo "📋 Stage 4: Waiting for StatefulSet pods to be ready..."
TIMEOUT=60
ELAPSED=0
while [ $ELAPSED -lt $TIMEOUT ]; do
    READY_PODS=$(kubectl get pods -n k8squest -l app=web-cluster -o jsonpath='{range .items[*]}{.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}' | grep -c "True") || true
    READY_PODS=${READY_PODS:-0}
    EXPECTED_PODS=$(kubectl get statefulset web -n k8squest -o jsonpath='{.spec.replicas}')
    
    if [ "$READY_PODS" -eq "$EXPECTED_PODS" ]; then
        break
    fi
    
    echo "   Waiting for pods... ($READY_PODS/$EXPECTED_PODS ready)"
    sleep 3
    ELAPSED=$((ELAPSED + 3))
done

if [ "$READY_PODS" -ne "$EXPECTED_PODS" ]; then
    echo -e "${RED}❌ Not all StatefulSet pods are ready ($READY_PODS/$EXPECTED_PODS)${NC}"
    echo ""
    echo "💡 Check pod status:"
    echo "   kubectl get pods -n k8squest -l app=web-cluster"
    exit 1
fi
echo -e "${GREEN}✓ All $EXPECTED_PODS StatefulSet pods are ready${NC}"
echo ""

# Stage 5: Verify per-pod DNS resolution
echo "📋 Stage 5: Testing per-pod DNS resolution..."

# Per-pod DNS is published for the Service named in spec.serviceName
SERVICE_NAME=$(kubectl get statefulset web -n k8squest -o jsonpath='{.spec.serviceName}')
if [ "$SERVICE_NAME" != "web-cluster" ]; then
    echo -e "${RED}❌ StatefulSet serviceName is '${SERVICE_NAME:-none}' (expected: web-cluster)${NC}"
    echo ""
    echo "💡 Per-pod DNS names come from the Service that spec.serviceName points to."
    exit 1
fi

# hostAliases would answer the lookups from /etc/hosts instead of cluster DNS
if [ -n "$(kubectl get statefulset web -n k8squest -o jsonpath='{.spec.template.spec.hostAliases}')" ]; then
    echo -e "${RED}❌ The StatefulSet pod template defines hostAliases, so names are answered from /etc/hosts, not cluster DNS${NC}"
    echo ""
    echo "💡 Remove hostAliases and let the headless Service provide the per-pod names."
    exit 1
fi

# Resolve each per-pod name from inside an existing StatefulSet pod (read-only: nothing is created).
# A pod's own name is written into its /etc/hosts by the kubelet, so ask a DIFFERENT pod:
# web-0's name from web-1, every other name from web-0.
POD_COUNT=$(kubectl get statefulset web -n k8squest -o jsonpath='{.spec.replicas}')
DNS_SUCCESS=true
if [ "${POD_COUNT:-0}" -lt 2 ]; then
    echo -e "${RED}❌ StatefulSet has ${POD_COUNT:-0} replica(s); this level expects 3${NC}"
    echo ""
    echo "💡 Per-pod DNS is checked from one pod to another, so at least two pods are needed."
    exit 1
fi

# Right after the Service becomes headless the per-pod records can lag, so each lookup is retried
DNS_WAIT=${LEVEL30_DNS_WAIT:-30}
DNS_INTERVAL=${LEVEL30_DNS_INTERVAL:-3}

for i in $(seq 0 $((POD_COUNT - 1))); do
    POD_DNS="web-$i.web-cluster.k8squest.svc.cluster.local"
    echo "   Testing: $POD_DNS"
    EXEC_POD=web-0
    [ "$i" = 0 ] && EXEC_POD=web-1

    END=$((SECONDS + DNS_WAIT))
    while true; do
        FAIL_MSG=""
        POD_IP=$(kubectl get pod "web-$i" -n k8squest -o jsonpath='{.status.podIP}')
        if ! RESOLVED=$(kubectl exec -n k8squest "$EXEC_POD" -- getent ahosts "$POD_DNS" 2>/dev/null); then
            FAIL_MSG="DNS resolution failed for $POD_DNS"
        elif [ -n "$POD_IP" ] && echo "$RESOLVED" | awk '{print $1}' | grep -qxF "$POD_IP"; then
            break
        else
            FAIL_MSG="DNS mismatch: resolved to $(echo "$RESOLVED" | awk '{print $1}' | sort -u | tr '\n' ' '), expected ${POD_IP:-no pod IP}"
        fi
        [ $SECONDS -ge $END ] && break
        sleep "$DNS_INTERVAL"
    done

    if [ -z "$FAIL_MSG" ]; then
        echo -e "${GREEN}   ✓ $POD_DNS → $POD_IP${NC}"
    else
        echo -e "${RED}   ❌ $FAIL_MSG${NC}"
        DNS_SUCCESS=false
    fi
done

if [ "$DNS_SUCCESS" = false ]; then
    echo -e "${RED}❌ Per-pod DNS resolution failed${NC}"
    echo ""
    echo "💡 This usually means the service is not configured as headless."
    echo "   Make sure: spec.clusterIP: None"
    exit 1
fi
echo ""

# Stage 6: Verify service endpoints
echo "📋 Stage 6: Verifying service endpoints..."
ENDPOINTS=$(kubectl get endpoints web-cluster -n k8squest -o jsonpath='{.subsets[*].addresses[*].ip}' | wc -w)
if [ "$ENDPOINTS" -ne "$POD_COUNT" ]; then
    echo -e "${RED}❌ Expected $POD_COUNT endpoints, found $ENDPOINTS${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Service has $ENDPOINTS endpoints (matches pod count)${NC}"
echo ""

# Stage 7: Final validation
echo "📋 Stage 7: Final validation..."
echo -e "${GREEN}✓ All checks passed!${NC}"
echo ""
echo "🎉 Success! Your StatefulSet has stable network identities"
echo ""
echo "📊 StatefulSet Details:"
echo "   • Pods: $POD_COUNT"
echo "   • Service: web-cluster (headless)"
echo "   • ClusterIP: None"
echo ""
echo "🔗 Per-Pod DNS Names:"
for i in $(seq 0 $((POD_COUNT - 1))); do
    POD_IP=$(kubectl get pod "web-$i" -n k8squest -o jsonpath='{.status.podIP}')
    echo "   • web-$i.web-cluster.k8squest.svc.cluster.local → $POD_IP"
done
echo ""
echo "💡 Headless Service Benefits:"
echo "   ✅ Each pod gets a stable DNS name"
echo "   ✅ Direct pod-to-pod communication"
echo "   ✅ No load balancing (connect to specific pod)"
echo "   ✅ Perfect for StatefulSets, databases, clustered apps"
echo ""
echo "📚 Use cases:"
echo "   • Databases (MySQL replication, MongoDB replica sets)"
echo "   • Message queues (Kafka, RabbitMQ clusters)"
echo "   • Distributed systems (etcd, Zookeeper)"
echo "   • Any app needing stable pod identities"
echo ""

exit 0
