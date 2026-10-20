#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
validate_vms
NAMESPACE="${NAMESPACE:-k8squest}"
SNAP=/var/backups/etcd/k8squest-snapshot.db
fail() { echo "❌ $1"; [ -n "${2:-}" ] && echo "💡 $2"; exit 1; }

echo "🔍 Stage 1: Is there a valid snapshot at $SNAP?"
vm_sh "$CP_VM" "test -s $SNAP" || fail "There is no snapshot at $SNAP" "etcdctl ... snapshot save $SNAP   (on k8squest-cp, as root)"
KEYS=$(vm_sh "$CP_VM" "etcdutl snapshot status $SNAP -w json 2>/dev/null" | grep -o '"totalKey":[0-9]*' | cut -d: -f2)
[ "${KEYS:-0}" -gt 100 ] || fail "$SNAP is not a usable snapshot (keys: ${KEYS:-none})" "etcdutl snapshot status $SNAP -w table"
echo "✅ The snapshot holds $KEYS keys"

echo ""
echo "🔍 Stage 2: Do the API server and etcd answer again?"
wait_admin 90 \
    || fail "The API server does not answer" "are both manifests back in /etc/kubernetes/manifests? sudo crictl ps -a"
etcdctl_cp endpoint health >/dev/null 2>&1 || fail "etcd does not report healthy" "sudo crictl ps -a ; sudo crictl logs <etcd container>"
echo "✅ The API server and etcd are up"

echo ""
echo "🔍 Stage 3: Did etcd come back from a restore?"
NOW=$(etcd_cluster_id)
WAS=$(recall 75-etcd-cluster-id)
[ -n "$NOW" ] && [ -n "$WAS" ] || fail "Could not read the etcd cluster identity"
[ "$NOW" != "$WAS" ] || fail "etcd is still the original cluster: nothing was restored" "etcdutl snapshot restore creates a new data directory; etcd has to use it"
echo "✅ etcd runs from restored data (new cluster identity)"

echo ""
echo "🔍 Stage 4: Is the ledger back, the original one?"
UID_NOW=$(kc -n "$NAMESPACE" get deployment ledger -o jsonpath='{.metadata.uid}' 2>/dev/null)
[ -n "$UID_NOW" ] || fail "The ledger Deployment does not exist" "it was in the snapshot; was the snapshot taken before the delete?"
[ "$UID_NOW" = "$(recall 75-ledger-uid)" ] || fail "The ledger Deployment is a new one, not the restored original" "re-creating it by hand is not a restore"
[ "$(kc -n "$NAMESPACE" get configmap ledger-config -o jsonpath='{.data.period}' 2>/dev/null)" = "2026-Q4" ] \
    || fail "The ConfigMap ledger-config is missing or changed" "it was in the snapshot too"
echo "✅ The ledger Deployment and ConfigMap are back"

echo ""
echo "🔍 Stage 5: Is the cluster healthy again?"
# after a restore the controller manager and scheduler lose their leader lock and restart, and the
# kubelets reconnect: give them up to two minutes
for i in $(seq 1 40); do
    READY=$(kc get nodes --no-headers 2>/dev/null | awk '$2 == "Ready"' | wc -l | tr -d ' ')
    BAD=0
    for c in etcd kube-apiserver kube-controller-manager kube-scheduler; do
        [ "$(kc -n kube-system get pods -l "component=$c" -o jsonpath='{.items[0].status.phase}' 2>/dev/null)" = Running ] || BAD=1
    done
    [ "$READY" = 2 ] && [ $BAD = 0 ] && break
    sleep 3
done
[ "$READY" = 2 ] || fail "$READY of 2 nodes are Ready (the kubelets reconnect within a minute)" "kubectl get nodes"
AV=$(kc -n "$NAMESPACE" get deployment ledger -o jsonpath='{.status.availableReplicas}' 2>/dev/null)
[ "${AV:-0}" = 2 ] || fail "${AV:-0} of 2 ledger replicas are available" "kubectl get pods -n $NAMESPACE"
for c in etcd kube-apiserver kube-controller-manager kube-scheduler; do
    [ "$(kc -n kube-system get pods -l "component=$c" -o jsonpath='{.items[0].status.phase}' 2>/dev/null)" = Running ] \
        || fail "The $c pod is not Running" "kubectl get pods -n kube-system"
done
echo "✅ Both nodes are Ready and the control plane runs"

echo ""
echo "🎉 SUCCESS! You restored the cluster from an etcd snapshot."
exit 0
