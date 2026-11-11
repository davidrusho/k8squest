#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

N=$(kubectl get node k8squest-control-plane -o json 2>/dev/null)
[[ "$(echo "$N" | jq -r .metadata.name)" == "k8squest-control-plane" ]] || fail "could not read node k8squest-control-plane"
[[ "$(echo "$N" | jq '.spec.unschedulable // false')" == "true" ]] || fail "node k8squest-control-plane is still schedulable"
P=$(kubectl get pod web -n "$NS" -o json 2>/dev/null)
[[ -n "$P" ]] || fail "Pod web does not exist any more"
WANT=$(kubectl get cm web-uid -n "$NS" -o jsonpath='{.data.uid}' 2>/dev/null) || fail "the baseline ConfigMap web-uid is missing"
[[ "$(echo "$P" | jq -r .metadata.uid)" == "$WANT" ]] || fail "Pod web was recreated; it must not be evicted"
[[ "$(echo "$P" | jq -r '.status.phase')" == "Running" && "$(echo "$P" | jq -r '.metadata.deletionTimestamp // "none"')" == "none" ]] || fail "Pod web is not running"
echo "✅ node k8squest-control-plane is cordoned and Pod web is still running"
exit 0
