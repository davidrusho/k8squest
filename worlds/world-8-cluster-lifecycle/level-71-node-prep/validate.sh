#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
validate_vms
fail() { echo "❌ $1"; [ -n "${2:-}" ] && echo "💡 $2"; exit 1; }

echo "🔍 Stage 1: Is swap off, now and after a reboot?"
[ -z "$(vm_sh "$CP_VM" 'swapon --noheadings')" ] || fail "Swap is still on" "swapon --show ; sudo swapoff -a"
[ -z "$(vm_sh "$CP_VM" "grep -E '^[^#].*[[:space:]]swap[[:space:]]' /etc/fstab")" ] \
    || fail "Swap is off now, but /etc/fstab would turn it on again at boot" "comment out the swap line in /etc/fstab"
echo "✅ Swap is off and stays off"

echo ""
echo "🔍 Stage 2: Are overlay and br_netfilter loaded, and loaded again at boot?"
MODS=$(vm_sh "$CP_VM" "lsmod | awk '{print \$1}'")
for m in overlay br_netfilter; do
    echo "$MODS" | grep -qx "$m" || fail "The kernel module $m is not loaded" "sudo modprobe $m"
    [ -n "$(vm_sh "$CP_VM" "grep -rlsx '$m' /etc/modules-load.d/")" ] \
        || fail "$m is loaded now, but nothing loads it at boot" "list it in a file in /etc/modules-load.d/"
done
echo "✅ Both modules are loaded and configured to load at boot"

echo ""
echo "🔍 Stage 3: Is IPv4 forwarding on, and configured to stay on?"
[ "$(vm_sh "$CP_VM" 'sysctl -n net.ipv4.ip_forward')" = 1 ] || fail "net.ipv4.ip_forward is 0" "sysctl net.ipv4.ip_forward"
[ -n "$(vm_sh "$CP_VM" "grep -rEs '^[[:space:]]*net\.ipv4\.ip_forward[[:space:]]*=[[:space:]]*1' /etc/sysctl.d/ /etc/sysctl.conf")" ] \
    || fail "Forwarding is on now, but no sysctl file sets it at boot" "a file in /etc/sysctl.d/, then sudo sysctl --system"
echo "✅ net.ipv4.ip_forward = 1, now and after a reboot"

echo ""
echo "🔍 Stage 4: Is containerd running with the systemd cgroup driver?"
[ "$(vm_sh "$CP_VM" 'systemctl is-active containerd')" = active ] || fail "containerd is not running" "sudo systemctl restart containerd"
vm_sh "$CP_VM" 'test -s /etc/containerd/config.toml' || fail "There is no /etc/containerd/config.toml" "containerd config default"
vm_sh "$CP_VM" "grep -Eq '^[[:space:]]*SystemdCgroup[[:space:]]*=[[:space:]]*true' /etc/containerd/config.toml" \
    || fail "SystemdCgroup is not true in /etc/containerd/config.toml" "set it under the runc options, then restart containerd"
vm_sh "$CP_VM" "containerd config dump | grep -Eq '^[[:space:]]*SystemdCgroup[[:space:]]*=[[:space:]]*true'" \
    || fail "containerd is running without SystemdCgroup = true" "sudo systemctl restart containerd"
echo "✅ containerd runs with SystemdCgroup = true"

echo ""
echo "🔍 Stage 5: Does kubeadm's own pre-flight check pass?"
PF=$(vm_sh "$CP_VM" "printf 'apiVersion: kubeadm.k8s.io/v1beta4\nkind: ClusterConfiguration\nkubernetesVersion: $K8S_NEW\n' > /tmp/k8squest-preflight.yaml; kubeadm init phase preflight --config /tmp/k8squest-preflight.yaml 2>&1; echo \"rc=\$?\"")
if ! echo "$PF" | grep -qx 'rc=0'; then
    echo "$PF" | grep 'ERROR' | head -5
    fail "kubeadm init would stop at its pre-flight checks" "sudo kubeadm init phase preflight"
fi
echo "✅ kubeadm's pre-flight checks pass"

echo ""
echo "🎉 SUCCESS! k8squest-cp is ready for kubeadm init."
exit 0
