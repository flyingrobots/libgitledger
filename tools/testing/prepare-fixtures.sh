#!/usr/bin/env bash
set -euo pipefail

DEST_ROOT="${1:-}"

if [[ -z "${DEST_ROOT}" ]]; then
    echo "Usage: $0 <destination-root>" >&2
    exit 1
fi

rm -rf "${DEST_ROOT}"
mkdir -p "${DEST_ROOT}"

FIXTURE_REPO="${DEST_ROOT}/ledger-fixture"

mkdir -p "${FIXTURE_REPO}"
cd "${FIXTURE_REPO}"

git init -q
git config --local user.name "libgitledger-fixture"
git config --local user.email "fixture@example.com"
echo "fixture" > README.md
git add README.md
git commit -q -m "Bootstrap fixture repo"

git config --local --unset-all remote.origin.url >/dev/null 2>&1 || true
git config --local --unset-all remote.origin.pushurl >/dev/null 2>&1 || true

while read -r remote; do
    git remote remove "${remote}" || true
done < <(git remote)

echo "${DEST_ROOT}" > "${DEST_ROOT}/.path"
