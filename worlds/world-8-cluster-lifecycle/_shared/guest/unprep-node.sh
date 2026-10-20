#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Runs as root inside a World 8 node. The state level 71 starts from: a node that has the
# packages but none of the preparation. Swap is on (and in /etc/fstab), IPv4 forwarding is
# off, br_netfilter is not loaded and nothing loads it at boot, containerd runs on its
# built-in defaults (no /etc/containerd/config.toml, so no systemd cgroup driver).
# overlay stays loaded: containerd loads it itself the moment it starts.
set -u
if ! swapon --noheadings | grep -q .; then
    fallocate -l 512M /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null
    swapon /swapfile
fi
grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
rm -f /etc/modules-load.d/k8s.conf /etc/sysctl.d/k8s.conf
sysctl -w net.ipv4.ip_forward=0 >/dev/null
rmmod br_netfilter 2>/dev/null
rm -f /etc/containerd/config.toml
systemctl reset-failed containerd 2>/dev/null
systemctl restart containerd
exit 0
