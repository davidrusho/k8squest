#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Runs as root (through sudo) on the control-plane node. Does for the player what the kubeadm
# init output tells them to do in level 72: copy /etc/kubernetes/admin.conf to
# $HOME/.kube/config of the user who runs `limactl shell`, so kubectl works there. Used by the
# levels that start with a cluster already built.
set -eu
U=${SUDO_USER:-}
[ -n "$U" ] && [ "$U" != root ] || exit 0
HOME_DIR=$(getent passwd "$U" | cut -d: -f6)
mkdir -p "$HOME_DIR/.kube"
cp /etc/kubernetes/admin.conf "$HOME_DIR/.kube/config"
chown -R "$U": "$HOME_DIR/.kube"
