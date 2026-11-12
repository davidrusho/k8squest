#!/bin/bash
# kubeadm task: runs on k8s-lab as david. cka1's kubectl configuration and answer file are read as cka1 (the user's own
# files, so a symbolic link cannot lead anywhere cka1 could not already read); the token comes from the cluster.

fail() { echo "❌ $1"; exit 1; }

CTX=$(sudo -n -H -u cka1 env -u KUBECONFIG kubectl config current-context 2>/dev/null) || fail "could not read cka1's kubectl configuration"
[ "$CTX" = cluster1 ] || fail "the current context of cka1 is '$CTX', not cluster1"

TOUT=$(sudo -n /usr/local/sbin/cka-kubeadm run-on --timeout 60 controlplane 2>&1 <<'EOS'
bad() { echo "FAIL: $1"; exit 3; }
KC="kubectl --kubeconfig /etc/kubernetes/admin.conf --request-timeout=5s"
T=$($KC -n default get configmap ctx-marker -o jsonpath='{.data.token}' 2>/dev/null)
[ -n "$T" ] || { echo "FAIL: internal: ConfigMap ctx-marker is missing"; exit 4; }
echo "TOKEN=$T"
EOS
)
RC=$?
case $RC in
  0) ;;
  3) fail "$(printf '%s\n' "$TOUT" | sed -n 's/^FAIL: //p' | head -n 1)" ;;
  *) fail "could not check controlplane (exit $RC): $(echo "$TOUT" | tail -n 3)" ;;
esac
TOKEN=$(printf '%s\n' "$TOUT" | sed -n 's/^TOKEN=//p' | head -n 1)
[ -n "$TOKEN" ] || fail "could not read the marker token from the cluster"

H=$(getent passwd cka1 | cut -d: -f6)
F="$H/cluster1-confirm.txt"
sudo -n -H -u cka1 test -f "$F" -a ! -L "$F" || fail "$F does not exist (or is a symbolic link)"
ANS=$(sudo -n -H -u cka1 head -c 4096 -- "$F") || fail "could not read $F"
L1=$(printf '%s\n' "$ANS" | sed 's/[[:space:]]*$//' | grep . | sed -n 1p)
L2=$(printf '%s\n' "$ANS" | sed 's/[[:space:]]*$//' | grep . | sed -n 2p)
[ "$L1" = cluster1 ] || fail "the first line of ~/cluster1-confirm.txt must be the current context, cluster1 (it is '$L1')"
[ "$L2" = "$TOKEN" ] || fail "the second line of ~/cluster1-confirm.txt must be the token of ConfigMap ctx-marker read from cluster1"
# the check passed: put cka1 back on a context other than cluster1 and remove the answer, so that the kind tasks that follow on cka1 are not sent to the kubeadm cluster
sudo -n -H -u cka1 env -u KUBECONFIG bash -c 'o=$(kubectl config get-contexts -o name | grep -vx cluster1 | head -n 1); [ -n "$o" ] && kubectl config use-context "$o" > /dev/null; rm -f "$HOME/cluster1-confirm.txt"'
echo "✅ cka1 works in context cluster1 and ~/cluster1-confirm.txt confirms it (the context was switched back for you)"
exit 0
