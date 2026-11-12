#!/bin/bash
# kubeadm task: runs on k8s-lab as david and reaches controlplane through the root helper.

fail() { echo "❌ $1"; exit 1; }

OUT=$(sudo -n /usr/local/sbin/cka-kubeadm run-on --timeout 150 controlplane 2>&1 <<'EOS'
f=/opt/backup.db
[ -f "$f" ] && [ ! -L "$f" ] || { echo "RC3"; exit 3; }
[ -s "$f" ] || { echo "RC4"; exit 4; }
# a real `etcdctl snapshot save` file has a sha256 appended (etcd 3.6 hasChecksum), so its size is 32 bytes past a
# multiple of 512; a copied member db is a multiple of 512 and is not a snapshot save file
SZ=$(stat -c %s "$f")
[ $((SZ % 512)) -eq 32 ] || { echo "RC8"; exit 8; }
command -v etcdutl >/dev/null || { echo "RC6"; exit 6; }
TK=$(etcdutl snapshot status "$f" -w json | sed -n 's/.*"totalKey": *\([0-9][0-9]*\).*/\1/p')
[ -n "$TK" ] || { echo "RC5"; exit 5; }
[ "$TK" -gt 0 ] || { echo "RC7"; exit 7; }
echo "TOTALKEY=$TK"
EOS
)
RC=$?
case $RC in
  0) ;;
  3) fail "/opt/backup.db does not exist on controlplane" ;;
  4) fail "/opt/backup.db on controlplane is empty" ;;
  5) fail "/opt/backup.db is not a valid etcd snapshot (etcdutl snapshot status failed)" ;;
  6) fail "etcdutl is not installed on controlplane" ;;
  8) fail "/opt/backup.db is not an etcdctl snapshot save file (take it with etcdctl snapshot save, do not copy the member db)" ;;
  7) fail "the snapshot /opt/backup.db holds no keys" ;;
  *) fail "could not check controlplane (exit $RC): $(echo "$OUT" | tail -n 3)" ;;
esac
TK=$(echo "$OUT" | sed -n 's/^TOTALKEY=\([0-9][0-9]*\)$/\1/p' | tail -n 1)
[ -n "$TK" ] && [ "$TK" -gt 0 ] || fail "could not read a positive key count from the snapshot status"
echo "✅ /opt/backup.db on controlplane is a valid etcd snapshot ($TK keys)"
exit 0
