#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/sites/silverev"

RU_SRC="$ROOT/dist/ru"
EN_SRC="$ROOT/dist/en"

echo "==> Checking build directories"

test -f "$RU_SRC/index.html" || {
    echo "ERROR: $RU_SRC/index.html not found"
    exit 1
}

test -f "$EN_SRC/index.html" || {
    echo "ERROR: $EN_SRC/index.html not found"
    exit 1
}

echo
echo "==> Publishing silverev.ru"
rclone sync \
    "$RU_SRC/" \
    "silverev-ru:" \
    --progress \
    --delete-after

echo
echo "==> Publishing silverev.org"
rclone sync \
    "$EN_SRC/" \
    "silverev-en:" \
    --progress \
    --delete-after \
    --exclude "cgi-bin/**"

echo
echo "==> Publish complete"
