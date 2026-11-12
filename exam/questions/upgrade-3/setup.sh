#!/bin/bash
# timeout: 300
# Runs as root on controlplane (via cka-kubeadm run-on): the repository is on v1.37 and the kubeadm package is the latest 1.37 patch.
set -eu
export DEBIAN_FRONTEND=noninteractive
# the package repository already points at the 1.37 minor release when the task starts
sed -i 's#/core:/stable:/v1\.36/#/core:/stable:/v1.37/#' /etc/apt/sources.list.d/kubernetes.list
grep -Fq 'core:/stable:/v1.37/' /etc/apt/sources.list.d/kubernetes.list || { echo "kubernetes.list does not point at v1.37"; exit 1; }
apt-get update -qq
V=$(apt-cache madison kubeadm | awk '$3 ~ /^1\.37\./ {print $3}' | sort -V | tail -n 1)
[ -n "$V" ] || { echo "no 1.37 kubeadm package in the repository"; exit 1; }
apt-mark unhold kubeadm
apt-get install -y -qq kubeadm="$V"
apt-mark hold kubeadm
