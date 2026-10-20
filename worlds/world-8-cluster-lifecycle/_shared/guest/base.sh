#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Runs as root inside a World 8 node, once per machine (a marker file makes it a no-op afterwards).
# Usage: base.sh <kubernetes version, e.g. v1.37.1> <cp|cp-no-etcd|worker>
#
# Puts on the machine what the levels treat as "already there": the containerd package
# (installed, NOT configured: level 71 configures it) and crictl, the images kubeadm init needs for
# that version (so level 72 does not spend minutes downloading them), and on the control
# plane the etcdctl and etcdutl binaries that level 75 uses.
set -eu
VER=$1 ROLE=$2
# sha256 of the etcd release tarballs, from the release's SHA256SUMS (pinned here, not fetched);
# a version or architecture without a pin is refused
ETCD_SHA256_3_7_0_amd64=b05cb07f5686dab8f9cdab89986b44f0dd24aaf5c627176aff325e21fa56f9f0
ETCD_SHA256_3_7_0_arm64=e61a0954fe6a3003ee20f45e773e12e15c58323ea485deb8a55d065170cdafe8
MARK=/var/lib/k8squest/base-$VER-$ROLE
# etcdctl and etcdutl must match the etcd of the cluster kubeadm builds; checked on every call
# (the marker below covers only the packages and images), so another version cannot leave its tools behind
install_etcd_tools() {
    local etcd a want pin T
    etcd=$(kubeadm config images list --kubernetes-version="$VER" | sed -n 's|.*/etcd:\([0-9.]*\)-.*|\1|p')
    [ "$(etcdutl version 2>/dev/null | sed -n 's/^etcdutl version: //p')" = "$etcd" ] && return 0
    case $(uname -m) in x86_64) a=amd64 ;; aarch64) a=arm64 ;; *) echo "unsupported architecture" >&2; return 1 ;; esac
    pin=ETCD_SHA256_$(echo "$etcd" | tr . _)_$a
    want=${!pin:-}
    [ -n "$want" ] || { echo "no pinned sha256 for etcd $etcd ($a)" >&2; return 1; }
    T=$(mktemp -d)
    curl -fsSL "https://github.com/etcd-io/etcd/releases/download/v$etcd/etcd-v$etcd-linux-$a.tar.gz" -o "$T/etcd.tgz"
    echo "$want  $T/etcd.tgz" | sha256sum -c - >/dev/null || { echo "etcd $etcd tarball does not match its pinned sha256" >&2; return 1; }
    tar -xz -C "$T" --strip-components=1 -f "$T/etcd.tgz"
    install -m 755 "$T/etcdctl" "$T/etcdutl" /usr/local/bin/
    rm -rf "$T"
}

export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a
[ -e "$MARK" ] && { [ "$ROLE" != cp ] || install_etcd_tools; exit 0; }
apt-get update -qq >/dev/null 2>&1
apt-get install -y -qq containerd socat conntrack cri-tools >/dev/null 2>&1
printf 'runtime-endpoint: unix:///run/containerd/containerd.sock\n' > /etc/crictl.yaml
systemctl enable --now containerd >/dev/null 2>&1
kubeadm config images pull --kubernetes-version="$VER" >/dev/null
[ "$ROLE" != cp ] || install_etcd_tools
mkdir -p /var/lib/k8squest
touch "$MARK"
