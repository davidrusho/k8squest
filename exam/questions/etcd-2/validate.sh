#!/bin/bash
# kubeadm task: runs on k8s-lab as david and reaches controlplane through the root helper.

fail() { echo "❌ $1"; exit 1; }

OUT=$(sudo -n /usr/local/sbin/cka-kubeadm run-on --timeout 60 controlplane 2>&1 <<'EOS'
bad() { echo "FAIL: $1"; exit 3; }
f=/opt/course/kubeadm/etcd-datadir.txt
M=/etc/kubernetes/manifests/etcd.yaml
[ -f "$f" ] && [ ! -L "$f" ] || bad "$f does not exist on controlplane (or is a symbolic link)"
[ "$(stat -c %s "$f")" -le 65536 ] || bad "$f is larger than 64 KiB"
want=$(sed -En 's/^[[:space:]]*- (--data-dir=.*)$/\1/p' "$M")
[ "$(printf '%s\n' "$want" | grep -c .)" = 1 ] || { echo "FAIL: internal: $M does not hold exactly one --data-dir line"; exit 4; }
NORM=$(sed -E 's/^[[:space:]]*(- )?//; s/[[:space:]]+$//' "$f" | grep .)
[ -n "$NORM" ] || bad "$f is empty"
printf '%s\n' "$NORM" | grep -Fxq -- "$want" || bad "the answer file does not hold the line $want"
[ "$(printf '%s\n' "$NORM" | grep -c .)" = 1 ] || bad "the answer file must hold that line only"
echo ok
EOS
)
RC=$?
case $RC in
  0) ;;
  3) fail "$(printf '%s\n' "$OUT" | sed -n 's/^FAIL: //p' | head -n 1)" ;;
  *) fail "could not check controlplane (exit $RC): $(echo "$OUT" | tail -n 3)" ;;
esac
echo "✅ /opt/course/kubeadm/etcd-datadir.txt holds the etcd data directory line"
exit 0
