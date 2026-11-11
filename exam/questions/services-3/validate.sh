#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

T=$(kubectl get svc fe-svc -n "$NS" -o jsonpath='{.spec.type}' 2>/dev/null)
[[ -n "$T" ]] || fail "Service fe-svc does not exist in namespace $NS"
[[ "$T" == "ClusterIP" ]] || fail "Service fe-svc is type $T, expected ClusterIP"
CIP=$(kubectl get svc fe-svc -n "$NS" -o jsonpath='{.spec.clusterIP}' 2>/dev/null)
[[ "$CIP" != "None" && -n "$CIP" ]] || fail "Service fe-svc is headless, expected a cluster IP"
PORTS=$(kubectl get svc fe-svc -n "$NS" -o jsonpath='{.spec.ports[*].port}' 2>/dev/null)
[[ "$PORTS" == "80" ]] || fail "Service fe-svc ports are '${PORTS:-none}', expected only 80"
PROTO=$(kubectl get svc fe-svc -n "$NS" -o jsonpath='{.spec.ports[0].protocol}' 2>/dev/null)
[[ "${PROTO:-TCP}" == "TCP" ]] || fail "Port 80 of fe-svc uses protocol $PROTO, expected TCP"
TP=$(kubectl get svc fe-svc -n "$NS" -o jsonpath='{.spec.ports[0].targetPort}' 2>/dev/null)
[[ -z "$TP" || "$TP" == "80" ]] || fail "Port 80 of fe-svc has targetPort $TP, expected 80"
SVC_SEL=$(kubectl get svc fe-svc -n "$NS" -o json 2>/dev/null | jq -r '.spec.selector // {} | to_entries[] | "\(.key)=\(.value)"' | sort)
TGT_SEL=$(kubectl get pod fe -n "$NS" -o json 2>/dev/null | jq -r '.metadata.labels // {} | to_entries[] | "\(.key)=\(.value)"' | sort)
[[ -n "$SVC_SEL" ]] || fail "Service fe-svc has no selector"
while IFS= read -r pair; do
  echo "$TGT_SEL" | grep -qxF "$pair" || fail "Service selector $pair does not match Pod fe"
done <<< "$SVC_SEL"
EP=$(kubectl get endpoints fe-svc -n "$NS" -o jsonpath='{.subsets[*].addresses[*].ip}' 2>/dev/null)
[[ -n "$EP" ]] || fail "Service fe-svc has no ready endpoint addresses"
echo "✅ fe-svc is a ClusterIP Service on port 80 selecting Pod fe"
exit 0
