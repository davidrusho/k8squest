#!/bin/bash
# kubeadm task: runs on k8s-lab as david and reaches controlplane through the root helper.
# The API must answer, its Pod must be Running and the manifest must be back to the original etcd endpoint.
fail() { echo "❌ $1"; exit 1; }

OUT=$(sudo -n /usr/local/sbin/cka-kubeadm run-on --timeout 150 controlplane 2>&1 <<'EOS'
bad() { echo "FAIL: $1"; exit 3; }
KC="kubectl --kubeconfig /etc/kubernetes/admin.conf --request-timeout=5s"
M=/etc/kubernetes/manifests/kube-apiserver.yaml
[ -f "$M" ] || bad "$M is missing"
grep -Fq '2370' "$M" && bad "$M still names the wrong etcd port 2370"
[ "$(grep -c -- '--etcd-servers=' "$M")" = 1 ] || bad "$M must hold exactly one --etcd-servers flag"
grep -Fxq -- '    - --etcd-servers=https://127.0.0.1:2379' "$M" || bad "--etcd-servers in $M is not https://127.0.0.1:2379"
end=$((SECONDS + 110))
up=
while [ "$SECONDS" -lt "$end" ]; do
  if $KC get --raw /readyz --request-timeout=5s > /dev/null 2>&1; then up=1; break; fi
  sleep 5
done
[ -n "$up" ] || bad "the API server does not answer"
POD=$($KC -n kube-system get pod kube-apiserver-controlplane -o jsonpath='{.status.phase}/{.status.containerStatuses[0].ready}' 2>/dev/null)
[ "$POD" = "Running/true" ] || bad "the kube-apiserver Pod is not Running and ready (it is '$POD')"
echo ok
EOS
)
RC=$?
case $RC in
  0) ;;
  3) fail "$(printf '%s\n' "$OUT" | sed -n 's/^FAIL: //p' | head -n 1)" ;;
  *) fail "could not check controlplane (exit $RC): $(echo "$OUT" | tail -n 3)" ;;
esac
echo "✅ the API server is back: it answers and its static Pod is Running with the original etcd endpoint"
exit 0
