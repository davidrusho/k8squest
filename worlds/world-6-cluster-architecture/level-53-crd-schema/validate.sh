#!/bin/bash
cd "$(dirname "$0")"
. ../_shared/lib.sh
NAMESPACE="${NAMESPACE:-k8squest}"
CRD="websites.k8squest.io"
WORK=$(level_workdir level-53-crd-schema)

echo "🔍 Stage 1: Is the CRD installed?"
if ! kubectl get crd "$CRD" >/dev/null 2>&1; then
    echo "❌ CRD $CRD not found"
    exit 1
fi
echo "✅ CRD exists"

echo ""
echo "🔍 Stage 2: Is spec.replicas an integer in the schema?"
TYPE=$(kubectl get crd "$CRD" -o jsonpath='{.spec.versions[?(@.name=="v1")].schema.openAPIV3Schema.properties.spec.properties.replicas.type}')
if [ "$TYPE" != "integer" ]; then
    echo "❌ spec.replicas is declared as '$TYPE' in the CRD schema"
    echo "💡 kubectl explain website.spec.replicas"
    exit 1
fi
echo "✅ replicas is an integer"

echo ""
echo "🔍 Stage 3: Is the schema still enforcing required fields?"
REQ=$(kubectl get crd "$CRD" -o jsonpath='{.spec.versions[?(@.name=="v1")].schema.openAPIV3Schema.properties.spec.required}')
case "$REQ" in
    *domain*replicas*|*replicas*domain*) echo "✅ domain and replicas are still required" ;;
    *) echo "❌ the schema no longer requires domain and replicas; fix the type, do not loosen the schema"; exit 1 ;;
esac

echo ""
echo "🔍 Stage 4: Does the API server accept website.yaml?"
if ! OUT=$(kubectl apply --dry-run=server -f "$WORK/website.yaml" 2>&1); then
    echo "❌ website.yaml is still rejected:"
    echo "$OUT"
    exit 1
fi
echo "✅ website.yaml validates against the CRD"

echo ""
echo "🎉 SUCCESS! The Website resource is accepted. Create it with: kubectl apply -f $WORK/website.yaml"
exit 0
