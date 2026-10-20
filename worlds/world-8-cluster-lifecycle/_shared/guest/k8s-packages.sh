#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Runs as root inside a node. Usage: k8s-packages.sh <minor, e.g. v1.37> <package version, e.g. 1.37.1-1.1>
# Points apt at the pkgs.k8s.io repository for that minor release and installs kubelet,
# kubeadm and kubectl at exactly that version (held), per
# https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/install-kubeadm/
set -eu
MINOR=$1 PKG=$2
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a
exec 3>&1 1>/tmp/k8squest-packages.log 2>&1
fail() { tail -20 /tmp/k8squest-packages.log >&3; exit 1; }
trap '[ $? = 0 ] || fail' EXIT
if dpkg-query -W -f='${Version}' kubeadm 2>/dev/null | grep -qx "$PKG" \
   && dpkg-query -W -f='${Version}' kubelet 2>/dev/null | grep -qx "$PKG" \
   && dpkg-query -W -f='${Version}' kubectl 2>/dev/null | grep -qx "$PKG" \
   && grep -q "stable:/$MINOR/" /etc/apt/sources.list.d/kubernetes.list 2>/dev/null; then
    exit 0
fi
apt-get update -qq
apt-get install -y -qq apt-transport-https ca-certificates curl gpg >/dev/null
mkdir -p -m 755 /etc/apt/keyrings
[ -s /etc/apt/keyrings/kubernetes-apt-keyring.gpg ] || \
    curl -fsSL "https://pkgs.k8s.io/core:/stable:/$MINOR/deb/Release.key" | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/$MINOR/deb/ /" > /etc/apt/sources.list.d/kubernetes.list
apt-mark unhold kubelet kubeadm kubectl >/dev/null 2>&1 || true
apt-get update -qq
apt-get install -y -qq --allow-downgrades --allow-change-held-packages "kubelet=$PKG" "kubeadm=$PKG" "kubectl=$PKG" >/dev/null
apt-mark hold kubelet kubeadm kubectl >/dev/null
systemctl enable kubelet >/dev/null 2>&1 || true
