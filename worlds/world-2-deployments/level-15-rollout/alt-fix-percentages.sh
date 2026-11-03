#!/bin/bash
# Alternative fix: percentage values (the hints mention them): maxUnavailable 25%, maxSurge 25%
kubectl patch deployment critical-api -n k8squest --type=merge -p '{"spec":{"strategy":{"rollingUpdate":{"maxUnavailable":"25%","maxSurge":"25%"}}}}'
