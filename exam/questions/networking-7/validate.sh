#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

NP=$(kubectl get networkpolicy allow-prod-ns -n "$NS" -o json 2>/dev/null)
[[ -n "$NP" ]] || fail "NetworkPolicy allow-prod-ns does not exist in namespace $NS"
PT=$(echo "$NP" | jq -c '.spec.policyTypes // ["Ingress"]')
[[ "$PT" == '["Ingress"]' ]] || fail "NetworkPolicy allow-prod-ns policyTypes are $PT, expected only Ingress"
[[ "$(echo "$NP" | jq -c '.spec.podSelector')" == '{"matchLabels":{"app":"web"}}' ]] || fail "NetworkPolicy allow-prod-ns must select Pods app=web, found $(echo "$NP" | jq -c '.spec.podSelector')"
[[ "$(echo "$NP" | jq '.spec.ingress | length')" == "1" ]] || fail "NetworkPolicy allow-prod-ns must have exactly one ingress rule"
[[ "$(echo "$NP" | jq '.spec.ingress[0].from | length')" == "1" ]] || fail "the ingress rule must have exactly one from entry"
PEER=$(echo "$NP" | jq -c '.spec.ingress[0].from[0]')
[[ "$(echo "$PEER" | jq -c 'keys - ["namespaceSelector","podSelector"]')" == "[]" ]] || fail "from entry is $PEER, expected only a namespaceSelector (and optionally an empty podSelector)"
[[ "$(echo "$PEER" | jq -c '.podSelector // {}')" == "{}" ]] || fail "from entry podSelector must be empty, found $(echo "$PEER" | jq -c '.podSelector')"
SEL=$(echo "$PEER" | jq -c '.namespaceSelector // empty')
[[ -n "$SEL" ]] || fail "from entry has no namespaceSelector"
[[ "$(echo "$SEL" | jq -c 'keys - ["matchLabels"]')" == "[]" && "$(echo "$SEL" | jq '.matchLabels | length')" -ge 1 ]] || fail "namespaceSelector must use matchLabels only, found $SEL"
MATCHED=$(kubectl get ns -o json 2>/dev/null | jq -r --argjson sel "$SEL" '.items[] | select(.metadata.labels as $l | $sel.matchLabels | to_entries | all(.value == $l[.key])) | .metadata.name' | sort | tr '\n' ' ')
[[ "$MATCHED" == "prodns " ]] || fail "namespaceSelector $SEL selects: ${MATCHED:-no namespace}; expected exactly prodns"
PORTS=$(echo "$NP" | jq -c '[.spec.ingress[0].ports[]? | {port, protocol: (.protocol // "TCP")}]')
[[ "$PORTS" == '[{"port":80,"protocol":"TCP"}]' ]] || fail "ingress ports are $PORTS, expected only TCP 80"
echo "✅ allow-prod-ns allows TCP 80 to app=web Pods only from namespace prodns"
exit 0
