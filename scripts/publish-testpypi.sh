#!/usr/bin/env bash
# Build, publish, and record a Gradipin release on TestPyPI.
#
# Pre-flight: refuses to upload a version that already exists on TestPyPI or
# that already has a matching git tag (immutable on both sides). On success,
# commits any pending changes, tags v$VERSION, and pushes branch + tag.
#
# Loads TWINE_USERNAME / TWINE_PASSWORD from .env at the repo root.

set -euo pipefail

cd "$(dirname "$0")/.."

# ---------------------------------------------------------------------------
# Load secrets from .env
# ---------------------------------------------------------------------------
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

VERSION="$("$PY" -c 'import tomllib;print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')"
TAG="v${VERSION}"
PROJECT_URL="https://test.pypi.org/project/gradipin/${VERSION}/"

echo "==> Publishing gradipin v${VERSION} to TestPyPI"

# ---------------------------------------------------------------------------
# Pre-flight: don't try to publish a duplicate version
# ---------------------------------------------------------------------------
echo "==> Checking that v${VERSION} is fresh"

HTTP_CODE="$(curl -s -o /dev/null -w '%{http_code}' "$PROJECT_URL" || echo "000")"
if [[ "$HTTP_CODE" == "200" ]]; then
  echo "error: gradipin v${VERSION} already exists on TestPyPI (HTTP 200 at $PROJECT_URL)." >&2
  echo "       PyPI versions are immutable. Bump 'version' in pyproject.toml and try again." >&2
  exit 1
fi

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "error: git tag $TAG already exists locally." >&2
  echo "       Bump 'version' in pyproject.toml and try again." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Build + validate + upload
# ---------------------------------------------------------------------------
echo "==> Cleaning dist/"
rm -rf dist/

echo "==> Building"
"$PY" -m build

echo "==> Validating metadata"
"$TWINE" check dist/*

echo "==> Uploading to TestPyPI"
"$TWINE" upload --repository testpypi dist/*

# ---------------------------------------------------------------------------
# Past this point, the release is immutable on TestPyPI. Make git match.
# Failures from here on are warnings, not hard errors — the publish stands.
# ---------------------------------------------------------------------------
echo "==> Recording release in git"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "  ...staging and committing local changes"
  git add -A
  git commit -m "release: gradipin v${VERSION}"
else
  echo "  ...working tree already clean"
fi

echo "  ...tagging $TAG"
git tag -a "$TAG" -m "gradipin v${VERSION}"

if git remote get-url origin >/dev/null 2>&1; then
  echo "  ...pushing branch + tag to origin"
  git push origin HEAD || \
    echo "warning: 'git push origin HEAD' failed. Release is on TestPyPI; push manually." >&2
  git push origin "$TAG" || \
    echo "warning: 'git push origin $TAG' failed. Release is on TestPyPI; push the tag manually." >&2
else
  echo "  ...no 'origin' remote configured; skipping push"
fi

echo
echo "Done. View at: $PROJECT_URL"
