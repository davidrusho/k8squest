#!/bin/bash
# timeout: 120
# Runs as root on controlplane (via cka-kubeadm run-on). The level runs solution-node01.sh first, on node01 (ssh node01), as root:
#   kubeadm upgrade node
# then this, with kubectl:
kubectl --kubeconfig /etc/kubernetes/admin.conf uncordon node01
