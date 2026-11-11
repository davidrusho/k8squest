#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

D=$(kubectl get deploy web -n "$NS" -o json 2>/dev/null)
[[ -n "$D" ]] || fail "deploy web does not exist in namespace $NS"
EF=$(echo "$D" | jq '[.spec.template.spec.containers[0].envFrom[]? | select(.configMapRef.name=="app-config")] | length')
if [[ "$EF" -lt 1 ]]; then
  # no envFrom entry: every key of the ConfigMap must then be wired through its own configMapKeyRef variable
  WANT=$(kubectl get cm app-config -n "$NS" -o json 2>/dev/null | jq -cS '.data | keys')
  GOT=$(echo "$D" | jq -cS '[.spec.template.spec.containers[0].env[]? | select(.valueFrom.configMapKeyRef.name=="app-config") | .valueFrom.configMapKeyRef.key] | unique')
  [[ -n "$WANT" && "$GOT" == "$WANT" ]] || fail "container variables come from ConfigMap keys $GOT, expected every key $WANT (or an envFrom entry)"
fi
echo "✅ Deployment web loads ConfigMap app-config through envFrom"
exit 0
