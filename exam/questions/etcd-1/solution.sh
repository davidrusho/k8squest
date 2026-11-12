#!/bin/bash
# Runs as root on controlplane (via cka-kubeadm run-on).
grep -E -- '--(cert-file|key-file|trusted-ca-file|data-dir)=' /etc/kubernetes/manifests/etcd.yaml > /opt/course/kubeadm/etcd-flags.txt
