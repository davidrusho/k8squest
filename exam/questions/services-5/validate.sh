#!/bin/bash

NS="${NAMESPACE:-k8squest}"

fail() { echo "❌ $1"; exit 1; }

T=$(kubectl get svc np1 -n "$NS" -o jsonpath='{.spec.type}' 2>/dev/null)
[[ -n "$T" ]] || fail "Service np1 does not exist in namespace $NS"
[[ "$T" == "NodePort" ]] || fail "Service np1 is type $T, expected NodePort"
CIP=$(kubectl get svc np1 -n "$NS" -o jsonpath='{.spec.clusterIP}' 2>/dev/null)
[[ "$CIP" != "None" && -n "$CIP" ]] || fail "Service np1 is headless, expected a cluster IP"
PORTS=$(kubectl get svc np1 -n "$NS" -o jsonpath='{.spec.ports[*].port}' 2>/dev/null)
[[ "$PORTS" == "80" ]] || fail "Service np1 ports are '${PORTS:-none}', expected only 80"
PROTO=$(kubectl get svc np1 -n "$NS" -o jsonpath='{.spec.ports[0].protocol}' 2>/dev/null)
[[ "${PROTO:-TCP}" == "TCP" ]] || fail "Port 80 of np1 uses protocol $PROTO, expected TCP"
TP=$(kubectl get svc np1 -n "$NS" -o jsonpath='{.spec.ports[0].targetPort}' 2>/dev/null)
[[ "$TP" == "80" ]] || fail "targetPort of np1 is '${TP:-unset}', expected 80"
NP=$(kubectl get svc np1 -n "$NS" -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null)
[[ "$NP" == "30777" ]] || fail "Service np1 has nodePort '${NP:-unset}', expected 30777"
echo "✅ np1 is a NodePort Service on port 80 with node port 30777"
exit 0
