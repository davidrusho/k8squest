#!/bin/bash
# kubeadm task: runs on k8s-lab as david and reaches both nodes through the root helper.
# `kubeadm upgrade node` on a worker rewrites the kubelet configuration; setup left a marker file on node01 to compare with.

fail() { echo "❌ $1"; exit 1; }

OUT=$(sudo -n /usr/local/sbin/cka-kubeadm run-on --timeout 60 node01 2>&1 <<'EOS'
bad() { echo "FAIL: $1"; exit 3; }
m=/var/lib/kubeadm-drill-upgrade-marker
[ -f "$m" ] || { echo "FAIL: internal: setup marker $m is missing"; exit 4; }
new=
for f in /var/lib/kubelet/config.yaml /var/lib/kubelet/kubeadm-flags.env; do
  [ -f "$f" ] && [ "$f" -nt "$m" ] && new=1
done
[ -n "$new" ] || bad "kubeadm upgrade node has not run on node01 (the kubelet configuration is unchanged)"
echo ok
EOS
)
RC=$?
case $RC in
  0) ;;
  3) fail "$(printf '%s\n' "$OUT" | sed -n 's/^FAIL: //p' | head -n 1)" ;;
  *) fail "could not check node01 (exit $RC): $(echo "$OUT" | tail -n 3)" ;;
esac

OUT=$(sudo -n /usr/local/sbin/cka-kubeadm run-on --timeout 60 controlplane 2>&1 <<'EOS'
bad() { echo "FAIL: $1"; exit 3; }
KC="kubectl --kubeconfig /etc/kubernetes/admin.conf --request-timeout=5s"
[ "$($KC get node node01 -o jsonpath='{.spec.unschedulable}')" != true ] || bad "node01 is still unschedulable (kubectl uncordon node01)"
[ "$($KC get node node01 -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')" = True ] || bad "node01 is not Ready"
echo ok
EOS
)
RC=$?
case $RC in
  0) ;;
  3) fail "$(printf '%s\n' "$OUT" | sed -n 's/^FAIL: //p' | head -n 1)" ;;
  *) fail "could not check controlplane (exit $RC): $(echo "$OUT" | tail -n 3)" ;;
esac
echo "✅ node01's kubeadm-managed configuration is upgraded and the node is schedulable"
exit 0
