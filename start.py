#!/usr/bin/env python3
# Launcher for the compiled main module.
import sys
import traceback

try:
    import _secure_main
    _secure_main.main_menu()
except KeyboardInterrupt:
    print("\n  interrupted")
    sys.exit(0)
except Exception as exc:
    print(f"\n  Fatal error: {exc}")
    traceback.print_exc()
    sys.exit(1)
