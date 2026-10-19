#!/bin/bash
# Modified 2026 by David Rusho; see CHANGES.md
set -e

# Optional: --multinode also creates the 3-node cluster World 7 runs on. Without it the
# engine creates that cluster the first time a World 7 level is started.
CREATE_MULTINODE=0
for arg in "$@"; do
  case "$arg" in
    --multinode) CREATE_MULTINODE=1 ;;
    -h|--help)
      echo "Usage: ./install.sh [--multinode]"
      echo "  --multinode  also create the 3-node kind cluster for World 7 now"
      echo "               (otherwise the game creates it on first entry to World 7)"
      exit 0 ;;
    *) echo "❌ Unknown option: $arg (try --help)"; exit 1 ;;
  esac
done

echo "🎮 K8sQuest Installation"
echo "========================"
echo ""

# Check prerequisites
command -v kind >/dev/null || { echo "❌ kind not found. Install with: brew install kind"; exit 1; }
command -v kubectl >/dev/null || { echo "❌ kubectl not found. Install with: brew install kubectl"; exit 1; }
command -v python3 >/dev/null || { echo "❌ python3 not found"; exit 1; }

# Verify Python version >= 3.9 (required for type hint syntax used in engine)
PYTHON_VERSION=$(python3 -c "import sys; v=sys.version_info; print(f'{v.major}.{v.minor}'); exit(0 if (v.major, v.minor) >= (3, 9) else 1)") || {
  echo "❌ Python 3.9+ required, but found $PYTHON_VERSION"
  echo "   Install a newer Python:"
  echo "   macOS:  brew install python@3.11"
  echo "   Linux:  sudo apt install python3.11"
  echo "   Then ensure 'python3' resolves to 3.9+ (update PATH or alternatives)"
  exit 1
}
echo "✅ Python $PYTHON_VERSION detected"

# kind v0.33.0 defaults to Kubernetes v1.37.0, the image kind/cluster.yaml pins.
# Warn on anything older rather than fail: the pinned image may still work there.
KIND_VERSION=$(kind version 2>/dev/null | sed -n 's/^kind v\([0-9][0-9.]*\).*/\1/p')
if [ -z "$KIND_VERSION" ]; then
  echo "⚠️  Could not determine kind version; K8sQuest expects kind >= v0.33.0"
elif [ "$(printf '%s\n' "0.33.0" "$KIND_VERSION" | sort -V | head -n 1)" != "0.33.0" ]; then
  echo "⚠️  kind v$KIND_VERSION detected; K8sQuest expects kind >= v0.33.0 (upgrade: brew upgrade kind)"
else
  echo "✅ kind v$KIND_VERSION detected"
fi

echo "✅ Prerequisites OK"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
  echo "🐍 Creating Python virtual environment..."
  python3 -m venv venv
  if [ ! -d "venv" ]; then
    echo "❌ Failed to create virtual environment"
    exit 1
  fi
fi

# Activate virtual environment and install dependencies
echo "📦 Installing Python dependencies..."
if [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
elif [ -f "venv/Scripts/activate" ]; then
  source venv/Scripts/activate
else
  echo "❌ Virtual environment activation script not found"
  echo "Expected: venv/bin/activate or venv/Scripts/activate"
  exit 1
fi
pip install -q -r requirements.txt

echo "✅ Python packages installed"
echo ""

# Create Kubernetes cluster
if ! kind get clusters | grep -qx k8squest; then
  echo "🔧 Creating Kubernetes cluster..."
  kind create cluster --name k8squest --config kind/cluster.yaml
else
  echo "✅ Cluster already exists"
fi


# World 7 runs on its own 3-node cluster, context kind-k8squest-multinode
if [ "$CREATE_MULTINODE" = 1 ]; then
  if ! kind get clusters | grep -qx k8squest-multinode; then
    echo "🔧 Creating the 3-node cluster for World 7..."
    kind create cluster --name k8squest-multinode --config kind/multinode.yaml --wait 180s
    kubectl --context kind-k8squest-multinode create namespace k8squest --dry-run=client -o yaml | kubectl --context kind-k8squest-multinode apply -f -
    [ -f rbac/k8squest-rbac.yaml ] && kubectl --context kind-k8squest-multinode apply -f rbac/k8squest-rbac.yaml
  else
    echo "✅ Multi-node cluster already exists"
  fi
fi

# The game cluster stays the current context; the engine switches to the multi-node one
# when a World 7 level starts, and back for the other worlds.
kubectl config use-context kind-k8squest

# Create k8squest namespace
echo "🏗️  Setting up k8squest namespace..."
kubectl create namespace k8squest --dry-run=client -o yaml | kubectl apply -f -

# Setup RBAC for safety
echo "🛡️  Configuring safety guards (RBAC)..."
if [ -f "rbac/k8squest-rbac.yaml" ]; then
  kubectl apply -f rbac/k8squest-rbac.yaml
  echo "✅ Safety guards configured"
else
  echo "⚠️  Warning: RBAC config not found, skipping"
fi

echo ""
echo "🚀 Setup Complete!"
echo ""
echo "To start playing, use the shortcut:"
echo "  ./play.sh"
echo ""
