#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
NAMESPACE="${NAMESPACE:-k8squest}"
SA="system:serviceaccount:${NAMESPACE}:reports-sa"

echo "🔍 Stage 1: Can reports-sa read ConfigMaps in $NAMESPACE?"
if [ "$(kubectl auth can-i list configmaps --as="$SA" -n "$NAMESPACE" 2>/dev/null)" != "yes" ]; then
    echo "❌ $SA cannot list configmaps"
    echo "💡 kubectl auth can-i list configmaps --as=$SA -n $NAMESPACE"
    exit 1
fi
echo "✅ list configmaps: yes"

echo ""
echo "🔍 Stage 2: Is access limited to get/list on ConfigMaps?"
EXTRA=$(sa_extra_permissions "$NAMESPACE" reports-sa)
if [ -n "$EXTRA" ]; then
    echo "❌ reports-sa has permissions beyond reading ConfigMaps; fix the binding, do not widen access:"
    echo "$EXTRA"
    exit 1
fi
CRBS=$(sa_clusterrolebindings "$NAMESPACE" reports-sa)
if [ -n "$CRBS" ]; then
    echo "❌ ClusterRoleBinding(s) grant reports-sa cluster-wide access: $CRBS"
    exit 1
fi
echo "✅ Only get/list on configmaps, and no ClusterRoleBinding"

echo ""
echo "🔍 Stage 3: Is the pod running?"
if [ "$(kubectl get pod reports-pod -n "$NAMESPACE" -o jsonpath='{.status.phase}' 2>/dev/null)" != "Running" ]; then
    echo "❌ reports-pod is not Running"
    exit 1
fi
echo "✅ Pod is Running"

echo ""
echo "🔍 Stage 4: Is the pod's latest API call successful?"
LAST=$(kubectl logs reports-pod -n "$NAMESPACE" --tail=1 2>/dev/null)
case "$LAST" in
    *"HTTP 200") echo "✅ $LAST" ;;
    *) echo "❌ Latest log line: ${LAST:-<none>} (calls repeat every 5 seconds, so retry)"
       echo "💡 kubectl logs reports-pod -n $NAMESPACE"
       exit 1 ;;
esac

echo ""
echo "🎉 SUCCESS! reports-sa can read ConfigMaps and nothing else."
exit 0
