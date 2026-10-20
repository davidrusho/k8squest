#!/bin/bash
# Added 2026 by David Rusho; see CHANGES.md
# Scripted proof of the fix (used by tests/level_harness.py; the engine never runs it).
# The player does this by hand on the two machines (see solution.yaml). Steps follow
# https://kubernetes.io/docs/tasks/administer-cluster/kubeadm/kubeadm-upgrade/ in order.
. ../_shared/lib.sh
set -e
PKG="${K8S_NEW_PKG%-*}-*"
# the repository, on both machines
for vm in "$CP_VM" "$WK_VM"; do
    vm_sh "$vm" "sed -i 's|stable:/$K8S_OLD_MINOR/|stable:/$K8S_NEW_MINOR/|' /etc/apt/sources.list.d/kubernetes.list && apt-get update -qq >/dev/null 2>&1"
done
# control plane: kubeadm, plan, apply, drain, kubelet and kubectl, restart, uncordon
vm_sh "$CP_VM" "apt-mark unhold kubeadm >/dev/null && apt-get install -y -qq kubeadm='$PKG' >/dev/null 2>&1 && apt-mark hold kubeadm >/dev/null"
vm_sh "$CP_VM" "kubeadm version -o short && kubeadm upgrade plan >/dev/null"
vm_sh "$CP_VM" "kubeadm upgrade apply $K8S_NEW -y >/tmp/upgrade-apply.log 2>&1 || { tail -20 /tmp/upgrade-apply.log; exit 1; }"
wait_admin
kc drain "$CP_NODE" --ignore-daemonsets >/dev/null
vm_sh "$CP_VM" "apt-mark unhold kubelet kubectl >/dev/null && apt-get install -y -qq kubelet='$PKG' kubectl='$PKG' >/dev/null 2>&1 && apt-mark hold kubelet kubectl >/dev/null && systemctl daemon-reload && systemctl restart kubelet"
wait_admin   # the kubelet upgrade restarts the control-plane static pods
kc uncordon "$CP_NODE" >/dev/null
# worker: kubeadm and kubectl, upgrade node, drain from the control plane, kubelet, restart, uncordon
vm_sh "$WK_VM" "apt-mark unhold kubeadm kubectl >/dev/null && apt-get install -y -qq kubeadm='$PKG' kubectl='$PKG' >/dev/null 2>&1 && apt-mark hold kubeadm kubectl >/dev/null"
vm_sh "$WK_VM" "kubeadm upgrade node >/tmp/upgrade-node.log 2>&1 || { tail -20 /tmp/upgrade-node.log; exit 1; }"
kc drain "$WK_NODE" --ignore-daemonsets >/dev/null
vm_sh "$WK_VM" "apt-mark unhold kubelet >/dev/null && apt-get install -y -qq kubelet='$PKG' >/dev/null 2>&1 && apt-mark hold kubelet >/dev/null && systemctl daemon-reload && systemctl restart kubelet"
kc uncordon "$WK_NODE" >/dev/null
