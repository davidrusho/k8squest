#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Runs as root inside a World 8 node. Puts the machine into the state level 71 teaches:
# swap off for good, the overlay and br_netfilter modules loaded now and at every boot,
# IPv4 forwarding on, and containerd configured for the systemd cgroup driver.
# https://kubernetes.io/docs/setup/production-environment/container-runtimes/
set -eu
swapoff -a
sed -i -E '/^[^#].*[[:space:]]swap[[:space:]]/ s/^/#/' /etc/fstab
rm -f /swapfile
printf 'overlay\nbr_netfilter\n' > /etc/modules-load.d/k8s.conf
modprobe overlay
modprobe br_netfilter
printf 'net.ipv4.ip_forward = 1\n' > /etc/sysctl.d/k8s.conf
sysctl --system >/dev/null
mkdir -p /etc/containerd
containerd config default > /etc/containerd/config.toml
sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
systemctl reset-failed containerd 2>/dev/null
systemctl restart containerd
systemctl enable kubelet >/dev/null 2>&1 || true
