#!/bin/bash
# Bypass: apply the full solution, then set the PDB minAvailable to the replica count (2), so check 5 (PodDisruptionBudget) is the only one that fails
kubectl apply -f solution.yaml || exit 1
kubectl patch pdb chaos-pdb -n k8squest --type=merge -p '{"spec":{"minAvailable":2}}' || exit 1
