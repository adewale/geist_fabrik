#!/usr/bin/env bash
# Compatibility wrapper: validate.sh is the single local/CI validation contract.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
exec "$ROOT/scripts/validate.sh"
