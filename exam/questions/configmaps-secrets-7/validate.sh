#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

S=$(kubectl get secret regcred -n "$NS" -o json 2>/dev/null)
[[ -n "$S" ]] || fail "secret regcred does not exist in namespace $NS"
GOT=$(echo "$S" | jq -cS '.type')
[[ "$GOT" == '"kubernetes.io/dockerconfigjson"' ]] || fail "type is $GOT, expected "'"kubernetes.io/dockerconfigjson"'
GOT=$(echo "$S" | jq -cS '.data[".dockerconfigjson"] | @base64d | fromjson | .auths | to_entries | map({s: .key, u: .value.username, p: .value.password})')
[[ "$GOT" == '[{"p":"pass","s":"registry.io","u":"user"}]' ]] || fail "registry credentials is $GOT, expected "'[{"p":"pass","s":"registry.io","u":"user"}]'
echo "✅ Secret regcred holds credentials for registry.io"
exit 0
