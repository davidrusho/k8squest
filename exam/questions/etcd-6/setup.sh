#!/bin/bash
# Runs as root on controlplane (via cka-kubeadm run-on): ConfigMap before-snapshot, a snapshot at /opt/backup.db, ConfigMap
# after-snapshot (only the live etcd has it), and the snapshot restored into /var/lib/etcd-restore. The etcd static Pod
# still uses /var/lib/etcd.
set -e
KC="kubectl --kubeconfig /etc/kubernetes/admin.conf"
$KC -n kube-system get configmap kubeadm-config -o jsonpath='{.data.ClusterConfiguration}' | grep -Fq 'dataDir: /var/lib/etcd' \
  || { echo "kubeadm-config does not name etcd.local.dataDir /var/lib/etcd"; exit 1; }
rm -f /opt/backup.db
rm -rf /var/lib/etcd-restore
$KC -n default create configmap before-snapshot --from-literal=note=created-before-the-snapshot --dry-run=client -o yaml | $KC apply -f -
ETCDCTL_API=3 etcdctl --endpoints=https://127.0.0.1:2379 --cacert=/etc/kubernetes/pki/etcd/ca.crt --cert=/etc/kubernetes/pki/etcd/server.crt --key=/etc/kubernetes/pki/etcd/server.key snapshot save /opt/backup.db
$KC -n default create configmap after-snapshot --from-literal=note=created-after-the-snapshot --dry-run=client -o yaml | $KC apply -f -
etcdutl --data-dir /var/lib/etcd-restore snapshot restore /opt/backup.db
