#!/bin/bash
# kubeadm task: runs on k8s-lab as david and reaches controlplane through the root helper.
# Setup restored a snapshot taken between two ConfigMaps: only an etcd that really serves the restored directory has
# before-snapshot and not after-snapshot. A wrong data-dir leaves etcd empty (no nodes, no ConfigMaps).

fail() { echo "❌ $1"; exit 1; }

OUT=$(sudo -n /usr/local/sbin/cka-kubeadm run-on --timeout 150 controlplane 2>&1 <<'EOS'
bad() { echo "FAIL: $1"; exit 3; }
KC="kubectl --kubeconfig /etc/kubernetes/admin.conf --request-timeout=5s"
M=/etc/kubernetes/manifests/etcd.yaml
HP=$(awk '/hostPath:/ {h=1} h && /^ *path:/ {p=$2; h=0} /^ *name: etcd-data$/ && p != "" {print p}' "$M")
[ "$HP" = "/var/lib/etcd-restore" ] || bad "the hostPath of volume etcd-data in $M is '$HP', not /var/lib/etcd-restore"
up=0
for _ in $(seq 1 30); do
  if $KC get --raw /readyz --request-timeout=5s > /dev/null 2>&1; then up=1; break; fi
  sleep 3
done
[ "$up" = 1 ] || bad "the API server does not answer (etcd not running with the new directory?)"
$KC -n default get configmap before-snapshot > /dev/null 2>&1 || bad "ConfigMap before-snapshot is missing: the cluster does not serve the restored data"
if $KC -n default get configmap after-snapshot > /dev/null 2>&1; then bad "ConfigMap after-snapshot still exists: etcd is not serving the restored data directory"; fi
[ "$($KC get nodes -o name | grep -c .)" = 2 ] || bad "the cluster does not list both nodes"
POD=
for _ in $(seq 1 20); do
  POD=$($KC -n kube-system get pod etcd-controlplane -o jsonpath='{.status.phase}/{.status.containerStatuses[0].ready}' 2>/dev/null)
  [ "$POD" = "Running/true" ] && break
  sleep 3
done
[ "$POD" = "Running/true" ] || bad "the etcd Pod is not Running and ready (it is '$POD')"
CC=$($KC -n kube-system get configmap kubeadm-config -o jsonpath='{.data.ClusterConfiguration}')
printf '%s\n' "$CC" | grep -Eq '^[[:space:]]*dataDir: /var/lib/etcd-restore[[:space:]]*$' || bad "etcd.local.dataDir in the kubeadm-config ConfigMap is not /var/lib/etcd-restore"
echo ok
EOS
)
RC=$?
case $RC in
  0) ;;
  3) fail "$(printf '%s\n' "$OUT" | sed -n 's/^FAIL: //p' | head -n 1)" ;;
  *) fail "could not check controlplane (exit $RC): $(echo "$OUT" | tail -n 3)" ;;
esac
echo "✅ etcd serves the restored data from /var/lib/etcd-restore and the kubeadm configuration agrees"
exit 0
