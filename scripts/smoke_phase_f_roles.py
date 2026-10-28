#!/usr/bin/env python3
"""Live Phase F smoke test against the local Presence API.

Exercises the tenant roles over real HTTP (no Django test client):

* owner: organization listing, member list, invitation creation;
* viewer: read access, denied write/invite management;
* outsider: organization endpoints answer 404 (no tenant probing);
* invitation: raw token returned once, only its SHA-256 digest is stored;
* optional: queue a real ``security`` scan (ZAP + Nuclei sandbox).

Usage::

    python3 scripts/smoke_phase_f_roles.py \
        --base-url https://localhost/api/v1 \
        --scan

The script prints one JSON document and exits non-zero when an assertion
fails.  It never prints access tokens.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from urllib.parse import parse_qs, urlparse

import requests

OWNER = "phasef.smoke.owner@presence.local"
VIEWER = "phasef.smoke.viewer@presence.local"
OUTSIDER = "phasef.smoke.outsider@presence.local"
PERSONAL = "test@test.com"
PASSWORD = os.environ.get("SMOKE_PASSWORD", "PhaseF-Live-2026!")


class SmokeFailure(AssertionError):
    pass


def expect(response: requests.Response, expected: int, label: str) -> requests.Response:
    if response.status_code != expected:
        raise SmokeFailure(
            f"{label}: expected HTTP {expected}, got {response.status_code}: "
            f"{response.text[:500]}"
        )
    return response


def login(session: requests.Session, base: str, email: str) -> str:
    response = expect(
        session.post(f"{base}/auth/login/", json={"email": email, "password": PASSWORD}),
        200,
        f"login {email}",
    )
    return response.json()["access"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def rows(response: requests.Response) -> list[dict]:
    """Return a DRF list payload, paginated or not."""
    payload = response.json()
    return payload["results"] if isinstance(payload, dict) else payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://localhost/api/v1")
    parser.add_argument(
        "--scan",
        action="store_true",
        help="queue a real security scan and wait for it to complete",
    )
    parser.add_argument("--scan-timeout", type=int, default=600)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    session = requests.Session()
    session.verify = False
    requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]

    report: dict = {"base_url": base, "checks": []}

    def check(name: str, detail: object) -> None:
        report["checks"].append({"check": name, "ok": True, "detail": detail})

    owner_token = login(session, base, OWNER)
    viewer_token = login(session, base, VIEWER)
    outsider_token = login(session, base, OUTSIDER)
    personal_token = login(session, base, PERSONAL)
    check("login_four_roles", [OWNER, VIEWER, OUTSIDER, PERSONAL])

    personal_orgs = rows(expect(
        session.get(f"{base}/organizations/", headers=auth(personal_token)),
        200,
        "personal organizations",
    ))
    personal_org = next(
        (item for item in personal_orgs if item["is_personal"]), None
    )
    if personal_org is None or personal_org["role"] != "owner":
        raise SmokeFailure(
            f"no personal organization for {PERSONAL}: {personal_orgs}"
        )
    report["personal_organization"] = {
        "email": PERSONAL,
        "id": personal_org["id"],
        "name": personal_org["name"],
        "role": personal_org["role"],
        "member_count": personal_org["member_count"],
    }
    check("personal_organization_listed", report["personal_organization"])

    owner_orgs = rows(expect(
        session.get(f"{base}/organizations/", headers=auth(owner_token)),
        200,
        "owner organizations",
    ))
    org = next((item for item in owner_orgs if item["role"] == "owner"), None)
    if org is None:
        raise SmokeFailure(f"owner organization listing unexpected: {owner_orgs}")
    report["organization"] = {
        "id": org["id"],
        "name": org["name"],
        "is_personal": org["is_personal"],
        "role": org["role"],
        "member_count": org["member_count"],
    }
    check("owner_team_organization", report["organization"])

    owner_members = rows(expect(
        session.get(
            f"{base}/organizations/{org['id']}/members/",
            headers=auth(owner_token),
        ),
        200,
        "owner member list",
    ))
    report["members_before"] = [
        {"email": item["email"], "role": item["role"]} for item in owner_members
    ]
    check("owner_member_list", len(owner_members))

    invitee_email = f"phasef.smoke.live.{int(time.time())}@presence.local"
    invitation = expect(
        session.post(
            f"{base}/organizations/{org['id']}/members/",
            headers=auth(owner_token),
            json={"email": invitee_email, "role": "viewer"},
        ),
        202,
        "owner creates invitation",
    ).json()
    accept_url = invitation.get("accept_url", "")
    token = parse_qs(urlparse(accept_url).query).get("token", [""])[0]
    if not token:
        raise SmokeFailure(f"invitation response has no token: {invitation}")
    report["invitation"] = {
        "id": invitation["invitation"]["id"],
        "email": invitation["email"],
        "role": invitation["invitation"]["role"],
        "status": invitation["invitation"]["status"],
        "email_sent": invitation["email_sent"],
        "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
    }
    check("owner_creates_invitation", report["invitation"])

    viewer_orgs = rows(expect(
        session.get(f"{base}/organizations/", headers=auth(viewer_token)),
        200,
        "viewer organizations",
    ))
    match = next((item for item in viewer_orgs if item["id"] == org["id"]), None)
    if match is None or match["role"] != "viewer":
        raise SmokeFailure(f"viewer role missing from organization listing: {viewer_orgs}")
    check("viewer_sees_organization", {"role": match["role"]})

    expect(
        session.get(
            f"{base}/organizations/{org['id']}/invitations/",
            headers=auth(viewer_token),
        ),
        403,
        "viewer invitation list denied",
    )
    check("viewer_cannot_manage_invitations", 403)

    expect(
        session.post(
            f"{base}/websites/",
            headers=auth(viewer_token),
            json={"domain": "phasef-viewer-denied.com", "organization_id": org["id"]},
        ),
        403,
        "viewer website creation denied",
    )
    check("viewer_cannot_create_website", 403)

    expect(
        session.get(
            f"{base}/organizations/{org['id']}/members/",
            headers=auth(outsider_token),
        ),
        404,
        "outsider organization probe hidden",
    )
    check("outsider_gets_404", 404)

    register = session.post(
        f"{base}/auth/register/",
        json={
            "email": invitee_email,
            "full_name": "Phase F Live Invitee",
            "password": PASSWORD,
        },
    )
    expect(register, 201, "invitee registration")
    invitee_token = login(session, base, invitee_email)
    accepted = expect(
        session.post(
            f"{base}/organizations/invitations/{token}/accept/",
            headers=auth(invitee_token),
        ),
        200,
        "invitee accepts invitation",
    ).json()
    if accepted["role"] != "viewer":
        raise SmokeFailure(f"invitee role unexpected: {accepted}")
    report["invitation_acceptance"] = {
        "membership_id": accepted["id"],
        "email": accepted["email"],
        "role": accepted["role"],
    }
    check("invitee_accepts_invitation", report["invitation_acceptance"])

    # Accepting twice is idempotent: the same membership is returned and no
    # duplicate row is created.
    reused = expect(
        session.post(
            f"{base}/organizations/invitations/{token}/accept/",
            headers=auth(invitee_token),
        ),
        200,
        "invitation acceptance is idempotent",
    ).json()
    if reused["id"] != accepted["id"]:
        raise SmokeFailure(f"duplicate membership created: {reused}")
    check("invitation_acceptance_idempotent", reused["id"])

    if args.scan:
        websites = rows(expect(
            session.get(f"{base}/websites/", headers=auth(owner_token)),
            200,
            "owner website list",
        ))
        website = next(
            (item for item in websites if item["domain"] == "example.com"), None
        )
        if website is None:
            raise SmokeFailure("owner has no example.com website to scan")

        active = session.get(
            f"{base}/websites/{website['id']}/active_scan/",
            headers=auth(owner_token),
        )
        if active.status_code == 200:
            raise SmokeFailure(f"a scan is already active: {active.text[:300]}")

        queued = expect(
            session.post(
                f"{base}/websites/{website['id']}/scan/",
                headers=auth(owner_token),
                json={"scan_type": "security"},
            ),
            202,
            "queue security scan",
        ).json()
        scan_id = queued["id"]
        report["scan"] = {"id": scan_id, "status": queued["status"], "type": "security"}
        check("security_scan_queued", scan_id)

        deadline = time.monotonic() + args.scan_timeout
        status = queued["status"]
        while time.monotonic() < deadline:
            detail = expect(
                session.get(f"{base}/scans/{scan_id}/", headers=auth(owner_token)),
                200,
                "scan detail",
            ).json()
            status = detail["status"]
            if status in {"completed", "failed"}:
                break
            time.sleep(5)

        findings = rows(expect(
            session.get(
                f"{base}/scans/{scan_id}/findings/",
                headers=auth(owner_token),
            ),
            200,
            "scan findings",
        ))
        results = rows(expect(
            session.get(
                f"{base}/scans/{scan_id}/results/",
                headers=auth(owner_token),
            ),
            200,
            "scan results",
        ))
        report["scan"].update(
            {
                "status": status,
                "progress": detail.get("progress"),
                "duration_seconds": detail.get("duration_seconds"),
                "results_by_category": {
                    item["category"]: {
                        "status": item["status"],
                        "score": item["score"],
                        "summary": item["summary"][:160],
                    }
                    for item in results
                },
                "finding_count": len(findings),
                "findings_by_check": {
                    item["check_code"]: item["severity"]
                    for item in findings
                },
            }
        )
        if status != "completed":
            raise SmokeFailure(f"security scan did not complete: {report['scan']}")
        for category in ("zap", "nuclei"):
            if category not in report["scan"]["results_by_category"]:
                raise SmokeFailure(f"missing {category} CheckResult: {report['scan']}")
        check("security_scan_completed", report["scan"])

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SmokeFailure as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        sys.exit(1)
