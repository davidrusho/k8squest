#!/bin/bash
# timeout: 400
# Runs as root on controlplane (via cka-kubeadm run-on).
KC="kubectl --kubeconfig /etc/kubernetes/admin.conf"
# 1. the etcd static Pod: only the hostPath of the volume etcd-data changes
sed -i 's#^\( *path: \)/var/lib/etcd$#\1/var/lib/etcd-restore#' /etc/kubernetes/manifests/etcd.yaml
# 2. wait until the API serves the restored data (the ConfigMap created after the snapshot is gone)
for _ in $(seq 1 60); do
  if $KC -n default get configmap before-snapshot --request-timeout=5s > /dev/null 2>&1 && ! $KC -n default get configmap after-snapshot --request-timeout=5s > /dev/null 2>&1; then break; fi
  sleep 5
done
# 3. the kubeadm cluster configuration (kept in the restored data) must name the new directory too
$KC -n kube-system get configmap kubeadm-config -o yaml | sed 's#dataDir: /var/lib/etcd$#dataDir: /var/lib/etcd-restore#' | $KC replace -f -
