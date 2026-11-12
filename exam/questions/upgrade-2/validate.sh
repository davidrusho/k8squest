#!/bin/bash
# kubeadm task: runs on k8s-lab as david and reaches controlplane through the root helper.
fail() { echo "❌ $1"; exit 1; }

OUT=$(sudo -n /usr/local/sbin/cka-kubeadm run-on --timeout 60 controlplane 2>&1 <<'EOS'
bad() { echo "FAIL: $1"; exit 3; }
f=/opt/course/kubeadm/upgrade-plan.txt
[ -f "$f" ] && [ ! -L "$f" ] || bad "$f does not exist on controlplane (or is a symbolic link)"
[ "$(stat -c %s "$f")" -le 262144 ] || bad "$f is larger than 256 KiB"
[ -s "$f" ] || bad "$f is empty"
KV=$(kubeadm version -o short 2>/dev/null)
case "$KV" in v1.37.[0-9]|v1.37.[0-9][0-9]) ;; *) bad "kubeadm on controlplane is '$KV', not a 1.37 release" ;; esac
# the plan names its target from the release server (stable.txt), not from the kubeadm binary: accept any 1.37.x
grep -Eq 'kubeadm upgrade apply v1\.37\.[0-9]+' "$f" || bad "the file does not offer a 'kubeadm upgrade apply v1.37.x' command (write the output of kubeadm upgrade plan, stdout and stderr)"
grep -q 'COMPONENT' "$f" || bad "the file has no component version table of kubeadm upgrade plan"
echo ok
EOS
)
RC=$?
case $RC in
  0) ;;
  3) fail "$(printf '%s\n' "$OUT" | sed -n 's/^FAIL: //p' | head -n 1)" ;;
  *) fail "could not check controlplane (exit $RC): $(echo "$OUT" | tail -n 3)" ;;
esac
echo "✅ /opt/course/kubeadm/upgrade-plan.txt holds the output of kubeadm upgrade plan"
exit 0
