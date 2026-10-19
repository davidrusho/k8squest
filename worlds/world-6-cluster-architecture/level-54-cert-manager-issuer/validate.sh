#!/bin/bash
NAMESPACE="${NAMESPACE:-k8squest}"
CERT="web-cert"

echo "🔍 Stage 1: Does the Certificate exist?"
if ! kubectl get certificate "$CERT" -n "$NAMESPACE" >/dev/null 2>&1; then
    echo "❌ Certificate '$CERT' not found"
    exit 1
fi
echo "✅ Certificate exists"

echo ""
echo "🔍 Stage 2: Does its issuerRef point at an issuer that exists?"
KIND=$(kubectl get certificate "$CERT" -n "$NAMESPACE" -o jsonpath='{.spec.issuerRef.kind}')
NAME=$(kubectl get certificate "$CERT" -n "$NAMESPACE" -o jsonpath='{.spec.issuerRef.name}')
KIND=${KIND:-Issuer}
if [ "$KIND" = "ClusterIssuer" ]; then
    FOUND=$(kubectl get clusterissuer "$NAME" -o name 2>/dev/null)
else
    FOUND=$(kubectl get issuer "$NAME" -n "$NAMESPACE" -o name 2>/dev/null)
fi
if [ -z "$FOUND" ]; then
    echo "❌ issuerRef is $KIND/$NAME, and no such object exists (an Issuer is namespaced, a ClusterIssuer is not)"
    echo "💡 kubectl get issuer,clusterissuer -A"
    exit 1
fi
echo "✅ issuerRef $KIND/$NAME exists"

echo ""
echo "🔍 Stage 3: Is the Certificate Ready?"
READY=$(kubectl get certificate "$CERT" -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')
if [ "$READY" != "True" ]; then
    echo "❌ Ready condition is '${READY:-unset}'"
    echo "💡 kubectl describe certificate $CERT -n $NAMESPACE"
    exit 1
fi
echo "✅ Ready=True"

echo ""
echo "🔍 Stage 4: Was the TLS Secret issued?"
if [ -z "$(kubectl get secret web-cert-tls -n "$NAMESPACE" -o jsonpath='{.data.tls\.crt}' 2>/dev/null)" ]; then
    echo "❌ Secret web-cert-tls has no tls.crt"
    exit 1
fi
echo "✅ Secret web-cert-tls holds the certificate"

echo ""
echo "🎉 SUCCESS! cert-manager issued the certificate."
exit 0
