#!/bin/bash
# kubeadm task: runs on k8s-lab as david and reaches controlplane through the root helper.
# A restore keeps the snapshot's revision and key count; a copy of the live data directory does not (setup changes the
# live etcd after the snapshot).

fail() { echo "❌ $1"; exit 1; }

OUT=$(sudo -n /usr/local/sbin/cka-kubeadm run-on --timeout 60 controlplane 2>&1 <<'EOS'
bad() { echo "FAIL: $1"; exit 3; }
d=/var/lib/etcd-restore
s=/opt/backup.db
[ -d "$d" ] && [ ! -L "$d" ] || bad "$d does not exist on controlplane"
[ -f "$d/member/snap/db" ] || bad "$d holds no member/snap/db: not a restored etcd data directory"
[ -d "$d/member/wal" ] || bad "$d holds no member/wal: not a restored etcd data directory"
command -v etcdutl >/dev/null || { echo "FAIL: internal: etcdutl is missing"; exit 4; }
[ -f "$s" ] || { echo "FAIL: internal: $s is missing"; exit 4; }
field() { sed -n "s/.*\"$1\": *\([0-9][0-9]*\).*/\1/p"; }
SJ=$(etcdutl snapshot status "$s" -w json) || { echo "FAIL: internal: cannot read $s"; exit 4; }
DJ=$(etcdutl snapshot status "$d/member/snap/db" -w json) || bad "etcdutl cannot read $d/member/snap/db"
SR=$(printf '%s' "$SJ" | field revision); DR=$(printf '%s' "$DJ" | field revision)
ST=$(printf '%s' "$SJ" | field totalKey); DT=$(printf '%s' "$DJ" | field totalKey)
[ -n "$SR" ] && [ -n "$DR" ] && [ -n "$ST" ] && [ -n "$DT" ] || { echo "FAIL: internal: could not read the status values"; exit 4; }
[ "$SR" = "$DR" ] || bad "$d does not hold the snapshot's data (revision $DR, the snapshot has $SR)"
[ "$ST" = "$DT" ] || bad "$d does not hold the snapshot's data ($DT keys, the snapshot has $ST)"
echo "revision $DR, $DT keys"
EOS
)
RC=$?
case $RC in
  0) ;;
  3) fail "$(printf '%s\n' "$OUT" | sed -n 's/^FAIL: //p' | head -n 1)" ;;
  *) fail "could not check controlplane (exit $RC): $(echo "$OUT" | tail -n 3)" ;;
esac
echo "✅ /var/lib/etcd-restore holds the restored snapshot ($(printf '%s\n' "$OUT" | tail -n 1))"
exit 0
