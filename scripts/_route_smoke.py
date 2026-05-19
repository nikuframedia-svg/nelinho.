"""Sprint Q.7 Fase 3 — per-route smoke tester for one module.

For each route registered under /v1/{module}/* hits the endpoint with
minimum-viable inputs and reports HTTP status. Without a live DB most
endpoints return 503; the goal is to catch endpoints that crash with
500 (real bug) vs. cleanly return 4xx/503 (graceful)."""
import os
import sys
import logging
from uuid import uuid4

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

logging.disable(logging.CRITICAL)

from fastapi.testclient import TestClient
from src.main import app


def main(module: str = "plan") -> int:
    client = TestClient(app)
    headers = {"X-Tenant-Id": str(uuid4())}

    crashes: list[tuple[str, str, int, str]] = []
    ok: list[tuple[str, str, int]] = []

    for r in app.routes:
        if not hasattr(r, "methods") or not hasattr(r, "path"):
            continue
        path = r.path
        if not (f"/{module}/" in path or path.startswith(f"/v1/{module}")):
            continue
        for method in sorted(r.methods):
            if method == "HEAD":
                continue

            # Resolve path params with placeholders (keep route patterns)
            test_path = path
            placeholders = {
                "{tenant_id}": str(uuid4()),
                "{schedule_id}": str(uuid4()),
                "{order_id}": str(uuid4()),
                "{batch_id}": str(uuid4()),
                "{employee_id}": str(uuid4()),
                "{machine_id}": str(uuid4()),
                "{mold_id}": str(uuid4()),
                "{planning_run_id}": str(uuid4()),
                "{mrp_run_id}": str(uuid4()),
                "{sha}": "abcdef1234567890",
                "{from_sha}": "abcdef1234567890",
                "{to_sha}": "0987654321fedcba",
                "{phase_id}": "LAMINAGEM",
            }
            for k, v in placeholders.items():
                test_path = test_path.replace(k, v)

            try:
                if method == "GET":
                    resp = client.get(test_path, headers=headers)
                elif method == "POST":
                    # Try empty body — most routes will 422; that's fine.
                    resp = client.post(test_path, headers=headers, json={})
                elif method == "PUT":
                    resp = client.put(test_path, headers=headers, json={})
                elif method == "PATCH":
                    resp = client.patch(test_path, headers=headers, json={})
                elif method == "DELETE":
                    resp = client.delete(test_path, headers=headers)
                else:
                    continue

                status = resp.status_code
                # Real crashes: 5xx other than 503 (DB unavailable). 503 is graceful.
                if status >= 500 and status != 503:
                    body_snip = resp.text[:200] if resp.text else ""
                    crashes.append((method, path, status, body_snip))
                else:
                    ok.append((method, path, status))
            except Exception as e:
                crashes.append((method, path, -1, f"client crash: {type(e).__name__}: {e}"))

    print(f"=== Route smoke: /{module}/* ({len(ok) + len(crashes)} routes) ===\n")
    print(f"OK / graceful: {len(ok)}")
    print(f"500-class crashes: {len(crashes)}")
    if crashes:
        print()
        print("CRASHES:")
        for method, path, status, snip in crashes:
            print(f"  {method:6} {path:60}  HTTP {status}")
            if snip:
                print(f"         {snip[:180]}")
    print()
    print("Status distribution among OK routes:")
    counts: dict[int, int] = {}
    for _, _, s in ok:
        counts[s] = counts.get(s, 0) + 1
    for s in sorted(counts):
        print(f"  {s}: {counts[s]}")
    return 1 if crashes else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "plan"))
