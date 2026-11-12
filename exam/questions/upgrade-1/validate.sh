#!/bin/bash
# kubeadm task: runs on k8s-lab as david and reaches controlplane through the root helper.

fail() { echo "❌ $1"; exit 1; }

OUT=$(sudo -n /usr/local/sbin/cka-kubeadm run-on --timeout 60 controlplane 2>&1 <<'EOS'
bad() { echo "FAIL: $1"; exit 3; }
KV=$(kubeadm version -o short 2>/dev/null)
case "$KV" in v1.37.[0-9]|v1.37.[0-9][0-9]) ;; *) bad "kubeadm on controlplane is '$KV', not a 1.37 release" ;; esac
KP=${KV#v}
held() { apt-mark showhold | grep -Fxq "$1"; }
DV=$(dpkg-query -W -f='${Version}' kubeadm)
[ "${DV%%-*}" = "$KP" ] || bad "the installed kubeadm package is $DV but the binary reports $KV"
LATEST=$(apt-cache madison kubeadm | awk '$3 ~ /^1\.37\./ {print $3}' | sort -V | tail -n 1)
[ -n "$LATEST" ] || { echo "FAIL: internal: no 1.37 kubeadm package listed"; exit 4; }
[ "$DV" = "$LATEST" ] || bad "kubeadm is $DV, the latest 1.37 patch release in the repository is $LATEST"
held kubeadm || bad "the kubeadm package is not on hold any more (apt-mark hold kubeadm)"
echo "kubeadm $KV"
EOS
)
RC=$?
case $RC in
  0) ;;
  3) fail "$(printf '%s\n' "$OUT" | sed -n 's/^FAIL: //p' | head -n 1)" ;;
  *) fail "could not check controlplane (exit $RC): $(echo "$OUT" | tail -n 3)" ;;
esac
echo "✅ the kubeadm package is upgraded to 1.37 and held"
exit 0
