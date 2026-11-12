#!/bin/bash
# timeout: 300
# Runs as root on controlplane (via cka-kubeadm run-on).
kubectl --kubeconfig /etc/kubernetes/admin.conf drain controlplane --ignore-daemonsets
