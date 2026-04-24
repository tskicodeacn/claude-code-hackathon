#!/usr/bin/env python3
"""
Cutover rehearsal -- Challenge 8 (The Weekend).

Simulates the cutover runbook steps against a real running instance of Album Catalog Service.
Proves the runbook is executable, not just theoretical.

Steps executed:
  1. Contract test suite (pytest) -- runbook STEP 1
  2. Start Album Catalog Service on port 8765 -- runbook STEP 2
  3. Health check (OpenAPI endpoint) -- runbook STEP 2
  4. Live smoke tests over real HTTP -- runbook STEP 3
  5. Fence check: no JPA/Java leakage in live responses
  6. Stop service and report GO/NO-GO

Usage:
  python cutover/rehearse.py
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import urllib.request
import urllib.error

REHEARSAL_PORT = 8765
BASE_URL = f"http://127.0.0.1:{REHEARSAL_PORT}"
SERVICE_DIR = Path(__file__).parent.parent / "album-catalog-service"
PROJECT_ROOT = Path(__file__).parent.parent

JPA_LEAK_MARKERS = ["@Entity", "@Column", "@Id", "@GenericGenerator", "_class",
                    "javax.persistence", "jakarta.persistence", "org.springframework"]

SAMPLE_ALBUM = {"title": "Kind of Blue", "artist": "Miles Davis",
                "releaseYear": "1959", "genre": "Jazz"}


def step(label: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")


def ok(msg: str) -> None:
    print(f"  [PASS] {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}", file=sys.stderr)


def http(method: str, path: str, body: dict | None = None) -> tuple[int, bytes]:
    url = BASE_URL + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except urllib.error.URLError as e:
        return 0, str(e).encode()


# ---------------------------------------------------------------------------
# STEP 1 -- Contract test suite
# ---------------------------------------------------------------------------
def step1_contract_tests() -> bool:
    step("STEP 1 -- Contract test suite (pytest)")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_contract.py", "-q", "--tb=short"],
        cwd=str(SERVICE_DIR),
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        passed = [l for l in result.stdout.splitlines() if "passed" in l]
        ok(passed[-1] if passed else "all tests passed")
        return True
    else:
        fail("Contract tests failed")
        print(result.stdout[-600:])
        return False


# ---------------------------------------------------------------------------
# STEP 2 -- Start service + health check
# ---------------------------------------------------------------------------
def step2_start_service() -> subprocess.Popen | None:
    step(f"STEP 2 -- Start Album Catalog Service on port {REHEARSAL_PORT}")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app",
         "--host", "127.0.0.1", "--port", str(REHEARSAL_PORT), "--log-level", "warning"],
        cwd=str(SERVICE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait up to 8 seconds for the service to start
    for attempt in range(16):
        time.sleep(0.5)
        status, _ = http("GET", "/openapi.json")
        if status == 200:
            ok(f"Service started (pid={proc.pid}), health check returned 200")
            return proc
        if proc.poll() is not None:
            fail(f"Service process exited early (code={proc.returncode})")
            err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            print(err[:400])
            return None

    fail(f"Service did not start within 8 seconds (last status={status})")
    proc.terminate()
    return None


# ---------------------------------------------------------------------------
# STEP 3 -- Live smoke tests
# ---------------------------------------------------------------------------
def step3_smoke_tests() -> bool:
    step("STEP 3 -- Live smoke tests over real HTTP")
    failures = []

    # GET /albums -> 200 + list
    status, body = http("GET", "/albums")
    if status == 200 and json.loads(body) == []:
        ok("GET /albums -> 200 []")
    else:
        fail(f"GET /albums -> {status} {body[:80]}")
        failures.append("GET /albums")

    # PUT /albums -> create album
    status, body = http("PUT", "/albums", SAMPLE_ALBUM)
    if status == 200:
        album = json.loads(body)
        album_id = album.get("id")
        ok(f"PUT /albums -> 200, id={album_id}")
    else:
        fail(f"PUT /albums -> {status}")
        return False

    # GET /albums/{id} -> 200
    status, body = http("GET", f"/albums/{album_id}")
    if status == 200 and json.loads(body)["id"] == album_id:
        ok(f"GET /albums/{album_id} -> 200")
    else:
        fail(f"GET /albums/{{id}} -> {status}")
        failures.append("GET /albums/{id}")

    # GET /albums/{nonexistent} -> 404 (contract fix vs monolith bug)
    status, _ = http("GET", "/albums/does-not-exist")
    if status == 404:
        ok("GET /albums/does-not-exist -> 404 (contract fix confirmed)")
    else:
        fail(f"GET /albums/does-not-exist -> {status} (expected 404)")
        failures.append("GET /albums/{nonexistent}")

    # DELETE -> 200 + empty body
    status, body = http("DELETE", f"/albums/{album_id}")
    if status == 200 and body == b"":
        ok(f"DELETE /albums/{album_id} -> 200 empty body")
    else:
        fail(f"DELETE -> {status} body={body[:40]!r}")
        failures.append("DELETE")

    # GET deleted -> 404
    status, _ = http("GET", f"/albums/{album_id}")
    if status == 404:
        ok("GET deleted album -> 404")
    else:
        fail(f"GET deleted album -> {status} (expected 404)")
        failures.append("GET deleted")

    return len(failures) == 0


# ---------------------------------------------------------------------------
# STEP 4 -- Fence check on live responses
# ---------------------------------------------------------------------------
def step4_fence_check() -> bool:
    step("STEP 4 -- Fence check (no JPA/Java leakage in live responses)")
    # Seed one album, check list response
    http("PUT", "/albums", SAMPLE_ALBUM)
    _, body = http("GET", "/albums")
    text = body.decode(errors="replace")

    violations = [m for m in JPA_LEAK_MARKERS if m in text]
    if violations:
        fail(f"JPA/Java leakage detected in /albums response: {violations}")
        return False

    ok(f"No leakage in /albums response (checked {len(JPA_LEAK_MARKERS)} markers)")
    return True


# ---------------------------------------------------------------------------
# Main rehearsal runner
# ---------------------------------------------------------------------------
def main() -> None:
    print()
    print("=" * 64)
    print("  Album Catalog Service -- Cutover Rehearsal")
    print("  Rehearsing runbook steps before the real 3am cutover")
    print("=" * 64)

    results: dict[str, bool] = {}
    proc = None

    try:
        results["contract_tests"] = step1_contract_tests()
        if not results["contract_tests"]:
            print("\n  ABORT: Contract tests must be green before cutover. Do not proceed.")
            sys.exit(1)

        proc = step2_start_service()
        if proc is None:
            print("\n  ABORT: Service failed to start.")
            sys.exit(1)
        results["service_start"] = True

        results["smoke_tests"] = step3_smoke_tests()
        results["fence_check"] = step4_fence_check()

    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)
            print(f"\n  Service stopped (pid={proc.pid})")

    # Summary
    step("REHEARSAL SUMMARY")
    all_pass = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
        if not passed:
            all_pass = False

    print()
    if all_pass:
        print("  GO -- Rehearsal passed. Runbook is executable.")
        print("  Safe to proceed with real cutover during maintenance window.")
    else:
        print("  NO-GO -- Rehearsal failed. Fix issues before real cutover.")
        sys.exit(1)
    print()


if __name__ == "__main__":
    main()
