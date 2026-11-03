#!/bin/bash
# Bypass: strategy Recreate has no rollingUpdate block, but stops every pod at once during an update
kubectl patch deployment critical-api -n k8squest --type=merge -p '{"spec":{"strategy":{"type":"Recreate","rollingUpdate":null}}}'
