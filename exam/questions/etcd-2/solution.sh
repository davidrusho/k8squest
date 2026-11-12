#!/bin/bash
# Runs as root on controlplane (via cka-kubeadm run-on).
grep -- '--data-dir' /etc/kubernetes/manifests/etcd.yaml > /opt/course/kubeadm/etcd-datadir.txt
