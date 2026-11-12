#!/bin/bash
# kubeadm task: runs on k8s-lab as david and reaches controlplane through the root helper.

fail() { echo "❌ $1"; exit 1; }

OUT=$(sudo -n /usr/local/sbin/cka-kubeadm run-on --timeout 150 controlplane 2>&1 <<'EOS'
bad() { echo "FAIL: $1"; exit 3; }
KC="kubectl --kubeconfig /etc/kubernetes/admin.conf --request-timeout=5s"
KV=$(kubeadm version -o short 2>/dev/null)
case "$KV" in v1.37.[0-9]|v1.37.[0-9][0-9]) ;; *) bad "kubeadm on controlplane is '$KV', not a 1.37 release" ;; esac
KP=${KV#v}
held() { apt-mark showhold | grep -Fxq "$1"; }
for p in kubelet kubectl; do
  v=$(dpkg-query -W -f='${Version}' "$p" 2>/dev/null)
  [ "${v%%-*}" = "$KP" ] || bad "package $p is '$v', not the kubeadm version $KP"
  held "$p" || bad "package $p is not on hold (apt-mark hold)"
done
systemctl is-active --quiet kubelet || bad "the kubelet is not running"
end=$((SECONDS + 100))
kv=
while [ "$SECONDS" -lt "$end" ]; do
  kv=$($KC get node controlplane -o jsonpath='{.status.nodeInfo.kubeletVersion}' 2>/dev/null)
  [ "$kv" = "$KV" ] && break
  sleep 5
done
[ "$kv" = "$KV" ] || bad "node controlplane reports kubelet '$kv', not $KV (restart the kubelet)"
[ "$($KC get node controlplane -o jsonpath='{.spec.unschedulable}')" = true ] || bad "node controlplane was uncordoned: leave it cordoned"
[ "$($KC get node controlplane -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')" = True ] || bad "node controlplane is not Ready"
echo ok
EOS
)
RC=$?
case $RC in
  0) ;;
  3) fail "$(printf '%s\n' "$OUT" | sed -n 's/^FAIL: //p' | head -n 1)" ;;
  *) fail "could not check controlplane (exit $RC): $(echo "$OUT" | tail -n 3)" ;;
esac
echo "✅ kubelet and kubectl on controlplane are upgraded and the node reports the new version"
exit 0
