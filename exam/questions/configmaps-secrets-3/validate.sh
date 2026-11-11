#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

S=$(kubectl get secret db-creds -n "$NS" -o json 2>/dev/null)
[[ -n "$S" ]] || fail "secret db-creds does not exist in namespace $NS"
GOT=$(echo "$S" | jq -cS '.type')
[[ "$GOT" == '"Opaque"' ]] || fail "type is $GOT, expected "'"Opaque"'
GOT=$(echo "$S" | jq -cS '.data | map_values(@base64d)')
[[ "$GOT" == '{"password":"s3cret","username":"admin"}' ]] || fail "decoded data is $GOT, expected "'{"password":"s3cret","username":"admin"}'
echo "✅ Secret db-creds is Opaque with username=admin and password=s3cret"
exit 0
