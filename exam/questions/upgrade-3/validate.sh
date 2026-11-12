#!/bin/bash
# kubeadm task: runs on k8s-lab as david and reaches controlplane through the root helper.

fail() { echo "❌ $1"; exit 1; }

OUT=$(sudo -n /usr/local/sbin/cka-kubeadm run-on --timeout 150 controlplane 2>&1 <<'EOS'
bad() { echo "FAIL: $1"; exit 3; }
KC="kubectl --kubeconfig /etc/kubernetes/admin.conf --request-timeout=5s"
KV=$(kubeadm version -o short 2>/dev/null)
case "$KV" in v1.37.[0-9]|v1.37.[0-9][0-9]) ;; *) bad "kubeadm on controlplane is '$KV', not a 1.37 release" ;; esac
end=$((SECONDS + 110))
msg=
while [ "$SECONDS" -lt "$end" ]; do
  msg=
  for c in kube-apiserver kube-controller-manager kube-scheduler; do
    img=$($KC -n kube-system get pod "$c-controlplane" -o jsonpath='{.spec.containers[0].image}' 2>/dev/null)
    rdy=$($KC -n kube-system get pod "$c-controlplane" -o jsonpath='{.status.containerStatuses[0].ready}' 2>/dev/null)
    case "$img" in *:v1.37.[0-9]|*:v1.37.[0-9][0-9]) ;; *) msg="$c still runs '$img'"; break ;; esac
    [ "$rdy" = true ] || { msg="$c is not ready"; break; }
  done
  [ -z "$msg" ] && break
  sleep 5
done
[ -z "$msg" ] || bad "the control plane is not upgraded: $msg"
CC=$($KC -n kube-system get configmap kubeadm-config -o jsonpath='{.data.ClusterConfiguration}' 2>/dev/null)
printf '%s\n' "$CC" | grep -Eq '^kubernetesVersion: v1\.37\.[0-9]+' || bad "kubernetesVersion in the kubeadm-config ConfigMap is not 1.37.x"
echo ok
EOS
)
RC=$?
case $RC in
  0) ;;
  3) fail "$(printf '%s\n' "$OUT" | sed -n 's/^FAIL: //p' | head -n 1)" ;;
  *) fail "could not check controlplane (exit $RC): $(echo "$OUT" | tail -n 3)" ;;
esac
echo "✅ the first control plane node is upgraded to Kubernetes 1.37"
exit 0
