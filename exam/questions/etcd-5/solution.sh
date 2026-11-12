#!/bin/bash
# Runs as root on controlplane (via cka-kubeadm run-on).
etcdutl --data-dir /var/lib/etcd-restore snapshot restore /opt/backup.db
