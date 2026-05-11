#!/usr/bin/env python3
"""Create the HubSpot custom property group + 12 contact properties used by
the Finwell AI waitlist form.

Idempotent — properties that already exist are skipped (HubSpot returns 409
on duplicate). The script reads a bearer token from the HUBSPOT_TOKEN env var.
Works with either a Private App token (recommended for production) or a
Personal Access Token (PAT).

Usage:
    HUBSPOT_TOKEN=pat-na1-... python3 scripts/hubspot_setup.py

Required token scopes:
    crm.schemas.contacts.write     (to create properties)
    crm.objects.contacts.read      (to verify lookups)
"""
from __future__ import annotations

import json
import os
import sys
from urllib import request, error

API = "https://api.hubapi.com/crm/v3"
GROUP_NAME = "finwell_survey"
GROUP_LABEL = "Finwell AI Survey"

# Each tuple: (internal name, label, type, fieldType, options or None).
# `type` and `fieldType` are HubSpot taxonomy. See:
# https://developers.hubspot.com/docs/api/crm/properties#property-types
PROPERTIES: list[tuple[str, str, str, str, list[dict] | None]] = [
    ("finwell_marketing_consent", "Marketing consent (Finwell)", "enumeration", "booleancheckbox", [
        {"label": "Yes", "value": "Yes"},
        {"label": "No", "value": "No"},
    ]),
    # Survey v1 properties (kept for back-compat with archived submissions)
    ("finwell_income_type", "Income type (v1)", "string", "text", None),
    ("finwell_salary_range", "Annual income range (v1)", "string", "text", None),
    ("finwell_fair_price", "Fair monthly price AUD (v1)", "number", "number", None),
    # Survey v2 properties
    ("finwell_segment", "Segment qualifier (v2)", "string", "text", None),
    ("finwell_lost_receipt", "Lost a tax receipt in last 12 months", "string", "text", None),
    ("finwell_tax_stress", "Tax-time stress (1-10, low=good)", "number", "number", None),
    ("finwell_deduction_confidence", "Deduction confidence (1-10)", "number", "number", None),
    ("finwell_top_feature", "Top feature priorities", "string", "textarea", None),
    ("finwell_trust_builder", "Trust builders selected", "string", "textarea", None),
    ("finwell_points_willingness", "Willingness to pay for points", "string", "text", None),
    # Van Westendorp price sensitivity (v2)
    ("finwell_price_too_cheap", "Price: too cheap (AUD/month)", "number", "number", None),
    ("finwell_price_bargain", "Price: bargain (AUD/month)", "number", "number", None),
    ("finwell_price_expensive", "Price: getting expensive (AUD/month)", "number", "number", None),
    ("finwell_price_too_expensive", "Price: too expensive (AUD/month)", "number", "number", None),
    # Tracking metadata (v2)
    ("finwell_survey_version", "Survey version", "string", "text", None),
    ("finwell_launch_phase", "Launch phase at submission", "string", "text", None),
]


def hs_request(method: str, path: str, body: dict | None = None, *, token: str) -> tuple[int, dict]:
    url = f"{API}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read() or b"{}")
    except error.HTTPError as e:
        try:
            payload = json.loads(e.read() or b"{}")
        except Exception:
            payload = {"message": str(e)}
        return e.code, payload


def ensure_group(token: str) -> None:
    status, body = hs_request("GET", f"/properties/contacts/groups/{GROUP_NAME}", token=token)
    if status == 200:
        print(f"  group exists: {GROUP_NAME}")
        return
    if status != 404:
        sys.exit(f"unexpected status {status} fetching group: {body}")
    status, body = hs_request(
        "POST",
        "/properties/contacts/groups",
        {"name": GROUP_NAME, "label": GROUP_LABEL, "displayOrder": -1},
        token=token,
    )
    if status not in (200, 201, 409):
        sys.exit(f"failed to create group ({status}): {body}")
    print(f"  group created: {GROUP_NAME}")


def ensure_property(name: str, label: str, ptype: str, field: str, options, token: str) -> None:
    status, body = hs_request("GET", f"/properties/contacts/{name}", token=token)
    if status == 200:
        print(f"  property exists: {name}")
        return
    if status != 404:
        sys.exit(f"unexpected status {status} fetching property {name}: {body}")
    payload: dict = {
        "name": name,
        "label": label,
        "type": ptype,
        "fieldType": field,
        "groupName": GROUP_NAME,
        "description": f"Captured by the Finwell AI waitlist survey ({label}).",
    }
    if options:
        payload["options"] = options
    status, body = hs_request("POST", "/properties/contacts", payload, token=token)
    if status in (200, 201):
        print(f"  property created: {name}")
        return
    if status == 409:
        print(f"  property exists (409): {name}")
        return
    sys.exit(f"failed to create property {name} ({status}): {body}")


def main() -> None:
    token = os.environ.get("HUBSPOT_TOKEN", "").strip()
    if not token:
        sys.exit("HUBSPOT_TOKEN env var not set. Export it before running this script.")

    # Sanity ping — fetches the basic info on the contacts schema.
    status, body = hs_request("GET", "/properties/contacts", token=token)
    if status != 200:
        sys.exit(f"token rejected ({status}): {body}")

    print(f"Using token (first 12 chars): {token[:12]}...")
    print("Ensuring property group…")
    ensure_group(token)
    print("Ensuring properties…")
    for name, label, ptype, field, options in PROPERTIES:
        ensure_property(name, label, ptype, field, options, token=token)
    print("Done.")


if __name__ == "__main__":
    main()
