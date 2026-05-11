#!/usr/bin/env bash
# Build, publish, and record a Gradipin release on the *real* PyPI.
#
# Mirrors publish-testpypi.sh but for production. Differences:
#   - Reads TWINE_USERNAME_PYPI / TWINE_PASSWORD_PYPI from .env (so the
#     TestPyPI token can stay in TWINE_USERNAME / TWINE_PASSWORD without
#     conflict).
#   - Uploads to https://upload.pypi.org/legacy/ (twine's default).
#   - Requires you to type "yes" before uploading. Real PyPI versions are
#     immutable, public, and visible to every Python developer in the world;
#     the friction is intentional.
#
# Pre-flight: refuses to upload a version that already exists on PyPI. After a
# successful upload, commits any pending changes, tags v$VERSION (if not
# already tagged), and pushes branch + tag.

set -euo pipefail

cd "$(dirname "$0")/.."

# ---------------------------------------------------------------------------
# Load secrets from .env
# ---------------------------------------------------------------------------
if [[ ! -f .env ]]; then
  echo "error: .env not found at repo root." >&2
  echo "       Copy .env.example to .env and fill in your PyPI token." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

if [[ -z "${TWINE_USERNAME_PYPI:-}" || -z "${TWINE_PASSWORD_PYPI:-}" ]]; then
  echo "error: TWINE_USERNAME_PYPI or TWINE_PASSWORD_PYPI missing from .env" >&2
  echo "       Get a token at https://pypi.org/manage/account/token/ and add" >&2
  echo "       both vars to .env (see .env.example)." >&2
  exit 1
fi

# Twine reads TWINE_USERNAME / TWINE_PASSWORD from the environment. Override
# them locally with the production credentials so we don't accidentally use
# the TestPyPI ones.
export TWINE_USERNAME="$TWINE_USERNAME_PYPI"
export TWINE_PASSWORD="$TWINE_PASSWORD_PYPI"

PY="${PY:-.venv/bin/python}"
TWINE="${TWINE:-.venv/bin/twine}"

if [[ ! -x "$PY" ]]; then
  echo "error: $PY not found. Activate or build the .venv first." >&2
  exit 1
fi

VERSION="$("$PY" -c 'import tomllib;print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')"
TAG="v${VERSION}"
PROJECT_URL="https://pypi.org/project/gradipin/${VERSION}/"
EXISTS_API="https://pypi.org/pypi/gradipin/${VERSION}/json"

echo "==> Publishing gradipin v${VERSION} to PRODUCTION PyPI"

# ---------------------------------------------------------------------------
# Pre-flight: don't try to publish a duplicate version
# ---------------------------------------------------------------------------
echo "==> Checking that v${VERSION} is fresh"

HTTP_CODE="$(curl -s -o /dev/null -w '%{http_code}' "$EXISTS_API" || echo "000")"
if [[ "$HTTP_CODE" == "200" ]]; then
  echo "error: gradipin v${VERSION} already exists on PyPI ($PROJECT_URL)." >&2
  echo "       PyPI versions are immutable. Bump 'version' in pyproject.toml and try again." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Confirmation prompt — real PyPI is forever
# ---------------------------------------------------------------------------
echo
echo "  *** You are about to publish gradipin v${VERSION} to the *real* PyPI. ***"
echo "  *** This is public, permanent, and visible to every Python user.    ***"
echo "  *** TestPyPI is the staging environment; this is production.        ***"
echo
read -r -p "  Type 'yes' to continue: " CONFIRM
if [[ "$CONFIRM" != "yes" ]]; then
  echo "Aborted."
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

echo "==> Uploading to PyPI"
# No --repository flag: twine's default is upload.pypi.org/legacy/.
"$TWINE" upload dist/*

# ---------------------------------------------------------------------------
# Past this point the release is immutable on PyPI. Make git match.
# ---------------------------------------------------------------------------
echo "==> Recording release in git"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "  ...staging and committing local changes"
  git add -A
  git commit -m "release: gradipin v${VERSION} (PyPI)"
else
  echo "  ...working tree already clean"
fi

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "  ...tag $TAG already exists, leaving it alone"
else
  echo "  ...tagging $TAG"
  git tag -a "$TAG" -m "gradipin v${VERSION}"
fi

if git remote get-url origin >/dev/null 2>&1; then
  echo "  ...pushing branch + tag to origin"
  git push origin HEAD || \
    echo "warning: 'git push origin HEAD' failed. Release is on PyPI; push manually." >&2
  git push origin "$TAG" || \
    echo "warning: 'git push origin $TAG' failed. Release is on PyPI; push the tag manually." >&2
else
  echo "  ...no 'origin' remote configured; skipping push"
fi

echo
echo "Done. View at: $PROJECT_URL"
echo "Install with:  pip install gradipin==${VERSION}"
