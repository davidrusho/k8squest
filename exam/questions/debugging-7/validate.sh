#!/bin/bash
# kubeadm task: runs on k8s-lab as david and reaches node01 and controlplane through the root helper.
# node01 must be Ready, the kubelet enabled and running, and its unit must use the original --config path (a symlink or a copy does not count).
fail() { echo "❌ $1"; exit 1; }

OUT=$(sudo -n /usr/local/sbin/cka-kubeadm run-on --timeout 60 node01 2>&1 <<'EOS'
bad() { echo "FAIL: $1"; exit 3; }
systemctl is-enabled --quiet kubelet || bad "the kubelet is not enabled on node01"
systemctl is-active --quiet kubelet || bad "the kubelet is not running on node01"
[ "$(systemctl show kubelet -p NeedDaemonReload --value)" = no ] || bad "systemd has not reloaded the kubelet unit (systemctl daemon-reload)"
CAT=$(systemctl cat kubelet)
printf '%s\n' "$CAT" | grep -Fq -- '--config=/var/lib/kubelet/config.yaml' || bad "the kubelet unit does not use --config=/var/lib/kubelet/config.yaml"
if printf '%s\n' "$CAT" | grep -Fq 'config.yml'; then bad "the kubelet unit still names config.yml"; fi
[ -f /var/lib/kubelet/config.yaml ] && [ ! -L /var/lib/kubelet/config.yaml ] || bad "/var/lib/kubelet/config.yaml is not a regular file"
echo ok
EOS
)
RC=$?
case $RC in
  0) ;;
  3) fail "$(printf '%s\n' "$OUT" | sed -n 's/^FAIL: //p' | head -n 1)" ;;
  *) fail "could not check node01 (exit $RC): $(echo "$OUT" | tail -n 3)" ;;
esac

OUT2=$(sudo -n /usr/local/sbin/cka-kubeadm run-on --timeout 100 controlplane 2>&1 <<'EOS'
bad() { echo "FAIL: $1"; exit 3; }
KC="kubectl --kubeconfig /etc/kubernetes/admin.conf --request-timeout=5s"
end=$((SECONDS + 80))
s=
while [ "$SECONDS" -lt "$end" ]; do
  s=$($KC get node node01 -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
  [ "$s" = True ] && break
  sleep 5
done
[ "$s" = True ] || bad "node01 is not Ready yet (status '$s'); wait a little after the kubelet runs"
echo ok
EOS
)
RC=$?
case $RC in
  0) ;;
  3) fail "$(printf '%s\n' "$OUT2" | sed -n 's/^FAIL: //p' | head -n 1)" ;;
  *) fail "could not check controlplane (exit $RC): $(echo "$OUT2" | tail -n 3)" ;;
esac
echo "✅ node01 is Ready again and its kubelet is configured as before"
exit 0
