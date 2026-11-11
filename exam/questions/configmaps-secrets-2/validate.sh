#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

D=$(kubectl get cm file-config -n "$NS" -o json 2>/dev/null)
[[ -n "$D" ]] || fail "ConfigMap file-config does not exist in namespace $NS"
KEYS=$(echo "$D" | jq -c '.data | keys')
[[ "$KEYS" == '["config.properties"]' ]] || fail "ConfigMap keys are $KEYS, expected only config.properties"
GOT=$(echo "$D" | jq -r '.data["config.properties"]')
[[ "$GOT" == $'app.mode=prod\nretries=3' ]] || fail "the value of key config.properties does not match the file"
echo "✅ ConfigMap file-config holds the file config.properties"
exit 0
