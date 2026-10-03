#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
swiftc -O -target arm64-apple-macos13 helper/main.swift -o bin/speak-helper
