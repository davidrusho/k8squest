#!/bin/bash
# kubeadm task: runs on k8s-lab as david and reaches controlplane through the root helper.
# The expected values are read from the etcd manifest at check time, never hardcoded.

fail() { echo "❌ $1"; exit 1; }

OUT=$(sudo -n /usr/local/sbin/cka-kubeadm run-on --timeout 60 controlplane 2>&1 <<'EOS'
bad() { echo "FAIL: $1"; exit 3; }
f=/opt/course/kubeadm/etcd-flags.txt
M=/etc/kubernetes/manifests/etcd.yaml
[ -f "$f" ] && [ ! -L "$f" ] || bad "$f does not exist on controlplane (or is a symbolic link)"
[ "$(stat -c %s "$f")" -le 65536 ] || bad "$f is larger than 64 KiB"
[ -s "$f" ] || bad "$f is empty"
NORM=$(sed -E 's/^[[:space:]]*(- )?//; s/[[:space:]]+$//' "$f")
for flag in cert-file key-file trusted-ca-file data-dir; do
  want=$(sed -En "s/^[[:space:]]*- (--$flag=.*)\$/\1/p" "$M")
  [ "$(printf '%s\n' "$want" | grep -c .)" = 1 ] || { echo "FAIL: internal: $M does not hold exactly one --$flag line"; exit 4; }
  printf '%s\n' "$NORM" | grep -Fxq -- "$want" || bad "the answer file has no line $want"
done
echo "all four settings present"
EOS
)
RC=$?
case $RC in
  0) ;;
  3) fail "$(printf '%s\n' "$OUT" | sed -n 's/^FAIL: //p' | head -n 1)" ;;
  *) fail "could not check controlplane (exit $RC): $(echo "$OUT" | tail -n 3)" ;;
esac
echo "✅ the etcd certificate, key, CA and data directory settings are in /opt/course/kubeadm/etcd-flags.txt"
exit 0
