#!/bin/bash
# Runs as root on controlplane (via cka-kubeadm run-on): a fresh answer directory and a real snapshot at /opt/backup.db.
set -e
rm -rf /opt/course/kubeadm
mkdir -p /opt/course
mkdir -m 1777 /opt/course/kubeadm
rm -f /opt/backup.db
ETCDCTL_API=3 etcdctl --endpoints=https://127.0.0.1:2379 --cacert=/etc/kubernetes/pki/etcd/ca.crt --cert=/etc/kubernetes/pki/etcd/server.crt --key=/etc/kubernetes/pki/etcd/server.key snapshot save /opt/backup.db
