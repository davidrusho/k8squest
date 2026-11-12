#!/bin/bash
# timeout: 300
# Runs as root on controlplane (via cka-kubeadm run-on): the API server's --etcd-servers names the wrong etcd port (2370
# instead of 2379), so the kube-apiserver container exits and the API is down.
set -eu
KC="kubectl --kubeconfig /etc/kubernetes/admin.conf"
M=/etc/kubernetes/manifests/kube-apiserver.yaml
grep -Fq -- '--etcd-servers=https://127.0.0.1:2379' "$M" || { echo "$M has no --etcd-servers=https://127.0.0.1:2379"; exit 1; }
sed -i 's#--etcd-servers=https://127.0.0.1:2379#--etcd-servers=https://127.0.0.1:2370#' "$M"
for _ in $(seq 1 30); do
  if ! $KC get --raw /readyz --request-timeout=5s > /dev/null 2>&1; then break; fi
  sleep 5
done
sleep 10
if $KC get --raw /readyz --request-timeout=5s > /dev/null 2>&1; then echo "the API server is still up"; exit 1; fi
