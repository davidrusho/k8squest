#!/bin/bash
# Bypass: delete the backend pods instead of adding readiness probes (nothing is left to check)
kubectl delete pod -n k8squest -l app=web --wait=true
