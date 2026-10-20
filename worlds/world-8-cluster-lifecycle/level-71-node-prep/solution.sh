#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Scripted proof of the fix (used by tests/level_harness.py; the engine never runs it).
# The player does this inside the machine: limactl shell k8squest-cp
. ../_shared/lib.sh
limactl shell --workdir /tmp "$CP_VM" sudo bash -s <<'REMOTE'
set -e
swapoff -a
sed -i '/ swap / s/^/#/' /etc/fstab
rm -f /swapfile
printf 'overlay\nbr_netfilter\n' > /etc/modules-load.d/k8s.conf
modprobe overlay
modprobe br_netfilter
echo 'net.ipv4.ip_forward = 1' > /etc/sysctl.d/k8s.conf
sysctl --system >/dev/null
mkdir -p /etc/containerd
containerd config default > /etc/containerd/config.toml
sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
systemctl restart containerd
REMOTE
