#!/bin/bash
# Test script for all K8sQuest levels
# Walks every world under worlds/ and validates world.yaml and that every level
# has the 8 mandatory files (docs/contributing.md) and valid mission metadata.
# Run from the repository root.

set -e

PASSED=0
FAILED=0
WORLD_FAILED=0
TOTAL_LEVELS=0
LEVEL_NAMES=""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

VALID_CLUSTERS_REGEX='^cluster: *"?(kind|kind-multinode|lima)"?[[:space:]]*$'

echo "=================================================="
echo "  K8sQuest Level Validation Test"
echo "=================================================="
echo ""

# Function to test a world directory (world.yaml)
test_world() {
    local world_dir=$1
    local world_yaml="$world_dir/world.yaml"
    local problems=()

    echo -n "Testing world $(basename "$world_dir")... "

    if [ ! -f "$world_yaml" ]; then
        echo -e "${RED}FAIL${NC}"
        echo "   Missing/Invalid: world.yaml"
        WORLD_FAILED=$((WORLD_FAILED + 1))
        return 1
    fi

    local field
    for field in order title description cluster requires; do
        if ! grep -q "^$field:" "$world_yaml"; then
            problems+=("field '$field'")
        fi
    done
    if ! grep -qE '^order: *[0-9]+[[:space:]]*$' "$world_yaml"; then
        problems+=("order must be an integer")
    fi
    if ! grep -qE "$VALID_CLUSTERS_REGEX" "$world_yaml"; then
        problems+=("cluster must be kind, kind-multinode or lima")
    fi

    if [ ${#problems[@]} -eq 0 ]; then
        echo -e "${GREEN}PASS${NC}"
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        echo "   Missing/Invalid: ${problems[*]}"
        WORLD_FAILED=$((WORLD_FAILED + 1))
        return 1
    fi
}

# Function to test a level
test_level() {
    local level_dir=$1
    local level_name
    level_name=$(basename "$level_dir")

    echo -n "  Testing $level_name... "

    # Check required files (the 8 mandatory files)
    local required_files=(
        "mission.yaml"
        "broken.yaml"
        "solution.yaml"
        "validate.sh"
        "hint-1.txt"
        "hint-2.txt"
        "hint-3.txt"
        "debrief.md"
    )

    local missing_files=()
    for file in "${required_files[@]}"; do
        if [ ! -f "$level_dir/$file" ]; then
            missing_files+=("$file")
        fi
    done

    # Check if validate.sh is executable
    if [ -f "$level_dir/validate.sh" ] && [ ! -x "$level_dir/validate.sh" ]; then
        missing_files+=("validate.sh (not executable)")
    fi

    # Check mission.yaml has required fields
    if [ -f "$level_dir/mission.yaml" ]; then
        if ! grep -q "^name:" "$level_dir/mission.yaml" || \
           ! grep -q "^xp:" "$level_dir/mission.yaml" || \
           ! grep -q "^difficulty:" "$level_dir/mission.yaml"; then
            missing_files+=("mission.yaml (missing required fields)")
        fi
    fi

    if [ ${#missing_files[@]} -eq 0 ]; then
        echo -e "${GREEN}PASS${NC}"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        echo "   Missing/Invalid: ${missing_files[*]}"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

# A directory under worlds/ without world.yaml is invisible to the engine
for world_dir in worlds/*/; do
    world_dir=${world_dir%/}
    if [ ! -f "$world_dir/world.yaml" ]; then
        test_world "$world_dir" || true
    fi
done

# Worlds sorted by the `order` field in world.yaml
WORLD_DIRS=$(for y in worlds/*/world.yaml; do
    printf '%s %s\n' "$(sed -n 's/^order: *\([0-9]*\).*/\1/p' "$y")" "$(dirname "$y")"
done | sort -n | awk '{print $2}')

for world_dir in $WORLD_DIRS; do
    echo -e "${YELLOW}$(basename "$world_dir")${NC}"
    echo "--------------------------------------"
    test_world "$world_dir" || true
    for level_dir in "$world_dir"/level-*; do
        [ -d "$level_dir" ] || continue
        TOTAL_LEVELS=$((TOTAL_LEVELS + 1))
        LEVEL_NAMES="$LEVEL_NAMES$(basename "$level_dir")"$'\n'
        test_level "$level_dir" || true
    done
    echo ""
done

# Level names must be unique across worlds
DUPLICATES=$(printf '%s' "$LEVEL_NAMES" | sort | uniq -d)
if [ -n "$DUPLICATES" ]; then
    echo -e "${RED}Duplicate level names across worlds:${NC} $DUPLICATES"
    FAILED=$((FAILED + 1))
fi

# Summary
echo "=================================================="
echo "  Test Summary"
echo "=================================================="
echo -e "Total Levels Tested: $TOTAL_LEVELS"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo -e "${RED}World problems: $WORLD_FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ] && [ $WORLD_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All levels validated successfully!${NC}"
    echo "All $TOTAL_LEVELS levels are ready to play."
    exit 0
else
    echo -e "${RED}❌ Some levels have issues.${NC}"
    echo "Please review the failures above."
    exit 1
fi
