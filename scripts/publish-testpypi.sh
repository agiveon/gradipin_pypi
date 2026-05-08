#!/usr/bin/env bash
# Build and publish the package to TestPyPI.
# Loads TWINE_USERNAME / TWINE_PASSWORD from .env at the repo root.

set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "error: .env not found at repo root." >&2
  echo "       Copy .env.example to .env and fill in your TestPyPI token." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

if [[ -z "${TWINE_USERNAME:-}" || -z "${TWINE_PASSWORD:-}" ]]; then
  echo "error: TWINE_USERNAME or TWINE_PASSWORD missing from .env" >&2
  exit 1
fi

PY="${PY:-.venv/bin/python}"
TWINE="${TWINE:-.venv/bin/twine}"

if [[ ! -x "$PY" ]]; then
  echo "error: $PY not found. Activate or build the .venv first." >&2
  exit 1
fi

VERSION="$("$PY" -c 'import tomllib,sys;print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')"
echo "==> Publishing gradipin v${VERSION} to TestPyPI"

echo "==> Cleaning dist/"
rm -rf dist/

echo "==> Building"
"$PY" -m build

echo "==> Validating metadata"
"$TWINE" check dist/*

echo "==> Uploading to TestPyPI"
"$TWINE" upload --repository testpypi dist/*

echo
echo "Done. View at: https://test.pypi.org/project/gradipin/${VERSION}/"
