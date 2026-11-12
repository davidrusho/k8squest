#!/bin/bash
# timeout: 300
# Runs as root on controlplane (via cka-kubeadm run-on).
# the container log names the problem:  crictl ps -a | grep kube-apiserver ; crictl logs <container-id>
sed -i 's#--etcd-servers=https://127.0.0.1:2370#--etcd-servers=https://127.0.0.1:2379#' /etc/kubernetes/manifests/kube-apiserver.yaml
for _ in $(seq 1 60); do
  if kubectl --kubeconfig /etc/kubernetes/admin.conf get --raw /readyz --request-timeout=5s > /dev/null 2>&1; then break; fi
  sleep 5
done
