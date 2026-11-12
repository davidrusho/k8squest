#!/bin/bash
# timeout: 900
# Runs as root on controlplane (via cka-kubeadm run-on): the control plane is upgraded to the latest 1.37 patch (kubeadm package and kubeadm upgrade apply) and node controlplane is drained.
set -eu
export DEBIAN_FRONTEND=noninteractive
KC="kubectl --kubeconfig /etc/kubernetes/admin.conf"
waitapi() {
  for _ in $(seq 1 60); do
    if $KC get --raw /readyz --request-timeout=5s > /dev/null 2>&1; then return 0; fi
    sleep 5
  done
  echo "the API server does not answer"; exit 1
}
# the package repository already points at the 1.37 minor release when the task starts
sed -i 's#/core:/stable:/v1\.36/#/core:/stable:/v1.37/#' /etc/apt/sources.list.d/kubernetes.list
grep -Fq 'core:/stable:/v1.37/' /etc/apt/sources.list.d/kubernetes.list || { echo "kubernetes.list does not point at v1.37"; exit 1; }
apt-get update -qq
V=$(apt-cache madison kubeadm | awk '$3 ~ /^1\.37\./ {print $3}' | sort -V | tail -n 1)
[ -n "$V" ] || { echo "no 1.37 kubeadm package in the repository"; exit 1; }
P=${V%%-*}
apt-mark unhold kubeadm
apt-get install -y -qq kubeadm="$V"
apt-mark hold kubeadm
kubeadm upgrade apply "v$P" -y
waitapi
$KC wait --for=condition=Ready node/controlplane --timeout=180s
$KC drain controlplane --ignore-daemonsets --timeout=240s
