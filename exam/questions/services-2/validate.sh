#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

T=$(kubectl get svc web-np -n "$NS" -o jsonpath='{.spec.type}' 2>/dev/null)
[[ -n "$T" ]] || fail "Service web-np does not exist in namespace $NS"
[[ "$T" == "NodePort" ]] || fail "Service web-np is type $T, expected NodePort"
CIP=$(kubectl get svc web-np -n "$NS" -o jsonpath='{.spec.clusterIP}' 2>/dev/null)
[[ "$CIP" != "None" && -n "$CIP" ]] || fail "Service web-np is headless, expected a cluster IP"
PORTS=$(kubectl get svc web-np -n "$NS" -o jsonpath='{.spec.ports[*].port}' 2>/dev/null)
[[ "$PORTS" == "80" ]] || fail "Service web-np ports are '${PORTS:-none}', expected only 80"
PROTO=$(kubectl get svc web-np -n "$NS" -o jsonpath='{.spec.ports[0].protocol}' 2>/dev/null)
[[ "${PROTO:-TCP}" == "TCP" ]] || fail "Port 80 of web-np uses protocol $PROTO, expected TCP"
TP=$(kubectl get svc web-np -n "$NS" -o jsonpath='{.spec.ports[0].targetPort}' 2>/dev/null)
[[ -z "$TP" || "$TP" == "80" ]] || fail "Port 80 of web-np has targetPort $TP, expected 80"
SVC_SEL=$(kubectl get svc web-np -n "$NS" -o json 2>/dev/null | jq -r '.spec.selector // {} | to_entries[] | "\(.key)=\(.value)"' | sort)
TGT_SEL=$(kubectl get deploy web -n "$NS" -o json 2>/dev/null | jq -r '.spec.selector.matchLabels // {} | to_entries[] | "\(.key)=\(.value)"' | sort)
[[ -n "$SVC_SEL" ]] || fail "Service web-np has no selector"
while IFS= read -r pair; do
  echo "$TGT_SEL" | grep -qxF "$pair" || fail "Service selector $pair does not match deploy web"
done <<< "$SVC_SEL"
EP=$(kubectl get endpoints web-np -n "$NS" -o jsonpath='{.subsets[*].addresses[*].ip}' 2>/dev/null)
[[ -n "$EP" ]] || fail "Service web-np has no ready endpoint addresses"
echo "✅ web-np is a NodePort Service on port 80 selecting the web Pods"
exit 0
