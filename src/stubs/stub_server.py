"""
Combined runner — starts all four upstream stubs on their respective ports.

Usage:
    python -m stubs.stub_server          (from the src/ directory)
    python src/stubs/stub_server.py      (from project root)

Ports:
    8081  WMS        (SYS-1)
    8082  TMS        (SYS-2)
    8083  Ticketing  (SYS-3)
    8084  Contracts  (SYS-4)
"""

from __future__ import annotations

import multiprocessing
import sys


def _run_wms() -> None:
    import uvicorn
    from stubs.wms_stub import app
    uvicorn.run(app, host="0.0.0.0", port=8081)


def _run_tms() -> None:
    import uvicorn
    from stubs.tms_stub import app
    uvicorn.run(app, host="0.0.0.0", port=8082)


def _run_ticketing() -> None:
    import uvicorn
    from stubs.ticketing_stub import app
    uvicorn.run(app, host="0.0.0.0", port=8083)


def _run_contracts() -> None:
    import uvicorn
    from stubs.contracts_stub import app
    uvicorn.run(app, host="0.0.0.0", port=8084)


def main() -> None:
    workers = [
        ("WMS      :8081", _run_wms),
        ("TMS      :8082", _run_tms),
        ("Ticketing:8083", _run_ticketing),
        ("Contracts:8084", _run_contracts),
    ]

    processes: list[multiprocessing.Process] = []
    for label, target in workers:
        p = multiprocessing.Process(target=target, name=label, daemon=True)
        p.start()
        print(f"[stub_server] Started {label}  pid={p.pid}")
        processes.append(p)

    print(f"[stub_server] All {len(processes)} stubs running.  Ctrl+C to stop.")

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\n[stub_server] Shutting down...")
        for p in processes:
            p.terminate()
        for p in processes:
            p.join(timeout=5)
        print("[stub_server] Done.")


if __name__ == "__main__":
    # Ensure src/ is on the path so `from stubs.…` imports work when
    # invoked directly as a script.
    import pathlib
    src_dir = str(pathlib.Path(__file__).resolve().parent.parent)
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    main()
