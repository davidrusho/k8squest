#!/bin/bash
# node: node01
# Runs as root on node01 (via cka-kubeadm run-on): a wrong path for the kubelet configuration file in the kubelet's systemd
# drop-in (config.yaml written as config.yml), so the kubelet exits at start.
set -eu
F=$(systemctl show -p DropInPaths --value kubelet | tr ' ' '\n' | grep '10-kubeadm.conf$' | head -n 1)
[ -n "$F" ] && [ -f "$F" ] || { echo "kubelet drop-in 10-kubeadm.conf not found"; exit 1; }
grep -Fq -- '--config=/var/lib/kubelet/config.yaml' "$F" || { echo "$F has no --config=/var/lib/kubelet/config.yaml"; exit 1; }
sed -i 's#--config=/var/lib/kubelet/config\.yaml#--config=/var/lib/kubelet/config.yml#' "$F"
systemctl daemon-reload
systemctl restart kubelet || true
sleep 5
if systemctl is-active --quiet kubelet; then echo "the kubelet is still active"; exit 1; fi
