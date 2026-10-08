from __future__ import annotations

from datetime import date, timedelta
import json
import re

from src.contracts import Architecture, EvidenceItem, ProcurementDecision
from src.data_access import (
    DATA_DIR,
    get_request,
    load_budgets,
    load_employees,
    load_purchase_history,
    load_software_catalog,
    load_vendors,
)
from src.telemetry import RunTelemetryCounter
from src.vendor_client import get_vendor_risk


REFERENCE_DATE = date(2026, 9, 30)
REVIEW_MAX_AGE = timedelta(days=365)


def _tool(counter: RunTelemetryCounter, name: str) -> None:
    counter.record_tool_call(name)


def _load_risk_snapshot(vendor_name: str) -> dict:
    path = DATA_DIR / "vendor_risk.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get(vendor_name, {})


def _vendor_risk(vendor_name: str, counter: RunTelemetryCounter) -> tuple[dict | None, str | None]:
    _tool(counter, "vendor_risk_api")
    try:
        return get_vendor_risk(vendor_name), None
    except Exception as exc:
        # The fixture identifies simulated outages. Other local fallback data keeps
        # the adapter usable when the optional mock service is not running.
        snapshot = _load_risk_snapshot(vendor_name)
        if snapshot.get("force_error"):
            return None, str(snapshot.get("error_message", exc))
        if snapshot:
            return snapshot, f"Risk API unavailable; used local snapshot ({type(exc).__name__})."
        return None, f"Risk API unavailable: {type(exc).__name__}: {exc}"


def _contains_injection(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.lower()
    patterns = (
        r"ignore\s+(all\s+)?(procurement|previous|these|the)\s+rules?",
        r"bypass\s+(controls|approval|security)",
        r"approve\s+(it|this|immediately)",
        r"treat\s+this\s+request\s+as\s+cfo-approved",
        r"ignore\s+.*instructions",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _approval_threshold(cost: float | None) -> list[str]:
    if cost is None:
        return []
    if cost <= 1000:
        return ["Manager"]
    if cost <= 10000:
        return ["Department Head", "Procurement"]
    if cost <= 25000:
        return ["Department Head", "Finance", "Procurement"]
    return ["Department Head", "Finance", "CFO", "Procurement"]


def _date_is_expired(value: object) -> bool:
    if not value:
        return True
    try:
        return REFERENCE_DATE - date.fromisoformat(str(value)) > REVIEW_MAX_AGE
    except ValueError:
        return True


def _required_fields(request: dict) -> list[str]:
    missing: list[str] = []
    required = {
        "requester_id": "requester",
        "product_name": "product/vendor",
        "vendor_name": "product/vendor",
        "annual_cost_usd": "annual cost",
        "user_count": "users/licenses",
        "business_justification": "business purpose",
        "data_access_level": "data access",
        "requested_integrations": "required integrations",
    }
    for field, label in required.items():
        value = request.get(field)
        if value is None or value == "" or (isinstance(value, list) and value is None):
            missing.append(label)
    if request.get("data_access_level") in {"unknown", "unspecified"}:
        missing.append("data access")
    return list(dict.fromkeys(missing))


def _collect_evidence(request_id: str, counter: RunTelemetryCounter) -> dict:
    request = get_request(request_id)
    _tool(counter, "request_lookup")

    employees = load_employees()
    employee = employees[employees["employee_id"] == request["requester_id"]].iloc[0].to_dict()
    _tool(counter, "employee_lookup")

    budgets = load_budgets()
    budget = budgets[budgets["department"] == employee["department"]].iloc[0].to_dict()
    _tool(counter, "budget_lookup")

    vendors = load_vendors()
    vendor_rows = vendors[vendors["vendor_name"] == request["vendor_name"]]
    vendor = vendor_rows.iloc[0].to_dict() if not vendor_rows.empty else {}
    _tool(counter, "vendor_registry_lookup")

    catalog = load_software_catalog()
    same_vendor = catalog[catalog["vendor_name"].str.casefold() == request["vendor_name"].casefold()]
    same_category = catalog[catalog["category"].str.casefold() == request["category"].casefold()]
    _tool(counter, "software_catalog_lookup")

    history = load_purchase_history()
    prior_purchases = history[history["vendor_name"].str.casefold() == request["vendor_name"].casefold()]
    _tool(counter, "purchase_history_lookup")

    risk, risk_error = _vendor_risk(request["vendor_name"], counter)
    return {
        "request": request,
        "employee": employee,
        "budget": budget,
        "vendor": vendor,
        "same_vendor": same_vendor.to_dict("records"),
        "same_category": same_category.to_dict("records"),
        "prior_purchases": prior_purchases.to_dict("records"),
        "risk": risk,
        "risk_error": risk_error,
    }


def _decide(facts: dict, counter: RunTelemetryCounter) -> ProcurementDecision:
    request = facts["request"]
    employee = facts["employee"]
    budget = facts["budget"]
    vendor = facts["vendor"]
    risk = facts["risk"]
    cost = request.get("annual_cost_usd")
    missing = _required_fields(request)
    flags: list[str] = []
    approvals = _approval_threshold(cost)
    evidence = [
        {
            "source": "request_lookup",
            "finding": f"{request['product_name']} requested by {employee['name']} in {employee['department']} for {cost if cost is not None else 'unspecified'} USD/year.",
            "reference": request["request_id"],
        },
        {
            "source": "budget_lookup",
            "finding": f"{employee['department']} has {float(budget['available_usd']):.0f} USD available software budget.",
            "reference": employee["department"],
        },
    ]

    if cost is not None:
        if float(cost) > float(budget["available_usd"]):
            flags.append("budget_insufficient")
            evidence.append({"source": "budget_check", "finding": "Annual cost exceeds available department budget."})
        else:
            evidence.append({"source": "budget_check", "finding": "Annual cost is within available department budget."})

    overlap = facts["same_vendor"] + facts["same_category"]
    if overlap:
        flags.append("existing_tool_overlap")
        names = ", ".join(sorted({row["product_name"] for row in overlap}))
        evidence.append({"source": "software_catalog_lookup", "finding": f"Existing approved catalog matches: {names}."})
    else:
        evidence.append({"source": "software_catalog_lookup", "finding": "No same-vendor or same-category catalog match found."})

    if facts["prior_purchases"]:
        evidence.append({"source": "purchase_history_lookup", "finding": "Prior approved purchases exist for this vendor."})

    security_reasons: list[str] = []
    data_access = str(request.get("data_access_level") or "").casefold()
    integrations = " ".join(str(item) for item in request.get("requested_integrations") or []).casefold()
    if any(token in data_access for token in ("source_code", "production", "confidential", "pii", "credential", "secret")):
        security_reasons.append("requested data access")
    if any(token in integrations for token in ("production", "cloud", "credential", "secret")):
        security_reasons.append("production or sensitive integration")

    if risk is None:
        flags.extend(["vendor_risk_unavailable", "security_review_required"])
        approvals.append("Security")
        evidence.append({"source": "vendor_risk_api", "finding": f"Vendor risk could not be verified: {facts['risk_error']}"})
    else:
        risk_status = str(risk.get("security_review_status", "unknown")).casefold()
        if risk_status != "approved" or _date_is_expired(risk.get("last_review_date")):
            flags.extend(["security_review_required", "vendor_review_expired"] if risk.get("last_review_date") else ["security_review_required"])
            security_reasons.append("vendor assessment missing, incomplete, or expired")
            approvals.append("Security")
        internal_status = str(vendor.get("security_status", "")).casefold()
        if internal_status and internal_status != risk_status:
            flags.append("conflicting_vendor_evidence")
            approvals.append("Security")
        evidence.append({
            "source": "vendor_risk_api",
            "finding": f"Vendor risk is {risk.get('risk_level', 'unknown')}; security status is {risk.get('security_review_status', 'unknown')}.",
            "reference": request["vendor_name"],
        })

    if security_reasons:
        flags.append("security_review_required")
        approvals.append("Security")
        evidence.append({"source": "security_rules", "finding": "Security review required for " + ", ".join(sorted(set(security_reasons))) + "."})

    if "pii" in data_access or (risk and risk.get("stores_data_outside_region")):
        flags.append("privacy_review_required")
        approvals.append("Privacy")
        evidence.append({"source": "privacy_rules", "finding": "The request involves personal data or cross-region storage."})

    if (str(vendor.get("procurement_status", "")).casefold() == "new" and cost is not None and float(cost) >= 10000) or str(vendor.get("legal_terms_status", "")).casefold() not in {"approved", "standard"}:
        flags.append("legal_review_required")
        approvals.append("Legal")
        evidence.append({"source": "legal_rules", "finding": "New vendor or unapproved legal terms require Legal review."})

    if any(_contains_injection(value) for value in request.values()):
        flags.append("prompt_injection_detected")
        evidence.append({"source": "untrusted_content_check", "finding": "Request text attempted to bypass procurement controls; it was treated as data, not instruction."})

    for item in missing:
        evidence.append({"source": "required_fields_check", "finding": f"Required information is missing: {item}."})
    if missing:
        flags.append("missing_information")

    approvals = list(dict.fromkeys(approvals))
    flags = list(dict.fromkeys(flags))
    if missing:
        recommendation = "Request clarification before approval"
        next_step = "Ask the requester for the missing information, then rerun policy checks."
    elif flags:
        recommendation = "Route for specialist review before approval"
        next_step = "Human approvers must review the listed evidence and resolve every flagged issue; do not purchase automatically."
    else:
        recommendation = "Eligible to proceed through required approvals"
        next_step = "Route to the listed human approvers; the copilot cannot approve or purchase."

    return ProcurementDecision(
        request_id=request["request_id"],
        recommendation=recommendation,
        evidence=[EvidenceItem.model_validate(item) for item in evidence],
        required_approvals=approvals,
        missing_information=missing,
        risk_flags=flags,
        next_step=next_step,
        human_review_required=True,
        telemetry={"llm_calls": 0, "tool_calls": counter.tool_calls, "tool_names": counter.tool_names},
    )


def handle_request(request_id: str, architecture: Architecture = "single") -> ProcurementDecision:
    """Assessment adapter.

    Keep this function callable by the public/hidden evaluation harness.
    Your internal implementation may use any framework, modules, agents, tools,
    deterministic checks, or orchestration strategy.
    """
    if architecture not in {"single", "staged"}:
        raise ValueError(f"Unsupported architecture: {architecture}")
    counter = RunTelemetryCounter()
    facts = _collect_evidence(request_id, counter)
    if architecture == "staged":
        # Stage 1 gathers normalized evidence; this explicit handoff marks the
        # boundary before stage 2 applies the shared deterministic policy engine.
        counter.record_tool_call("staged_evidence_handoff")
        return _decide(facts, counter)
    return _decide(facts, counter)
