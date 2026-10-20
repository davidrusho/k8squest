#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Runs as root on the control-plane node. Usage: init-cp.sh <kubernetes version, e.g. v1.37.1>
# kubeadm init with the pod network CIDR flannel expects. The pod network add-on is applied
# separately, because installing it is half of level 72.
# https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/create-cluster-kubeadm/
set -eu
VER=$1
kubeadm config images pull --kubernetes-version="$VER" >/dev/null
kubeadm init --kubernetes-version="$VER" --pod-network-cidr=10.244.0.0/16 > /var/log/k8squest-kubeadm-init.log 2>&1 \
    || { tail -25 /var/log/k8squest-kubeadm-init.log >&2; exit 1; }
