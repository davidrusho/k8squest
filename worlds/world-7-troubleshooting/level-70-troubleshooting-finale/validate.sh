#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
validate_context
NAMESPACE="${NAMESPACE:-k8squest}"
CP="k8squest-multinode-control-plane"
LOST="k8squest-multinode-worker"
SNAP=/var/lib/etcd/k8squest-snapshot.db

echo "🔍 Part 1, stage 1: Does the snapshot file exist on the control-plane node?"
if ! docker exec "$CP" test -s "$SNAP" 2>/dev/null; then
    echo "❌ $SNAP does not exist (or is empty) on $CP"
    echo "💡 etcd's pod can write to /var/lib/etcd, which is a hostPath: kubectl -n kube-system exec etcd-$CP -- etcdctl ... snapshot save $SNAP"
    exit 1
fi
echo "✅ $SNAP exists"

echo ""
echo "🔍 Part 1, stage 2: Is it a valid snapshot with data in it?"
STATUS=$(kubectl --request-timeout=30s -n kube-system exec "etcd-$CP" -- etcdutl snapshot status "$SNAP" -w json 2>/dev/null)
KEYS=$(printf '%s' "$STATUS" | grep -o '"totalKey":[0-9]*' | cut -d: -f2)
if [ -z "$KEYS" ] || [ "$KEYS" -lt 1 ]; then
    echo "❌ etcdutl snapshot status did not report a valid snapshot (got: ${STATUS:-nothing})"
    echo "💡 kubectl -n kube-system exec etcd-$CP -- etcdutl snapshot status $SNAP -w table"
    exit 1
fi
echo "✅ valid snapshot, $KEYS keys"

echo ""
echo "🔍 Part 1, stage 3: Was it taken from THIS cluster, after the window opened?"
if ! docker exec "$CP" grep -qa 'maintenance-marker' "$SNAP" 2>/dev/null; then
    echo "❌ The snapshot does not contain the maintenance-marker ConfigMap, so it is not a snapshot of this cluster's current data"
    exit 1
fi
echo "✅ the snapshot contains the maintenance-marker ConfigMap"

echo ""
echo "🔍 Part 2, stage 1: Is the lost worker out of service?"
if [ "$(kubectl --request-timeout=10s get node "$LOST" -o jsonpath='{.spec.unschedulable}' 2>/dev/null)" != "true" ]; then
    echo "❌ $LOST is not cordoned (SchedulingDisabled)"
    echo "💡 kubectl cordon $LOST   (kubectl drain does this too)"
    exit 1
fi
echo "✅ $LOST is cordoned"

echo ""
echo "🔍 Part 2, stage 2: Does the whole shop run on the remaining worker?"
if [ "$(kubectl get deployment shop -n "$NAMESPACE" -o jsonpath='{.spec.replicas}')" != "4" ]; then
    echo "❌ The shop Deployment must keep 4 replicas"
    exit 1
fi
PODS=$(pod_nodes "$NAMESPACE" app=shop)
ON_LOST=$(printf '%s\n' "$PODS" | grep -c " $LOST\$")
if [ "$ON_LOST" != "0" ]; then
    echo "❌ $ON_LOST shop pod(s) are still assigned to $LOST (pods that are Terminating do not count)"
    echo "💡 kubectl get pods -n $NAMESPACE -o wide"
    exit 1
fi
RUNNING=$(running_nodes "$NAMESPACE" app=shop | grep -c .)
ELSEWHERE=$(running_nodes "$NAMESPACE" app=shop | grep -c '^k8squest-multinode-worker2$')
if [ "$RUNNING" != "4" ] || [ "$ELSEWHERE" != "4" ]; then
    echo "❌ $ELSEWHERE of 4 shop pods are Running on k8squest-multinode-worker2 ($RUNNING Running in total)"
    exit 1
fi
echo "✅ 4 shop pods Running on k8squest-multinode-worker2, none on $LOST"

echo ""
echo "🎉 SUCCESS! The data store is backed up and the lost node's workload has moved."
exit 0
