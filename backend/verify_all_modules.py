import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
checks = [
    ("Core academic APIs and access control", "verify_phase2.py"),
    ("Dynamic QR attendance", "verify_phase4.py"),
    ("RAG assistant, insights, and recommendations", "verify_phase5.py"),
    ("Production configuration and health security", "verify_phase6.py"),
]


def main():
    print("\n=======================================================")
    print("   SMART CURRICULUM & ATTENDANCE - SAFE VERIFICATION")
    print("=======================================================\n")

    passed = 0
    failed = 0

    for name, script in checks:
        print(f"--> Running {name} ({script})...", flush=True)
        res = subprocess.run(
            [sys.executable, str(BACKEND_DIR / script)],
            cwd=BACKEND_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            print(res.stdout.rstrip(), flush=True)
            if res.stderr.strip():
                print(res.stderr.rstrip(), file=sys.stderr, flush=True)
            print(f"    [PASS] {name} passed successfully!\n", flush=True)
            passed += 1
        else:
            print(f"    [FAIL] {name} failed with exit code {res.returncode}", flush=True)
            if res.stdout:
                print(res.stdout, flush=True)
            if res.stderr:
                print(res.stderr, file=sys.stderr, flush=True)
            failed += 1

    print("=======================================================")
    print(f" SUMMARY: {passed}/{len(checks)} Isolated Suites Passed ({failed} Failed)")
    print("=======================================================\n")

    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
