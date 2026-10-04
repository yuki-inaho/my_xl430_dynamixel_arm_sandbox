#!/usr/bin/env bash
# Explicit alternative binding; never silently substitutes for nanobind.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${AF_PYTHON:-$(command -v python)}"
COMMAND="${1:-test}"
if [[ $# -gt 0 ]]; then shift; fi
cd "$ROOT"
command -v uv >/dev/null || { echo 'uv が必要です。' >&2; exit 2; }
"$PYTHON" -c 'import numpy, scipy, cv2, trimesh, numba, PIL' || {
  echo '指定したPython環境に数値依存がありません。README.mdを参照してください。' >&2; exit 2;
}
printf '実行経路：明示C ABI（nanobindではありません）\n'
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DAF_BUILD_NANOBIND=OFF
cmake --build build -j "${AF_BUILD_JOBS:-2}"
export AF_BINDING=ctypes
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
case "$COMMAND" in
  test) uv run --no-project --python "$PYTHON" -m pytest tests -q "$@" ;;
  fit|render) uv run --no-project --python "$PYTHON" -m articulated_filterreg.cli "$COMMAND" --root "$ROOT" --binding ctypes "$@" ;;
  *) echo '使用法：scripts/run_capi.sh {test|fit|render} [引数]' >&2; exit 2 ;;
esac
