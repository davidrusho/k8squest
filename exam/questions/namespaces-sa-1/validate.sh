#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

PH=$(kubectl get ns devns -o jsonpath='{.status.phase}' 2>/dev/null)
[[ -n "$PH" ]] || fail "Namespace devns does not exist"
[[ "$PH" == "Active" ]] || fail "Namespace devns is $PH, expected Active"
echo "✅ namespace devns exists"
exit 0
