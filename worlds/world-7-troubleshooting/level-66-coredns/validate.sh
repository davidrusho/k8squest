#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
validate_context
NAMESPACE="${NAMESPACE:-k8squest}"

echo "🔍 Stage 1: Is CoreDNS running?"
READY=$(kubectl --request-timeout=10s get deployment coredns -n kube-system -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
if [ "${READY:-0}" -lt 1 ]; then
    echo "❌ CoreDNS has ${READY:-0} ready replicas"
    echo "💡 kubectl get deployment,pods -n kube-system -l k8s-app=kube-dns"
    exit 1
fi
echo "✅ CoreDNS has $READY ready replica(s)"

echo ""
echo "🔍 Stage 2: Is it configured for the cluster's domain?"
CF=$(kubectl get configmap coredns -n kube-system -o jsonpath='{.data.Corefile}' 2>/dev/null)
if ! printf '%s\n' "$CF" | grep -Eq '^[[:space:]]*kubernetes[[:space:]]+cluster\.local[[:space:]]'; then
    echo "❌ The Corefile's kubernetes plugin does not serve cluster.local"
    echo "💡 kubectl get configmap coredns -n kube-system -o yaml"
    exit 1
fi
echo "✅ kubernetes plugin serves cluster.local"

echo ""
echo "🔍 Stage 3: Does a lookup from a pod work?"
if ! kubectl exec -n "$NAMESPACE" dns-client -- nslookup web.k8squest.svc.cluster.local >/dev/null 2>&1; then
    echo "❌ nslookup web.k8squest.svc.cluster.local fails inside dns-client"
    echo "💡 kubectl exec -n $NAMESPACE dns-client -- nslookup web.k8squest.svc.cluster.local"
    echo "   (CoreDNS reloads its Corefile within about two minutes, or restart it: kubectl rollout restart deployment/coredns -n kube-system)"
    exit 1
fi
if ! kubectl exec -n "$NAMESPACE" dns-client -- nslookup kubernetes.default.svc.cluster.local >/dev/null 2>&1; then
    echo "❌ nslookup kubernetes.default.svc.cluster.local fails"
    exit 1
fi
echo "✅ web.k8squest.svc.cluster.local and kubernetes.default.svc.cluster.local resolve"

echo ""
echo "🎉 SUCCESS! Cluster DNS answers again."
exit 0
