#!/bin/bash
# timeout: 300
# Runs as root on controlplane (via cka-kubeadm run-on).
apt-mark unhold kubeadm
apt-get update
V=$(apt-cache madison kubeadm | awk '$3 ~ /^1\.37\./ {print $3}' | sort -V | tail -n 1)   # latest 1.37 patch, 1.37.x-*
apt-get install -y kubeadm="$V"
apt-mark hold kubeadm
