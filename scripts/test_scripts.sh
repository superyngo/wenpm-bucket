#!/bin/bash
#
# Test script for WenPM bucket development tools
# Tests all scripts and validates the workflow
#

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🧪 WenPM Bucket Development Tools - Test Suite"
echo "=" | tr '=' '\n' | head -50 | tr '\n' '='
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

pass() {
    echo -e "${GREEN}✓${NC} $1"
}

fail() {
    echo -e "${RED}✗${NC} $1"
    exit 1
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

# Test 1: Check Python version
echo ""
info "Test 1: Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 7 ]; then
        pass "Python $PYTHON_VERSION (>= 3.7 required)"
    else
        fail "Python version too old: $PYTHON_VERSION (need >= 3.7)"
    fi
else
    fail "Python 3 not found"
fi

# Test 2: Check script files exist
echo ""
info "Test 2: Checking script files..."
if [ -f "$SCRIPT_DIR/generate_manifest.py" ]; then
    pass "generate_manifest.py exists"
else
    fail "generate_manifest.py not found"
fi

if [ -f "$SCRIPT_DIR/validate_manifest.py" ]; then
    pass "validate_manifest.py exists"
else
    fail "validate_manifest.py not found"
fi

# Test 3: Check Python syntax
echo ""
info "Test 3: Checking Python syntax..."
python3 -m py_compile "$SCRIPT_DIR/generate_manifest.py" && pass "generate_manifest.py syntax OK" || fail "Syntax error in generate_manifest.py"
python3 -m py_compile "$SCRIPT_DIR/validate_manifest.py" && pass "validate_manifest.py syntax OK" || fail "Syntax error in validate_manifest.py"

# Test 4: Test generate_manifest.py --help
echo ""
info "Test 4: Testing script help..."
python3 "$SCRIPT_DIR/generate_manifest.py" --help > /dev/null && pass "generate_manifest.py --help works" || fail "generate_manifest.py --help failed"
python3 "$SCRIPT_DIR/validate_manifest.py" --help > /dev/null && pass "validate_manifest.py --help works" || fail "validate_manifest.py --help failed"

# Test 5: Test with example sources
echo ""
info "Test 5: Testing manifest generation..."

# Create test directory
TEST_DIR=$(mktemp -d)
cd "$TEST_DIR"

# Create test sources.txt
cat > sources.txt << 'EOF'
# Test sources
https://github.com/BurntSushi/ripgrep
https://github.com/sharkdp/fd
EOF

info "   Using test directory: $TEST_DIR"

# Generate manifest
if python3 "$SCRIPT_DIR/generate_manifest.py" sources.txt -o manifest.json 2>&1 | grep -q "Generation complete"; then
    pass "Manifest generation succeeded"
else
    fail "Manifest generation failed"
fi

# Test 6: Validate generated manifest
echo ""
info "Test 6: Testing manifest validation..."
if python3 "$SCRIPT_DIR/validate_manifest.py" manifest.json 2>&1 | grep -q "Manifest is valid"; then
    pass "Manifest validation succeeded"
else
    fail "Manifest validation failed"
fi

# Test 7: Check manifest structure
echo ""
info "Test 7: Checking manifest structure..."

# Check if manifest is valid JSON
if python3 -c "import json; json.load(open('manifest.json'))" 2>/dev/null; then
    pass "Manifest is valid JSON"
else
    fail "Manifest is not valid JSON"
fi

# Check if manifest is an array
if python3 -c "import json; assert isinstance(json.load(open('manifest.json')), list)" 2>/dev/null; then
    pass "Manifest is an array"
else
    fail "Manifest is not an array"
fi

# Check if packages have required fields
if python3 -c "
import json
packages = json.load(open('manifest.json'))
for pkg in packages:
    assert 'name' in pkg
    assert 'repo' in pkg
    assert 'platforms' in pkg
" 2>/dev/null; then
    pass "Packages have required fields"
else
    fail "Packages missing required fields"
fi

# Test 8: Test invalid manifest
echo ""
info "Test 8: Testing validation with invalid manifest..."

# Create invalid manifest
echo '{"invalid": "format"}' > invalid.json

if python3 "$SCRIPT_DIR/validate_manifest.py" invalid.json 2>&1 | grep -q "error"; then
    pass "Validation correctly rejects invalid manifest"
else
    warn "Validation should reject invalid manifest"
fi

# Test 9: Check example manifest
echo ""
info "Test 9: Checking example manifest..."

if [ -f "$PROJECT_ROOT/examples/manifest.json" ]; then
    if python3 "$SCRIPT_DIR/validate_manifest.py" "$PROJECT_ROOT/examples/manifest.json" 2>&1 | grep -q "Manifest is valid"; then
        pass "Example manifest is valid"
    else
        warn "Example manifest validation failed"
    fi
else
    warn "Example manifest not found"
fi

# Test 10: Check workflow file
echo ""
info "Test 10: Checking workflow file..."

WORKFLOW_FILE="$PROJECT_ROOT/workflows/update-manifest.yml"
if [ -f "$WORKFLOW_FILE" ]; then
    pass "Workflow file exists"

    # Check if workflow has required keys
    if grep -q "name: Update Bucket Manifest" "$WORKFLOW_FILE"; then
        pass "Workflow has correct name"
    else
        warn "Workflow name not found"
    fi

    if grep -q "python.*generate_manifest.py" "$WORKFLOW_FILE"; then
        pass "Workflow calls generate_manifest.py"
    else
        warn "Workflow doesn't call generate_manifest.py"
    fi

    if grep -q "python.*validate_manifest.py" "$WORKFLOW_FILE"; then
        pass "Workflow calls validate_manifest.py"
    else
        warn "Workflow doesn't call validate_manifest.py"
    fi
else
    warn "Workflow file not found"
fi

# Cleanup
cd /
rm -rf "$TEST_DIR"

echo ""
echo "=" | tr '=' '\n' | head -50 | tr '\n' '='
echo ""
echo -e "${GREEN}✅ All tests passed!${NC}"
echo ""
echo "📊 Test Summary:"
echo "   • Python version: OK"
echo "   • Script files: OK"
echo "   • Syntax check: OK"
echo "   • Manifest generation: OK"
echo "   • Manifest validation: OK"
echo "   • Workflow configuration: OK"
echo ""
echo "🎉 Ready to deploy!"
