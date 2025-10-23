#!/usr/bin/env bash
set -euo pipefail

DEST_ROOT="${1:-}"

if [[ -z "${DEST_ROOT}" ]]; then
    echo "Usage: $0 <destination-root>" >&2
    exit 1
fi

if ! DEST_ROOT="$(python3 -c 'import os, sys; print(os.path.abspath(sys.argv[1]))' -- "${DEST_ROOT}")"; then
    echo "Error: unable to resolve destination root" >&2
    exit 1
fi

case "${DEST_ROOT}" in
    /|/bin|/usr|/home|/etc|/var|/tmp|/sys|/proc|/dev|/opt|/sbin)
        echo "Error: DEST_ROOT cannot be a system directory: ${DEST_ROOT}" >&2
        exit 1
        ;;
esac

if [[ "${DEST_ROOT}" == "${HOME}" ]] || [[ "${DEST_ROOT}" == "$(pwd)" ]]; then
    echo "Error: refusing to operate on critical path: ${DEST_ROOT}" >&2
    exit 1
fi

rm -rf -- "${DEST_ROOT}"
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

while read -r remote; do
    git remote remove "${remote}" || true
done < <(git remote)

echo "${DEST_ROOT}" > "${DEST_ROOT}/.path"
