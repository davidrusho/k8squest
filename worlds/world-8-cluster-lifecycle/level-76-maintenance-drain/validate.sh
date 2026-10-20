#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
validate_vms
NAMESPACE="${NAMESPACE:-k8squest}"
fail() { echo "❌ $1"; [ -n "${2:-}" ] && echo "💡 $2"; exit 1; }

echo "🔍 Stage 1: Does the API server answer, and is the budget still in place?"
wait_admin 90 || fail "The API server does not answer"
[ "$(kc -n "$NAMESPACE" get pdb web-pdb -o jsonpath='{.spec.minAvailable}' 2>/dev/null)" = 3 ] \
    || fail "The PodDisruptionBudget web-pdb is missing or changed" "the budget is part of the application; drain around it, do not delete it"
echo "✅ The API server is up and web-pdb (minAvailable: 3) is intact"

echo ""
echo "🔍 Stage 2: Was the worker drained?"
WAS=$(recall 76-worker-pod-uids)
[ -n "$WAS" ] || fail "Could not read the list of web pods that ran on the worker" "reset the level"
NOW=$(kc -n "$NAMESPACE" get pods -l app=web -o jsonpath='{.items[*].metadata.uid}' 2>/dev/null)
for u in $WAS; do
    case " $NOW " in *" $u "*) fail "A web pod that ran on the worker is still there (uid ${u:0:8})" "kubectl drain lima-k8squest-worker --ignore-daemonsets --delete-emptydir-data" ;; esac
done
echo "✅ The web pods that ran on $WK_NODE were evicted and replaced"

echo ""
echo "🔍 Stage 3: Is the worker back in service?"
[ "$(kc get node "$WK_NODE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)" = True ] \
    || fail "$WK_NODE is not Ready" "kubectl get nodes"
[ "$(kc get node "$WK_NODE" -o jsonpath='{.spec.unschedulable}' 2>/dev/null)" != true ] \
    || fail "$WK_NODE is still cordoned (SchedulingDisabled)" "kubectl uncordon $WK_NODE"
echo "✅ $WK_NODE is Ready and schedulable"

echo ""
echo "🔍 Stage 4: Is the application whole?"
AV=$(kc -n "$NAMESPACE" get deployment web -o jsonpath='{.status.availableReplicas}' 2>/dev/null)
[ "${AV:-0}" = 4 ] || fail "${AV:-0} of 4 web replicas are available" "kubectl get pods -n $NAMESPACE -o wide"
echo "✅ All 4 web replicas are available"

echo ""
echo "🎉 SUCCESS! The worker had its maintenance window and the web application never dropped below budget."
exit 0
