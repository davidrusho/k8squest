#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

T=$(kubectl get svc my-svc -n "$NS" -o jsonpath='{.spec.type}' 2>/dev/null)
[[ -n "$T" ]] || fail "Service my-svc does not exist in namespace $NS"
[[ "$T" == "ClusterIP" ]] || fail "Service my-svc is type $T, expected ClusterIP"
CIP=$(kubectl get svc my-svc -n "$NS" -o jsonpath='{.spec.clusterIP}' 2>/dev/null)
[[ "$CIP" != "None" && -n "$CIP" ]] || fail "Service my-svc is headless, expected a cluster IP"
PORTS=$(kubectl get svc my-svc -n "$NS" -o jsonpath='{.spec.ports[*].port}' 2>/dev/null)
[[ "$PORTS" == "80" ]] || fail "Service my-svc ports are '${PORTS:-none}', expected only 80"
PROTO=$(kubectl get svc my-svc -n "$NS" -o jsonpath='{.spec.ports[0].protocol}' 2>/dev/null)
[[ "${PROTO:-TCP}" == "TCP" ]] || fail "Port 80 of my-svc uses protocol $PROTO, expected TCP"
TP=$(kubectl get svc my-svc -n "$NS" -o jsonpath='{.spec.ports[0].targetPort}' 2>/dev/null)
[[ "$TP" == "8080" ]] || fail "targetPort of my-svc is '${TP:-unset}', expected 8080"
echo "✅ my-svc is a ClusterIP Service on port 80 with targetPort 8080"
exit 0
