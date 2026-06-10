"""
Reset the live demo back to its "before" state so the full integration act
(un-integrated -> onboard -> install -> uncomment -> it appears on the dashboard)
can be performed again for a fresh audience.

This is only needed when you want to REPLAY the live integration. For back-to-back
runs where you just re-run the already-integrated agent and show new records land on
the dashboard, you do NOT need this (run scripts/demo_check.py instead).

What it does (mirrors section C of local/DEMO_RUNSHEET.md):
  1. Re-comments the two integration blocks in northwind/backend/main.py
     (the import+client block, and the @audit.capture line above decide()).
  2. Clears AGENTAUDIT_API_KEY in northwind/backend/.env.
  3. Deletes the onboarded org(s) from the tenant store so the same company name
     can be onboarded again (create_org rejects a duplicate org_id).
  4. Asks whether to ALSO uninstall the SDK from Northwind's venv (so the live
     `pip install agentaudit-core` installs again). Default is to keep it.

It does NOT touch on-chain records (append-only) or resources — use demo_check.py
for funding/AACR. After this runs, restart Northwind's backend (:9000).

Usage:
  python scripts/reset_demo.py                       # interactive (asks about SDK uninstall)
  python scripts/reset_demo.py northwindco nwtest    # also reset these org_ids
  python scripts/reset_demo.py --uninstall-sdk       # non-interactive: do uninstall
  python scripts/reset_demo.py --keep-sdk            # non-interactive: keep the SDK
"""

import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tenancy.store import TenantStore  # noqa: E402

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
NORTHWIND_DIR = Path(os.getenv("NORTHWIND_DIR", REPO_ROOT.parent / "northwind"))
MAIN_PY = NORTHWIND_DIR / "backend" / "main.py"
ENV_FILE = NORTHWIND_DIR / "backend" / ".env"
VENV_PIP = NORTHWIND_DIR / "backend" / ".venv" / "bin" / "pip"

# Org ids cleared by default (the run sheet's set). Override by passing org ids as args.
DEFAULT_ORGS = ["northwindco", "northwind", "meditrust", "nwtest", "smoketest"]

# Active (uncommented) code lines that mark the integration. Re-commenting any line
# whose stripped form starts with one of these returns main.py to the "before" state.
INTEGRATION_PREFIXES = (
    "from agentaudit import AuditClient",
    "PROCUREMENT_AGENT =",
    "audit = AuditClient(",
    "@audit.capture(",
)


# ── Step 1: re-comment the integration in main.py ─────────────────────────────
def recomment_main_py() -> bool:
    """Comment out any active integration line in Northwind's main.py.

    Idempotent: already-commented lines are skipped. Writes a .bak alongside the
    file before changing it. Returns True if anything changed.
    """
    if not MAIN_PY.exists():
        print(f"  ! main.py not found at {MAIN_PY} — skipped")
        return False

    original = MAIN_PY.read_text()
    out_lines = []
    changed = 0
    for line in original.splitlines(keepends=True):
        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]
        is_active = not stripped.startswith("#") and any(
            stripped.startswith(p) for p in INTEGRATION_PREFIXES
        )
        if is_active:
            out_lines.append(f"{indent}# {stripped}")
            changed += 1
        else:
            out_lines.append(line)

    if changed == 0:
        print("  main.py already in the 'before' state (nothing to comment)")
        return False

    MAIN_PY.with_suffix(".py.bak").write_text(original)
    MAIN_PY.write_text("".join(out_lines))
    print(f"  re-commented {changed} integration line(s)  (backup: main.py.bak)")
    return True


# ── Step 2: clear the API key in .env ─────────────────────────────────────────
def clear_api_key() -> None:
    """Blank AGENTAUDIT_API_KEY in Northwind's .env (keeps the key name, drops the value)."""
    if not ENV_FILE.exists():
        print(f"  ! .env not found at {ENV_FILE} — skipped")
        return

    text = ENV_FILE.read_text()
    new_text, n = re.subn(
        r"^(AGENTAUDIT_API_KEY=).*$", r"\1", text, flags=re.MULTILINE
    )
    if n == 0:
        print("  no AGENTAUDIT_API_KEY line in .env — nothing to clear")
        return
    if new_text == text:
        print("  AGENTAUDIT_API_KEY already empty")
        return
    ENV_FILE.write_text(new_text)
    print("  cleared AGENTAUDIT_API_KEY")


# ── Step 3: delete onboarded org(s) from the tenant store ─────────────────────
def delete_orgs(org_ids: list[str]) -> None:
    """Remove the given org_ids (and their agents+rules) so names are free to re-onboard.

    Matches case-insensitively because the store keys org_ids verbatim (the demo
    onboards 'Northwindco' with a capital N) but delete_org is case-sensitive.
    """
    store = TenantStore()
    by_lower = {o["org_id"].lower(): o["org_id"] for o in store.list_orgs()}
    for org_id in org_ids:
        actual = by_lower.get(org_id.lower())
        if actual:
            store.delete_org(actual)
            print(f"  deleted org '{actual}'")
        else:
            print(f"  org '{org_id}' not present (ok)")


# ── Step 4: optionally uninstall the SDK from Northwind's venv ─────────────────
def want_uninstall() -> bool:
    """Resolve whether to uninstall the SDK: flags win, else ask interactively."""
    if "--uninstall-sdk" in sys.argv:
        return True
    if "--keep-sdk" in sys.argv:
        return False
    if not sys.stdin.isatty():
        print("  (non-interactive, no flag) keeping the SDK installed")
        return False
    ans = input(
        "  Also uninstall the SDK from Northwind's venv so the live "
        "`pip install` runs again? [y/N] "
    ).strip().lower()
    return ans in ("y", "yes")


def uninstall_sdk() -> None:
    """Uninstall agentaudit / agentaudit-core from Northwind's venv."""
    if not VENV_PIP.exists():
        print(f"  ! pip not found at {VENV_PIP} — skipped")
        return
    result = subprocess.run(
        [str(VENV_PIP), "uninstall", "-y", "agentaudit", "agentaudit-core"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("  uninstalled agentaudit / agentaudit-core from Northwind's venv")
    else:
        # pip exits non-zero if neither package is installed — that's fine here.
        print("  SDK not installed (or already removed) — nothing to uninstall")


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    flags = {"--uninstall-sdk", "--keep-sdk"}
    org_args = [a for a in sys.argv[1:] if a not in flags]
    org_ids = org_args or DEFAULT_ORGS

    print("Resetting Northwind demo to the 'before' state\n")

    print("1. main.py integration")
    recomment_main_py()

    print("\n2. .env API key")
    clear_api_key()

    print("\n3. tenant store org(s)")
    delete_orgs(org_ids)

    print("\n4. SDK in Northwind's venv")
    if want_uninstall():
        uninstall_sdk()
    else:
        print("  keeping the SDK installed")

    print("\nDone. Now restart Northwind's backend so it loads the reset main.py:")
    print("  cd /Users/omb/sanctum/northwind/backend && ./.venv/bin/uvicorn main:app --port 9000")
    print("\n(Run `python scripts/demo_check.py` if you also want to top up ALGO/AACR.)")


if __name__ == "__main__":
    main()
