#!/bin/bash
# timeout: 400
# Runs as root on controlplane (via cka-kubeadm run-on): waits until node01 reports NotReady. The level runs setup-node01.sh
# (which stops the kubelet on node01) first.
set -eu
KC="kubectl --kubeconfig /etc/kubernetes/admin.conf"
for _ in $(seq 1 60); do
  s=$($KC get node node01 --request-timeout=5s -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null) || s=
  if [ "$s" != True ] && [ -n "$s" ]; then exit 0; fi
  sleep 5
done
echo "node01 never became NotReady"
exit 1
