#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Runs as root inside a World 8 node. Takes the machine back to "kubeadm packages installed,
# no cluster": kubeadm reset, then the cleanup kubeadm reset documents as NOT done
# (CNI configuration, network traffic rules) plus leftovers of the pod network.
# Does not touch the node preparation (swap, modules, sysctl, containerd configuration).
# https://kubernetes.io/docs/reference/setup-tools/kubeadm/kubeadm-reset/
set -u
kubeadm reset -f >/dev/null 2>&1
systemctl stop kubelet 2>/dev/null
rm -rf /etc/cni/net.d /var/lib/cni /var/lib/etcd /var/lib/etcd-restored /var/backups/etcd /var/lib/k8squest/level-* /root/.kube /home/*/.kube
for link in flannel.1 cni0 flannel-v6.1; do ip link delete "$link" 2>/dev/null; done
for t in iptables ip6tables; do
    for table in filter nat mangle raw; do
        "$t" -t "$table" -F 2>/dev/null
        "$t" -t "$table" -X 2>/dev/null
    done
done
systemctl reset-failed containerd 2>/dev/null
systemctl restart containerd 2>/dev/null
exit 0
