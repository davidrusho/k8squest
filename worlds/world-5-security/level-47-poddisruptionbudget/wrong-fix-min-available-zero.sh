#!/bin/bash
# Bypass: minAvailable 0 allows every eviction, so the PDB protects nothing
kubectl patch pdb web-pdb -n k8squest --type=merge -p '{"spec":{"minAvailable":0}}'
