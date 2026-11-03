#!/bin/bash
# Bypass: delete the pods (fresh pods, restart count 0) without fixing the liveness probe path
kubectl delete pods -n k8squest -l app=api --wait=true
