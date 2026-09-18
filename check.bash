#!/usr/bin/env bash

set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

set -x

ruff format --check --exclude adobe-notdef --exclude last-resort-font .
ruff check --exclude adobe-notdef --exclude last-resort-font .
