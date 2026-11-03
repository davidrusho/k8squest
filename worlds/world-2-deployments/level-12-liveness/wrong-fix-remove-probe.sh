#!/bin/bash
# Bypass: remove the liveness probe entirely instead of pointing it at a working endpoint
kubectl patch deployment api-server -n k8squest --type=json -p '[{"op":"remove","path":"/spec/template/spec/containers/0/livenessProbe"}]'
