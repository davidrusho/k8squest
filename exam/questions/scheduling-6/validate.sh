#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

N=$(kubectl get node k8squest-control-plane -o json 2>/dev/null)
[[ "$(echo "$N" | jq -r .metadata.name)" == "k8squest-control-plane" ]] || fail "could not read node k8squest-control-plane"
P=$(kubectl get pod ssdpod -n "$NS" -o json 2>/dev/null)
[[ -n "$P" ]] || fail "Pod ssdpod does not exist"
WANT=$(kubectl get cm ssdpod-uid -n "$NS" -o jsonpath='{.data.uid}' 2>/dev/null) || fail "the baseline ConfigMap ssdpod-uid is missing"
[[ "$(echo "$P" | jq -r .metadata.uid)" == "$WANT" ]] || fail "Pod ssdpod was recreated; fix it without touching the Pod"
[[ "$(echo "$P" | jq -cS '.spec.nodeSelector')" == '{"disk":"ssd"}' ]] || fail "the Pod's nodeSelector was changed"
[[ "$(echo "$N" | jq -r '.metadata.labels.disk // "unset"')" == "ssd" ]] || fail "node k8squest-control-plane has no label disk=ssd"
[[ "$(echo "$P" | jq -r '.spec.nodeName // ""')" == "k8squest-control-plane" ]] || fail "Pod ssdpod is not scheduled onto the node yet"
echo "✅ Pod ssdpod is scheduled onto the labelled node"
exit 0
