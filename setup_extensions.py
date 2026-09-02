#!/usr/bin/env python3
"""Script de déploiement des extensions Presence SaaS."""
from __future__ import annotations
import os, subprocess, sys, time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
BACKEND_DIR  = PROJECT_ROOT / "backend"
G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[94m"; E = "\033[0m"; BO = "\033[1m"

def log(m, c=G):   print(f"{c}{BO}[OK]{E} {m}")
def warn(m):        print(f"{Y}{BO}[WARN]{E} {m}")
def error(m):       print(f"{R}{BO}[ERR]{E} {m}")
def step(t):        print(f"\n{B}{BO}{'─'*55}\n  {t}\n{'─'*55}{E}")

def run(cmd, cwd=None, check=True, capture=False, env=None):
    cwd = cwd or PROJECT_ROOT
    ev  = {**os.environ, **(env or {})}
    r   = subprocess.run(cmd, cwd=str(cwd), check=False,
                         capture_output=capture, text=True, env=ev)
    if check and r.returncode != 0:
        error(f"Failed: {' '.join(cmd)}")
        if capture: print(r.stdout); print(r.stderr)
        sys.exit(1)
    return r

def find_python():
    for c in ["python3", "python", sys.executable]:
        try:
            r = subprocess.run([c,"--version"], capture_output=True, text=True, check=False)
            if r.returncode==0 and "Python 3" in (r.stdout+r.stderr):
                return c
        except FileNotFoundError:
            pass
    return sys.executable

def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    log(f"  {path.relative_to(PROJECT_ROOT)}")

def touch(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists(): path.write_text("")

def main():
    if not BACKEND_DIR.exists():
        error(f"Backend not found: {BACKEND_DIR}")
        sys.exit(1)

    scripts_dir = PROJECT_ROOT / "_ext_scripts"
    scripts_dir.mkdir(exist_ok=True)

    step("PHASE 1 — Structure")
    for d in [
        BACKEND_DIR/"seo"/"tests",
        BACKEND_DIR/"social"/"providers",
        BACKEND_DIR/"social"/"tests",
        BACKEND_DIR/"advanced_security"/"tests",
    ]:
        d.mkdir(parents=True, exist_ok=True)
        touch(d/"__init__.py")
        touch(d.parent/"__init__.py")
    log("Dirs created")

    step("PHASE 2 — Writing files")
    py = find_python()
    ev = {"DJANGO_SETTINGS_MODULE":"config.settings.development","PYTHONPATH":str(BACKEND_DIR)}

    for script in sorted((PROJECT_ROOT/"_ext_scripts").glob("write_*.py")):
        log(f"Running {script.name}…", B)
        r = run([py, str(script)], cwd=PROJECT_ROOT, check=False, capture=True)
        if r.returncode == 0:
            log(f"  {script.name} OK")
        else:
            warn(f"  {script.name} WARN:\n{r.stderr[-500:]}")

    step("PHASE 3 — Migrations")
    for app in ("seo","social","advanced_security"):
        r = run([py,"manage.py","makemigrations",app,"--no-input"],
                cwd=BACKEND_DIR, env=ev, check=False, capture=True)
        if r.returncode==0: log(f"  migrations {app} OK"); print(r.stdout.strip())
        else: warn(f"  {app}: {r.stderr[-300:]}")
    r = run([py,"manage.py","migrate","--no-input"],
            cwd=BACKEND_DIR, env=ev, check=False, capture=True)
    if r.returncode==0: log("  migrate OK")
    else: warn(r.stderr[-300:])

    step("PHASE 4 — Tests")
    suites = [("SEO","seo.tests.test_seo"),
              ("Social","social.tests.test_social"),
              ("Security","advanced_security.tests.test_security_audit")]
    results = {}
    for name, module in suites:
        r = run([py,"manage.py","test",module,"--verbosity=1","--no-input"],
                cwd=BACKEND_DIR, env=ev, check=False, capture=True)
        ok = r.returncode==0
        results[name] = ok
        if ok: log(f"  PASS: {name}")
        else:  warn(f"  FAIL: {name}\n{r.stdout[-2000:]}\n{r.stderr[-500:]}")

    step("PHASE 5 — Docker")
    cf = PROJECT_ROOT/"docker-compose.yml"
    if not cf.exists(): cf = PROJECT_ROOT/"docker-compose.yaml"
    if cf.exists() and run(["docker","info"],check=False,capture=True).returncode==0:
        dcmd = ["docker","compose"] if run(["docker","compose","version"],check=False,capture=True).returncode==0 else ["docker-compose"]
        run([*dcmd,"stop","django","celery-worker","celery-beat"],check=False)
        r = run([*dcmd,"build","--no-cache","django"],check=False,capture=True)
        if r.returncode==0: log("  Image rebuilt")
        else: warn("  Build failed\n"+r.stderr[-500:])
        run([*dcmd,"run","--rm","django","python","manage.py","migrate","--no-input"],check=False)
        run([*dcmd,"up","-d","django","celery-worker","celery-beat"],check=False)
        time.sleep(3)
        run([*dcmd,"ps"],check=False)
    else:
        warn("Docker not available — manual steps:")
        print("  docker compose build --no-cache django")
        print("  docker compose run --rm django python manage.py migrate --no-input")
        print("  docker compose up -d django celery-worker celery-beat")

    step("PHASE 6 — Summary")
    for name,ok in results.items():
        print(f"  [{'OK  ' if ok else 'FAIL'}] {name}")
    print("""
  Endpoints added:
    /api/v1/seo/*
    /api/v1/social/*
    /api/v1/security/*
    /api/v1/reviews/bulk-import/
    /api/v1/reviews/sentiment/
  Docs: http://localhost:8000/api/docs/
""")

if __name__ == "__main__":
    main()
