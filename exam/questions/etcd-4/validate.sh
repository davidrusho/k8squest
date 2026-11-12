#!/bin/bash
# kubeadm task: runs on k8s-lab as david and reaches controlplane through the root helper.
# The expected hash, revision and key count are read from the snapshot itself at check time.

fail() { echo "❌ $1"; exit 1; }

OUT=$(sudo -n /usr/local/sbin/cka-kubeadm run-on --timeout 60 controlplane 2>&1 <<'EOS'
bad() { echo "FAIL: $1"; exit 3; }
f=/opt/course/kubeadm/snapshot-status.txt
s=/opt/backup.db
[ -f "$f" ] && [ ! -L "$f" ] || bad "$f does not exist on controlplane (or is a symbolic link)"
[ "$(stat -c %s "$f")" -le 65536 ] || bad "$f is larger than 64 KiB"
[ -s "$f" ] || bad "$f is empty"
command -v etcdutl >/dev/null || { echo "FAIL: internal: etcdutl is missing"; exit 4; }
J=$(etcdutl snapshot status "$s" -w json) || { echo "FAIL: internal: etcdutl cannot read $s"; exit 4; }
HASH=$(printf '%s' "$J" | sed -n 's/.*"hash": *\([0-9][0-9]*\).*/\1/p')
REV=$(printf '%s' "$J" | sed -n 's/.*"revision": *\([0-9][0-9]*\).*/\1/p')
TK=$(printf '%s' "$J" | sed -n 's/.*"totalKey": *\([0-9][0-9]*\).*/\1/p')
[ -n "$HASH" ] && [ -n "$REV" ] && [ -n "$TK" ] || { echo "FAIL: internal: could not read the snapshot status"; exit 4; }
HX=$(printf '%x' "$HASH")
grep -Eq '^\+-' "$f" || bad "the answer is not a table (use --write-out=table)"
grep -Eq '^\|[[:space:]]*HASH[[:space:]]*\|' "$f" || bad "the table has no HASH header"
ROW=$(grep -E "\|[[:space:]]*0*$HX[[:space:]]*\|" "$f" | head -n 1)
[ -n "$ROW" ] || bad "the table does not show this snapshot's hash"
printf '%s\n' "$ROW" | grep -Eq "\|[[:space:]]*$REV[[:space:]]*\|" || bad "the table row does not show revision $REV"
printf '%s\n' "$ROW" | grep -Eq "\|[[:space:]]*$TK[[:space:]]*\|" || bad "the table row does not show $TK total keys"
echo ok
EOS
)
RC=$?
case $RC in
  0) ;;
  3) fail "$(printf '%s\n' "$OUT" | sed -n 's/^FAIL: //p' | head -n 1)" ;;
  *) fail "could not check controlplane (exit $RC): $(echo "$OUT" | tail -n 3)" ;;
esac
echo "✅ /opt/course/kubeadm/snapshot-status.txt is the table status of /opt/backup.db"
exit 0
