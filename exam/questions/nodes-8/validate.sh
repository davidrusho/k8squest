#!/bin/bash
# kubeadm task: runs on k8s-lab as david and reaches controlplane through the root helper.
# End state: node01 schedulable and Ready, Deployment drain-web Running on node01 with Pods that are not the ones setup recorded but
# still belong to the ReplicaSet recorded at setup (no rollout restart). KNOWN LIMITATION: kubectl cordon leaves no durable trace
# (no event, no managedFields entry after uncordon), so deleting the Pods by hand is indistinguishable from drain + uncordon and passes.
fail() { echo "❌ $1"; exit 1; }

OUT=$(sudo -n /usr/local/sbin/cka-kubeadm run-on --timeout 150 controlplane 2>&1 <<'EOS'
bad() { echo "FAIL: $1"; exit 3; }
KC="kubectl --kubeconfig /etc/kubernetes/admin.conf --request-timeout=5s"
[ "$($KC get node node01 -o jsonpath='{.spec.unschedulable}')" != true ] || bad "node01 is still unschedulable (kubectl uncordon node01)"
[ "$($KC get node node01 -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')" = True ] || bad "node01 is not Ready"
BASE=$($KC -n default get configmap drain-baseline -o jsonpath='{.data.uids}' 2>/dev/null)
[ -n "$BASE" ] || { echo "FAIL: internal: ConfigMap drain-baseline is missing"; exit 4; }
end=$((SECONDS + 100))
ready=
while [ "$SECONDS" -lt "$end" ]; do
  ready=$($KC -n default get deployment drain-web -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
  [ "$ready" = 2 ] && break
  sleep 5
done
[ "$ready" = 2 ] || bad "Deployment drain-web has $ready of 2 Pods ready"
PODS=$($KC -n default get pods -l app=drain-web --no-headers -o custom-columns=NODE:.spec.nodeName,UID:.metadata.uid,DEL:.metadata.deletionTimestamp | awk '$3 == "<none>"')
[ "$(printf '%s\n' "$PODS" | grep -c .)" = 2 ] || bad "Deployment drain-web does not have exactly 2 Pods"
printf '%s\n' "$PODS" | awk '$1 != "node01" {x=1} END {exit x}' || bad "a drain-web Pod is not on node01"
for u in $(printf '%s\n' "$PODS" | awk '{print $2}'); do
  case ",$BASE," in *",$u,"*) bad "a drain-web Pod is the one from before: node01 was not drained (its Pods were never evicted)" ;; esac
done
RS=$($KC -n default get configmap drain-baseline -o jsonpath='{.data.rs}' 2>/dev/null)
[ -n "$RS" ] || { echo "FAIL: internal: drain-baseline has no ReplicaSet name"; exit 4; }
[ "$($KC -n default get pods -l app=drain-web -o jsonpath='{range .items[*]}{.metadata.ownerReferences[0].name}{"\n"}{end}' | grep -vxc "$RS")" = 0 ] || bad "the drain-web Pods belong to a new ReplicaSet: the Deployment was restarted instead of node01 being drained"
[ -z "$($KC -n default get deployment drain-web -o jsonpath='{.spec.template.metadata.annotations.kubectl\.kubernetes\.io/restartedAt}')" ] || bad "the Deployment was restarted (rollout restart) instead of node01 being drained"
echo ok
EOS
)
RC=$?
case $RC in
  0) ;;
  3) fail "$(printf '%s\n' "$OUT" | sed -n 's/^FAIL: //p' | head -n 1)" ;;
  *) fail "could not check controlplane (exit $RC): $(echo "$OUT" | tail -n 3)" ;;
esac
echo "✅ node01 was drained and is schedulable again; drain-web runs on it with new Pods"
exit 0
