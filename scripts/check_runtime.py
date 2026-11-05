"""Check the frontend, admin and API/database/Redis/migration readiness."""
import argparse
import json
from urllib.error import URLError
from urllib.request import urlopen


def check(frontend: str, admin: str) -> bool:
    ok = True
    for name, url in (("frontend", frontend + "/healthz"), ("admin", admin + "/healthz")):
        try:
            with urlopen(url, timeout=10) as response:
                assert response.status == 200 and response.read().strip() == b"ok"
            print(f"{name}=PASS")
        except (URLError, OSError, AssertionError):
            print(f"{name}=FAIL")
            ok = False
    try:
        with urlopen(frontend + "/api/v1/config/health", timeout=15) as response:
            data = json.load(response)["data"]
        for service in ("api", "database", "redis", "migrations"):
            passed = data.get("services", {}).get(service) == "up"
            print(f"{service}={'PASS' if passed else 'FAIL'}")
            ok = passed and ok
    except (URLError, OSError, ValueError, KeyError, TypeError):
        print("backend=FAIL (check compose logs app migrate postgres redis)")
        ok = False
    return ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend", default="http://127.0.0.1:8080")
    parser.add_argument("--admin", default="http://127.0.0.1:8081")
    args = parser.parse_args()
    raise SystemExit(0 if check(args.frontend.rstrip("/"), args.admin.rstrip("/")) else 1)
