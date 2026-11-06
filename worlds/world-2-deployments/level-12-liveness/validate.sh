#!/bin/bash

# Check if pods are running and NOT constantly restarting
RESTART_COUNT=$(kubectl get pods -n k8squest -l app=api -o jsonpath='{.items[*].status.containerStatuses[*].restartCount}' 2>/dev/null | awk '{for(i=1;i<=NF;i++) sum+=$i} END {print sum+0}')
RUNNING_PODS=$(kubectl get pods -n k8squest -l app=api -o jsonpath='{.items[?(@.status.phase=="Running")].metadata.name}' 2>/dev/null | wc -w | tr -d ' ')

# The current Deployment spec must have fully rolled out, so pods created from the old spec do not count
DESIRED=$(kubectl get deployment api-server -n k8squest -o jsonpath='{.spec.replicas}' 2>/dev/null)
GENERATION=$(kubectl get deployment api-server -n k8squest -o jsonpath='{.metadata.generation}' 2>/dev/null)
OBSERVED=$(kubectl get deployment api-server -n k8squest -o jsonpath='{.status.observedGeneration}' 2>/dev/null)
UPDATED=$(kubectl get deployment api-server -n k8squest -o jsonpath='{.status.updatedReplicas}' 2>/dev/null)
TOTAL=$(kubectl get deployment api-server -n k8squest -o jsonpath='{.status.replicas}' 2>/dev/null)
READY=$(kubectl get deployment api-server -n k8squest -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
ROLLED_OUT=no
if [ -n "$DESIRED" ] && [ "$OBSERVED" = "$GENERATION" ] && [ "$UPDATED" = "$DESIRED" ] && [ "$TOTAL" = "$DESIRED" ] && [ "$READY" = "$DESIRED" ]; then
    ROLLED_OUT=yes
fi

# The liveness probe must still exist and its HTTP endpoint must answer with a success status
# when requested from the API server through the pod proxy (a probe that is removed or still points at a 404 fails)
PROBE=$(kubectl get deployment api-server -n k8squest -o jsonpath='{.spec.template.spec.containers[0].livenessProbe}' 2>/dev/null)
PROBE_PATH=$(kubectl get deployment api-server -n k8squest -o jsonpath='{.spec.template.spec.containers[0].livenessProbe.httpGet.path}' 2>/dev/null)
PROBE_PORT=$(kubectl get deployment api-server -n k8squest -o jsonpath='{.spec.template.spec.containers[0].livenessProbe.httpGet.port}' 2>/dev/null)
ENDPOINT=ok
if [ -z "$PROBE" ]; then
    ENDPOINT="no liveness probe configured"
elif [ -n "$PROBE_PATH" ]; then
    case "$PROBE_PORT" in
        ''|*[!0-9]*) PROBE_PORT=$(kubectl get deployment api-server -n k8squest -o jsonpath='{.spec.template.spec.containers[0].ports[0].containerPort}' 2>/dev/null) ;;
    esac
    POD=$(kubectl get pods -n k8squest -l app=api -o jsonpath='{.items[?(@.status.phase=="Running")].metadata.name}' 2>/dev/null | awk '{print $1}')
    # Request through the API server's pod proxy (read-only GET): needs no wget or shell in the player's image
    if [ -z "$POD" ] || ! kubectl get --raw "/api/v1/namespaces/k8squest/pods/${POD}:${PROBE_PORT:-80}/proxy${PROBE_PATH}" >/dev/null 2>&1; then
        ENDPOINT="probe path ${PROBE_PATH} does not return a success status"
    fi
fi

# Give a grace period - if restarts are low (< 3 total) and pods are running, consider it fixed
if [ "$RUNNING_PODS" -eq 2 ] && [ "$RESTART_COUNT" -lt 3 ] && [ "$ROLLED_OUT" = "yes" ] && [ "$ENDPOINT" = "ok" ]; then
    echo "✅ Pods are running stably with $RUNNING_PODS/2 ready"
    echo "   Total restart count: $RESTART_COUNT (healthy)"
    echo "   Liveness probe: ${PROBE_PATH:-configured} answers successfully"
    exit 0
else
    echo "❌ Pods are not healthy"
    echo "   Running pods: $RUNNING_PODS/2"
    echo "   Total restarts: $RESTART_COUNT"
    echo "   Rollout of current spec complete: $ROLLED_OUT"
    echo "   Liveness endpoint: $ENDPOINT"
    if [ "$RESTART_COUNT" -ge 3 ]; then
        echo "   ⚠️  Too many restarts - liveness probe likely failing!"
    fi
    exit 1
fi
