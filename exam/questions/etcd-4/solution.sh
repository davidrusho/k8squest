#!/bin/bash
# Runs as root on controlplane (via cka-kubeadm run-on).
etcdutl --write-out=table snapshot status /opt/backup.db > /opt/course/kubeadm/snapshot-status.txt
