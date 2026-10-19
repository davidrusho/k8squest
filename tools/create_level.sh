#!/bin/bash
# K8sQuest - Quick Level Creation Script
# Usage: ./create_level.sh <world-number> <level-number> <level-name> <short-description>

set -e

if [ "$#" -lt 4 ]; then
    echo "Usage: $0 <world-num> <level-num> <level-name> <short-description>"
    echo "Example: $0 2 11 deployment-stuck \"Rolling update failed\""
    exit 1
fi

WORLD_NUM=$1
LEVEL_NUM=$2
LEVEL_NAME=$3
DESCRIPTION=$4

# Determine world directory name from worlds/*/world.yaml (`order: N`)
WORLD_DIR=""
for world_yaml in worlds/*/world.yaml; do
    if grep -qx "order: $WORLD_NUM" "$world_yaml"; then
        WORLD_DIR=$(basename "$(dirname "$world_yaml")")
        break
    fi
done

if [ -z "$WORLD_DIR" ]; then
    echo "No world with 'order: $WORLD_NUM' found. Known worlds:"
    grep -H "^order:" worlds/*/world.yaml
    exit 1
fi

LEVEL_DIR="worlds/$WORLD_DIR/level-$LEVEL_NUM-$LEVEL_NAME"

# Level directory names must be unique across all worlds
if ls -d worlds/*/"level-$LEVEL_NUM-$LEVEL_NAME" >/dev/null 2>&1; then
    echo "Level already exists: level-$LEVEL_NUM-$LEVEL_NAME"
    exit 1
fi

# Create directory
mkdir -p "$LEVEL_DIR"

# Create mission.yaml
cat > "$LEVEL_DIR/mission.yaml" <<EOF
name: "$DESCRIPTION"
description: "TODO: Add detailed description"
objective: "TODO: Add objective"
xp: 200
difficulty: intermediate
expected_time: 15m
concepts:
  - TODO
  - Add
  - Concepts
EOF

# Create broken.yaml
cat > "$LEVEL_DIR/broken.yaml" <<EOF
# TODO: Add intentionally broken Kubernetes resources
apiVersion: v1
kind: Pod
metadata:
  name: example-pod
  namespace: k8squest
spec:
  containers:
  - name: app
    image: nginx:latest
EOF

# Create solution.yaml
cat > "$LEVEL_DIR/solution.yaml" <<EOF
# TODO: Add the fixed Kubernetes resources
apiVersion: v1
kind: Pod
metadata:
  name: example-pod
  namespace: k8squest
spec:
  containers:
  - name: app
    image: nginx:latest
EOF

# Create validate.sh
cat > "$LEVEL_DIR/validate.sh" <<'EOF'
#!/bin/bash

# TODO: Add validation logic
POD_STATUS=$(kubectl get pod example-pod -n k8squest -o jsonpath='{.status.phase}' 2>/dev/null)

if [ "$POD_STATUS" = "Running" ]; then
    echo "✅ Validation passed"
    exit 0
else
    echo "❌ Validation failed"
    exit 1
fi
EOF

chmod +x "$LEVEL_DIR/validate.sh"

# Create hint files
cat > "$LEVEL_DIR/hint-1.txt" <<EOF
🔍 Observation Hint:

TODO: Add observation hint
Run: kubectl get pods -n k8squest
EOF

cat > "$LEVEL_DIR/hint-2.txt" <<EOF
🧭 Direction Hint:

TODO: Add direction hint
Check: kubectl describe pod <name> -n k8squest
EOF

cat > "$LEVEL_DIR/hint-3.txt" <<EOF
💡 Near-Solution Hint:

TODO: Add near-solution hint with specific commands
EOF

# Create debrief.md
cat > "$LEVEL_DIR/debrief.md" <<EOF
# 🎓 Mission Debrief: $DESCRIPTION

## What Happened

TODO: Explain what was broken and why

## How Kubernetes Behaved

TODO: Explain Kubernetes behavior

## The Correct Mental Model

TODO: Teach the concept properly

## Real-World Incident Example

**Company**: TODO  
**Impact**: TODO  
**Cost**: TODO

**What happened**: TODO

## Commands You Mastered

\`\`\`bash
# TODO: Add relevant commands
kubectl get pods -n k8squest
\`\`\`

## What's Next

TODO: Preview next challenge
EOF

echo "✅ Created level structure: $LEVEL_DIR"
echo ""
echo "Next steps:"
echo "1. Edit $LEVEL_DIR/mission.yaml - Add mission details"
echo "2. Edit $LEVEL_DIR/broken.yaml - Add broken K8s resources"
echo "3. Edit $LEVEL_DIR/solution.yaml - Add the fixed resources"
echo "4. Edit $LEVEL_DIR/validate.sh - Add validation logic"
echo "5. Edit $LEVEL_DIR/hint-*.txt - Add progressive hints"
echo "6. Edit $LEVEL_DIR/debrief.md - Add learning content"
echo ""
echo "Test with: ./play.sh"
