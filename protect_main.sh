#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

echo
echo "=============================================="
echo "  ANURAG SINGH - MAIN.PY NATIVE PROTECTION"
echo "=============================================="

if [ ! -f "main.py" ]; then
  echo "[ERROR] main.py nahi mila."
  echo "Is script ko main.py, core.py aur match.py wale folder me rakho."
  exit 1
fi

if [ ! -f "core.py" ] || [ ! -f "match.py" ]; then
  echo "[WARNING] core.py ya match.py nahi mila. Runtime par required hoga."
fi

if command -v pkg >/dev/null 2>&1; then
  pkg install -y clang make python >/dev/null
fi

echo "[1/4] Cython aur build tools install ho rahe hain..."
python -m pip install --upgrade setuptools wheel Cython

echo "[2/4] Native extension build ho raha hai..."
cat > ._build_main_protection.py <<'PYBUILD'
from setuptools import setup, Extension
from Cython.Build import cythonize

setup(
    name="anurag_secure_main",
    ext_modules=cythonize(
        [Extension("_secure_main", ["main.py"])],
        compiler_directives={"language_level": 3},
        quiet=True,
    ),
)
PYBUILD

python ._build_main_protection.py build_ext --inplace

echo "[3/4] Compiled module verify ho raha hai..."
python - <<'PYTEST'
import _secure_main
assert callable(getattr(_secure_main, "main_menu", None)), \
    "Compiled module me main_menu() nahi mila"
print("[OK] Native module load aur main_menu() verify ho gaya.")
PYTEST

echo "[4/4] Source cleanup..."
rm -f main.py main.c ._build_main_protection.py
rm -rf build

echo
echo "[SUCCESS] main.py source ab remove kar diya gaya hai."
echo "Run command: python start.py"
echo "IMPORTANT: core.py aur match.py ko isi folder me rehne do."
echo "Compiled .so file ko delete/move mat karna."
