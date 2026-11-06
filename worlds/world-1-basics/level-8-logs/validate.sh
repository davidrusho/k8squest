#!/bin/bash

echo "🔍 Checking pod status and stability..."

POD_STATUS=$(kubectl get pod database-app -n k8squest -o jsonpath='{.status.phase}' 2>/dev/null)
READY=$(kubectl get pod database-app -n k8squest -o jsonpath='{.status.containerStatuses[0].ready}' 2>/dev/null)
RESTART_COUNT=$(kubectl get pod database-app -n k8squest -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null)
# Accept the variable set directly (value) or from a Secret/ConfigMap (valueFrom)
PASSWORD_SET=$(kubectl get pod database-app -n k8squest -o jsonpath='{.spec.containers[0].env[?(@.name=="POSTGRES_PASSWORD")].name}' 2>/dev/null)
# ...or from envFrom (configMapRef/secretRef): the referenced object must hold the key (prefix applied) with a value
if [[ -z "$PASSWORD_SET" ]]; then
    while IFS=$'\t' read -r KIND REF PREFIX; do
        [[ -n "$REF" ]] || continue
        if kubectl get "$KIND" "$REF" -n k8squest -o json 2>/dev/null | jq -e --arg want POSTGRES_PASSWORD --arg p "$PREFIX" \
            '(.data // {}) | to_entries | any(($p + .key) == $want and .value != "")' >/dev/null 2>&1; then
            PASSWORD_SET=POSTGRES_PASSWORD
        fi
    done < <(kubectl get pod database-app -n k8squest -o json 2>/dev/null | jq -r '.spec.containers[0].envFrom[]?
        | [(if .configMapRef then "configmap" else "secret" end), (.configMapRef.name // .secretRef.name // ""), (.prefix // "")] | @tsv' 2>/dev/null)
fi

echo "   Pod Phase: $POD_STATUS"
echo "   Ready: $READY"
echo "   Restarts: $RESTART_COUNT"
echo "   PostgreSQL password configured: $([[ -n "$PASSWORD_SET" ]] && echo yes || echo no)"

if [[ "$POD_STATUS" == "Running" ]] && [[ "$READY" == "true" ]] && [[ "$RESTART_COUNT" -eq 0 ]] && [[ -n "$PASSWORD_SET" ]]; then
    echo "✅ Pod is running without restarts"
    exit 0
else
    echo "❌ Pod is not stable - Status: $POD_STATUS, Restarts: $RESTART_COUNT"
    echo "💡 Hint: Check logs with 'kubectl logs database-app -n k8squest'"
    echo "💡 Look for the PostgreSQL error about missing POSTGRES_PASSWORD"
    exit 1
fi
