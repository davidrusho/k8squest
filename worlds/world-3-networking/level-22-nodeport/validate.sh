#!/bin/bash

# Check the Service type and the explicitly requested NodePort (mission.yaml: 30080)
SVC_TYPE=$(kubectl get svc web-nodeport -n k8squest -o jsonpath='{.spec.type}' 2>/dev/null)
NODEPORT=$(kubectl get svc web-nodeport -n k8squest -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null)

if [[ -z "$NODEPORT" ]]; then
  echo "❌ Service not found"
  exit 1
fi

if [[ "$SVC_TYPE" != "NodePort" ]]; then
  echo "❌ Service type is $SVC_TYPE, expected NodePort"
  exit 1
fi

# Check if NodePort is the one the mission asks for (30080)
if [[ "$NODEPORT" != "30080" ]]; then
  echo "❌ NodePort is $NODEPORT. The mission requires nodePort: 30080"
  exit 1
fi

# The Service must actually route: its selector must match a Ready pod
ENDPOINTS=$(kubectl get endpoints web-nodeport -n k8squest -o jsonpath='{.subsets[*].addresses[*].ip}' 2>/dev/null)
if [[ -z "$ENDPOINTS" ]]; then
  echo "❌ NodePort is 30080 but the Service has no endpoints"
  echo "💡 Check that the selector matches the pod labels and the pod is Ready"
  exit 1
fi

echo "✅ Level complete! NodePort explicitly configured"
echo "   web-nodeport exposes 30080 and routes to: $ENDPOINTS"
exit 0
