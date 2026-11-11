#!/bin/bash

NS="${NAMESPACE:-k8squest}"

TYPE=$(kubectl get svc web-svc -n "$NS" -o jsonpath='{.spec.type}' 2>/dev/null)
if [[ -z "$TYPE" ]]; then
  echo "❌ Service web-svc does not exist in namespace $NS"
  exit 1
fi
if [[ "$TYPE" != "ClusterIP" ]]; then
  echo "❌ Service web-svc is type $TYPE, expected ClusterIP"
  exit 1
fi

PORTS=$(kubectl get svc web-svc -n "$NS" -o jsonpath='{.spec.ports[*].port}' 2>/dev/null)
if ! echo " $PORTS " | grep -q " 80 "; then
  echo "❌ Service web-svc has no port 80 (ports: ${PORTS:-none})"
  exit 1
fi

# that port entry must be TCP, target port 80 (an unset targetPort defaults to the port), and the Service not headless
CIP=$(kubectl get svc web-svc -n "$NS" -o jsonpath='{.spec.clusterIP}' 2>/dev/null)
if [[ "$CIP" == "None" || -z "$CIP" ]]; then
  echo "❌ Service web-svc is headless (clusterIP: ${CIP:-unset}), expected a cluster IP"
  exit 1
fi
PROTO=$(kubectl get svc web-svc -n "$NS" -o jsonpath='{.spec.ports[?(@.port==80)].protocol}' 2>/dev/null)
if [[ "${PROTO:-TCP}" != "TCP" ]]; then
  echo "❌ Port 80 of web-svc uses protocol $PROTO, expected TCP"
  exit 1
fi
TP=$(kubectl get svc web-svc -n "$NS" -o jsonpath='{.spec.ports[?(@.port==80)].targetPort}' 2>/dev/null)
if [[ -n "$TP" && "$TP" != "80" ]]; then
  echo "❌ Port 80 of web-svc has targetPort $TP, expected 80"
  exit 1
fi

# the Service selector must select the web pods: every key=value of the selector is in the
# Deployment's spec.selector.matchLabels, and it is not empty
SVC_SEL=$(kubectl get svc web-svc -n "$NS" -o go-template='{{range $k, $v := .spec.selector}}{{$k}}={{$v}}{{"\n"}}{{end}}' 2>/dev/null | sort)
DEP_SEL=$(kubectl get deploy web -n "$NS" -o go-template='{{range $k, $v := .spec.selector.matchLabels}}{{$k}}={{$v}}{{"\n"}}{{end}}' 2>/dev/null | sort)
if [[ -z "$SVC_SEL" ]]; then
  echo "❌ Service web-svc has no selector"
  exit 1
fi
while IFS= read -r pair; do
  if ! echo "$DEP_SEL" | grep -qxF "$pair"; then
    echo "❌ Service selector $pair does not match Deployment web's selector"
    exit 1
  fi
done <<< "$SVC_SEL"

ENDPOINTS=$(kubectl get endpoints web-svc -n "$NS" -o jsonpath='{.subsets[*].addresses[*].ip}' 2>/dev/null)
if [[ -z "$ENDPOINTS" ]]; then
  echo "❌ Service web-svc has no ready endpoint addresses"
  exit 1
fi

echo "✅ web-svc is a ClusterIP Service on port 80 selecting the web Pods"
exit 0
