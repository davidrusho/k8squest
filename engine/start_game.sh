#!/bin/bash
set -e

# First world = the world.yaml with the lowest `order`
WORLD_YAML=$(for y in worlds/*/world.yaml; do
  printf '%s %s\n' "$(sed -n 's/^order: *\([0-9]*\).*/\1/p' "$y")" "$y"
done | sort -n | head -n 1 | awk '{print $2}')
WORLD_DIR=$(dirname "$WORLD_YAML")

LEVELS=$(for d in "$WORLD_DIR"/level-*; do
  printf '%s %s\n' "$(basename "$d" | cut -d- -f2)" "$d"
done | sort -n | awk '{print $2}')

for LEVEL in $LEVELS; do
  echo "=================================="
  echo "▶ Starting $(basename $LEVEL)"
  echo "=================================="

  kubectl delete namespace k8squest --ignore-not-found
  kubectl create namespace k8squest

  kubectl apply -n k8squest -f "$LEVEL/broken.yaml"

  echo "❌ Mission deployed. Fix the issue."
  echo "Press ENTER when ready to validate"
  read

  sh "$LEVEL/validate.sh"

done

echo "🎉 $(basename "$WORLD_DIR") completed!"
