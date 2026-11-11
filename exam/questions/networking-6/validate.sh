#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

NP=$(kubectl get networkpolicy allow-client -n "$NS" -o json 2>/dev/null)
[[ -n "$NP" ]] || fail "NetworkPolicy allow-client does not exist in namespace $NS"
PT=$(echo "$NP" | jq -c '.spec.policyTypes // ["Ingress"]')
[[ "$PT" == '["Ingress"]' ]] || fail "NetworkPolicy allow-client policyTypes are $PT, expected only Ingress"
[[ "$(echo "$NP" | jq -c '.spec.podSelector')" == '{"matchLabels":{"app":"web"}}' ]] || fail "NetworkPolicy allow-client must select Pods app=web, found $(echo "$NP" | jq -c '.spec.podSelector')"
[[ "$(echo "$NP" | jq '.spec.ingress | length')" == "1" ]] || fail "NetworkPolicy allow-client must have exactly one ingress rule"
FROM=$(echo "$NP" | jq -c '.spec.ingress[0].from')
[[ "$FROM" == '[{"podSelector":{"matchLabels":{"role":"client"}}}]' ]] || fail "ingress source is $FROM, expected only Pods role=client"
PORTS=$(echo "$NP" | jq -c '[.spec.ingress[0].ports[]? | {port, protocol: (.protocol // "TCP")}]')
[[ "$PORTS" == '[{"port":80,"protocol":"TCP"}]' ]] || fail "ingress ports are $PORTS, expected only TCP 80"
echo "✅ allow-client allows TCP 80 to app=web Pods only from role=client Pods"
exit 0
