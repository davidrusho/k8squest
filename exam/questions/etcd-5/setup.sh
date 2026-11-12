#!/bin/bash
# Runs as root on controlplane (via cka-kubeadm run-on): a snapshot at /opt/backup.db, then a change AFTER the snapshot
# (ConfigMap after-snapshot) so that the live etcd no longer matches the snapshot, and no restore directory.
set -e
rm -f /opt/backup.db
rm -rf /var/lib/etcd-restore
ETCDCTL_API=3 etcdctl --endpoints=https://127.0.0.1:2379 --cacert=/etc/kubernetes/pki/etcd/ca.crt --cert=/etc/kubernetes/pki/etcd/server.crt --key=/etc/kubernetes/pki/etcd/server.key snapshot save /opt/backup.db
kubectl --kubeconfig /etc/kubernetes/admin.conf -n default create configmap after-snapshot --from-literal=note=created-after-the-snapshot --dry-run=client -o yaml | kubectl --kubeconfig /etc/kubernetes/admin.conf apply -f -
