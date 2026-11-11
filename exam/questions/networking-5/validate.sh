#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

NP=$(kubectl get networkpolicy default-deny -n "$NS" -o json 2>/dev/null)
[[ -n "$NP" ]] || fail "NetworkPolicy default-deny does not exist in namespace $NS"
PT=$(echo "$NP" | jq -c '.spec.policyTypes // ["Ingress"]')
[[ "$PT" == '["Ingress"]' ]] || fail "NetworkPolicy default-deny policyTypes are $PT, expected only Ingress"
[[ "$(echo "$NP" | jq -c '.spec.podSelector')" == '{}' ]] || fail "NetworkPolicy default-deny must select every Pod (empty podSelector), found $(echo "$NP" | jq -c '.spec.podSelector')"
[[ "$(echo "$NP" | jq '(.spec.ingress // []) | length')" == "0" ]] || fail "NetworkPolicy default-deny must have no ingress rules"
echo "✅ default-deny blocks all ingress to every Pod"
exit 0
