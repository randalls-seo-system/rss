#!/usr/bin/env bash
# RSS pipeline environment setup.
# Run once after cloning or in a fresh venv:
#   bash tools/setup-env.sh
#
# Installs Python dependencies and downloads NLTK data packages
# required by the corpus linker (lib/linker_core.py).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== Installing Python dependencies ==="
pip install -r "$REPO_ROOT/requirements.txt"

echo ""
echo "=== Downloading NLTK data ==="
python3 -c "
import nltk
nltk.download('averaged_perceptron_tagger_eng', quiet=False)
nltk.download('punkt_tab', quiet=False)
print('NLTK data download complete.')
"

echo ""
echo "=== Setup complete ==="
echo "Run tests with: python3 -m pytest modules/content-production-v2/tools/tests/ -q"
