#!/bin/bash
# node: node01
# Runs as root on node01 (via cka-kubeadm run-on).
# the kubelet log names the file it cannot read:  journalctl -u kubelet -n 100 --no-pager
F=$(systemctl show -p DropInPaths --value kubelet | tr ' ' '\n' | grep '10-kubeadm.conf$' | head -n 1)
sed -i 's#--config=/var/lib/kubelet/config\.yml#--config=/var/lib/kubelet/config.yaml#' "$F"
systemctl daemon-reload
systemctl restart kubelet
