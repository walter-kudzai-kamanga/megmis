#!/usr/bin/env python3
"""Run Gen 1 + Gen 2 deep smokes sequentially (connected platform check)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_main(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main


def main() -> int:
    print("\n######## GEN 1 + GEN 2 CONNECTED DEEP SMOKE ########\n")
    failed = 0
    for name in ("gen1_deep_smoke.py", "gen2_deep_smoke.py"):
        path = ROOT / "scripts" / name
        print(f"\n--- running {name} ---\n")
        try:
            code = int(_load_main(path)() or 0)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"\n{name} CRASHED: {exc}\n")
            continue
        if code != 0:
            failed += 1
            print(f"\n{name} FAILED exit={code}\n")
        else:
            print(f"\n{name} OK\n")
    print(
        f"\n######## CONNECTED RESULT: "
        f"{'PASS' if failed == 0 else 'FAIL'} ({failed} script failures) ########\n"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
