#!/bin/bash

echo "🔍 Checking pod and init container status..."

POD_STATUS=$(kubectl get pod web-with-init -n k8squest -o jsonpath='{.status.phase}' 2>/dev/null)
READY=$(kubectl get pod web-with-init -n k8squest -o jsonpath='{.status.containerStatuses[0].ready}' 2>/dev/null)
INIT_EXIT=$(kubectl get pod web-with-init -n k8squest -o jsonpath='{.status.initContainerStatuses[0].state.terminated.exitCode}' 2>/dev/null)

echo "   Pod Phase: $POD_STATUS"
echo "   Ready: $READY"
echo "   Init container exit code: ${INIT_EXIT:-none}"

# The init container must still be there and must have completed (by a Service appearing or by a command that finishes), and the main container must be Ready
if [[ "$POD_STATUS" == "Running" ]] && [[ "$READY" == "true" ]] && [[ "$INIT_EXIT" == "0" ]]; then
    echo "✅ Pod successfully initialized and running"
    exit 0
else
    echo "❌ Pod status: $POD_STATUS (Ready: $READY)"
    echo "💡 The init container must run to completion (exit code 0) and the main container must become Ready"
    echo "💡 Hint: Check init container logs:"
    echo "   kubectl logs web-with-init -n k8squest -c wait-for-service"
    echo "   kubectl describe pod web-with-init -n k8squest"
    exit 1
fi
