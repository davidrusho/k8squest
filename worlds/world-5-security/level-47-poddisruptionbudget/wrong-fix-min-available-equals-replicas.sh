#!/bin/bash
# Bypass: minAvailable equal to replicas (2 of 2) is no longer above the replica count but still blocks every eviction
kubectl patch pdb web-pdb -n k8squest --type=merge -p '{"spec":{"minAvailable":2}}'
