#!/usr/bin/env python3
"""Validate and write the two strategic DDD reports used by the blackboard.

Report types:
- domain-boundary-draft.json   (domain-boundary-discovery specialist)
- domain-boundary-analysis.json (domain-context-mapping specialist)

The script is the only sanctioned writer for these reports. Invalid payloads
are rejected, never repaired.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

EXIT_OK = 0
EXIT_INVALID = 1
EXIT_SOURCE = 2
EXIT_IO = 3

SCHEMA_VERSION = "1.0"
DEFAULT_OUTPUT_DIR = "blackboard"

REPORT_TYPE_DISCOVERY = "domain-boundary-draft"
REPORT_TYPE_FINAL = "domain-boundary-analysis"
REPORT_TYPE_SLICE = "domain-slice"
REPORT_TYPE_CONTEXT_MAP = "context-map"
REPORT_FILENAMES = {
    REPORT_TYPE_DISCOVERY: "domain-boundary-draft.json",
    REPORT_TYPE_FINAL: "domain-boundary-analysis.json",
    REPORT_TYPE_CONTEXT_MAP: "context-map.json",
}
REPORT_KINDS = {
    "discovery": REPORT_TYPE_DISCOVERY,
    "final": REPORT_TYPE_FINAL,
    "domain-slice": REPORT_TYPE_SLICE,
    "context-map": REPORT_TYPE_CONTEXT_MAP,
}
SLICE_KEYS = (
    "schema_version",
    "report_type",
    "metadata",
    "subdomain",
    "ubiquitous_language",
    "bounded_contexts",
    "assumptions",
)

CONFIDENCES = frozenset({"high", "medium", "low"})
SUBDOMAIN_TYPES = frozenset({"core", "supporting", "generic"})
UNCERTAINTY_TYPES = frozenset({"Assumption", "Ambiguity", "Open question"})
RELATIONSHIPS = frozenset(
    {
        "Partnership",
        "Shared kernel",
        "Customer-supplier",
        "Conformist",
        "Anticorruption layer",
        "Open host service / published language",
        "Separate ways",
    }
)
EXTERNAL_MARKERS = frozenset({"external", "external system", "outside"})

METADATA_REQUIRED_KEYS = ("generated_at", "agent")
METADATA_OPTIONAL_KEYS = ("run_id", "source_description", "source_report", "confidence")
BUSINESS_SUMMARY_KEYS = ("goal", "actors", "end_to_end_processes", "key_outcomes")
LANGUAGE_KEYS = ("term", "context", "definition", "synonyms_conflicts")
LANGUAGE_REQUIRED_KEYS = ("term", "context", "definition")
SUBDOMAIN_KEYS = ("name", "type", "capability", "why_distinct")
CONTEXT_KEYS = (
    "name",
    "responsibility",
    "in_scope",
    "out_of_scope",
    "ubiquitous_language",
    "invariants",
    "source_of_truth",
    "publishes",
    "consumes",
    "actors",
    "external_systems",
    "confidence",
)
CONTEXT_REQUIRED_KEYS = (
    "name",
    "responsibility",
    "in_scope",
    "out_of_scope",
    "ubiquitous_language",
    "invariants",
    "source_of_truth",
    "publishes",
    "consumes",
    "actors",
    "confidence",
)
ASSUMPTION_KEYS = ("item", "type", "impact_on_boundaries", "confidence")
MAPPING_HANDOFF_KEYS = ("contexts_ready", "unresolved_risks")

CONTEXT_MAP_KEYS = (
    "upstream",
    "downstream",
    "relationship",
    "direction",
    "exchanged_information",
    "boundary_protection",
)
FLOW_KEYS = ("business_process", "contexts_involved", "consistency_expectation", "notes")
FLOW_REQUIRED_KEYS = ("business_process", "contexts_involved", "consistency_expectation")
BOUNDARY_OVERVIEW_KEYS = ("from", "to", "description")
RATIONALE_KEYS = ("why_these_boundaries", "rejected_alternatives", "weakest_boundaries")
HANDOFF_KEYS = ("modeling_focus", "deeper_investigation", "coupling_risks", "out_of_scope")
CONTEXT_MAP_FILE_KEYS = ("schema_version", "report_type", "metadata", "context_map", "cross_boundary_flows")

DISCOVERY_KEYS = (
    "schema_version",
    "report_type",
    "metadata",
    "business_summary",
    "ubiquitous_language",
    "subdomains",
    "bounded_contexts",
    "assumptions",
    "mapping_handoff",
)
FINAL_KEYS = (
    "schema_version",
    "report_type",
    "metadata",
    "business_summary",
    "ubiquitous_language",
    "subdomains",
    "bounded_contexts",
    "context_map",
    "cross_boundary_flows",
    "boundary_overview",
    "boundary_rationale",
    "assumptions",
    "handoff_notes",
)


def is_non_empty_str(value):
    return isinstance(value, str) and bool(value.strip())


def is_string_list(value):
    return isinstance(value, list) and all(is_non_empty_str(item) for item in value)


def is_non_empty_string_list(value):
    return is_string_list(value) and bool(value)


def is_text(value):
    return is_non_empty_str(value) or is_string_list(value)


def check_keys(payload, required_keys, optional_keys, label):
    if not isinstance(payload, dict):
        return f"{label} must be an object"
    missing = [key for key in required_keys if key not in payload]
    if missing:
        return f"{label} is missing required key(s): {', '.join(missing)}"
    unexpected = sorted(set(payload) - set(required_keys) - set(optional_keys))
    if unexpected:
        return f"{label} has unsupported key(s): {', '.join(unexpected)}"
    return None


def require_text(payload, key, label):
    if not is_text(payload.get(key)):
        return f"{label}.{key} must be a non-empty string or a list of non-empty strings"
    return None


def require_string_list(payload, key, label, allow_empty=True):
    value = payload.get(key)
    valid = is_string_list(value) if allow_empty else is_non_empty_string_list(value)
    if not valid:
        suffix = "" if allow_empty else " (at least one item)"
        return f"{label}.{key} must be a list of non-empty strings{suffix}"
    return None


def validate_timestamp(value, label):
    if not is_non_empty_str(value):
        return f"{label} must be a non-empty ISO-8601 timestamp"
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        return f"{label} must be a valid ISO-8601 timestamp (got {value!r})"
    return None


def validate_metadata(metadata, report_type, label):
    reason = check_keys(metadata, METADATA_REQUIRED_KEYS, METADATA_OPTIONAL_KEYS, label)
    if reason:
        return reason
    reason = validate_timestamp(metadata.get("generated_at"), f"{label}.generated_at")
    if reason:
        return reason
    if not is_non_empty_str(metadata.get("agent")):
        return f"{label}.agent must be a non-empty string"
    for key in ("run_id", "source_description", "source_report"):
        if key in metadata and not is_non_empty_str(metadata[key]):
            return f"{label}.{key} must be a non-empty string when present"
    if "confidence" in metadata and metadata["confidence"] not in CONFIDENCES:
        return f"{label}.confidence must be one of {sorted(CONFIDENCES)} (got {metadata['confidence']!r})"
    if report_type in (REPORT_TYPE_FINAL, REPORT_TYPE_CONTEXT_MAP) and not is_non_empty_str(
        metadata.get("source_report")
    ):
        return f"{label}.source_report is required for {report_type}"
    return None


def validate_business_summary(summary, label):
    reason = check_keys(summary, BUSINESS_SUMMARY_KEYS, (), label)
    if reason:
        return reason
    reason = require_text(summary, "goal", label)
    if reason:
        return reason
    for key in ("actors", "end_to_end_processes", "key_outcomes"):
        reason = require_string_list(summary, key, label)
        if reason:
            return reason
    return None


def validate_language(language, label):
    if not isinstance(language, list) or not language:
        return f"{label} must be a non-empty list"
    for index, entry in enumerate(language):
        entry_label = f"{label}[{index}]"
        reason = check_keys(entry, LANGUAGE_REQUIRED_KEYS, ("synonyms_conflicts",), entry_label)
        if reason:
            return reason
        for key in LANGUAGE_REQUIRED_KEYS:
            if not is_non_empty_str(entry.get(key)):
                return f"{entry_label}.{key} must be a non-empty string"
        if "synonyms_conflicts" in entry:
            reason = require_text(entry, "synonyms_conflicts", entry_label)
            if reason:
                return reason
    return None


def validate_subdomains(subdomains, label):
    if not isinstance(subdomains, list) or not subdomains:
        return f"{label} must be a non-empty list"
    seen = set()
    for index, subdomain in enumerate(subdomains):
        subdomain_label = f"{label}[{index}]"
        reason = check_keys(subdomain, SUBDOMAIN_KEYS, (), subdomain_label)
        if reason:
            return reason
        for key in ("name", "capability", "why_distinct"):
            if not is_non_empty_str(subdomain.get(key)):
                return f"{subdomain_label}.{key} must be a non-empty string"
        if subdomain["type"] not in SUBDOMAIN_TYPES:
            return (
                f"{subdomain_label}.type must be one of {sorted(SUBDOMAIN_TYPES)} "
                f"(got {subdomain['type']!r})"
            )
        name = subdomain["name"].strip().casefold()
        if name in seen:
            return f"{subdomain_label}.name duplicates another subdomain name ({subdomain['name']!r})"
        seen.add(name)
    return None


def validate_bounded_contexts(contexts, label):
    if not isinstance(contexts, list) or not contexts:
        return f"{label} must be a non-empty list"
    names = {}
    invariants = {}
    sources = {}
    for index, context in enumerate(contexts):
        context_label = f"{label}[{index}]"
        reason = check_keys(context, CONTEXT_REQUIRED_KEYS, ("external_systems",), context_label)
        if reason:
            return reason
        for key in ("name", "responsibility"):
            if not is_non_empty_str(context.get(key)):
                return f"{context_label}.{key} must be a non-empty string"
        for key in (
            "in_scope",
            "out_of_scope",
            "ubiquitous_language",
            "invariants",
            "source_of_truth",
            "publishes",
            "consumes",
            "actors",
        ):
            reason = require_string_list(context, key, context_label)
            if reason:
                return reason
        if "external_systems" in context:
            reason = require_string_list(context, "external_systems", context_label)
            if reason:
                return reason
        if context["confidence"] not in CONFIDENCES:
            return (
                f"{context_label}.confidence must be one of {sorted(CONFIDENCES)} "
                f"(got {context['confidence']!r})"
            )
        name_key = context["name"].strip().casefold()
        if name_key in names:
            return f"{context_label}.name duplicates another bounded context name ({context['name']!r})"
        names[name_key] = context["name"]
        for invariant in context["invariants"]:
            key = normalize_reference(invariant)
            if key in invariants and invariants[key] != context["name"]:
                return (
                    f"invariant {invariant!r} is owned by both {invariants[key]!r} and "
                    f"{context['name']!r}; an invariant must have exactly one owner"
                )
            invariants[key] = context["name"]
        for source in context["source_of_truth"]:
            key = normalize_reference(source)
            if key in sources and sources[key] != context["name"]:
                return (
                    f"source of truth {source!r} is owned by both {sources[key]!r} and "
                    f"{context['name']!r}; it must have exactly one owner"
                )
            sources[key] = context["name"]
    return names


def validate_assumptions(assumptions, label):
    if not isinstance(assumptions, list):
        return f"{label} must be a list"
    for index, assumption in enumerate(assumptions):
        assumption_label = f"{label}[{index}]"
        reason = check_keys(assumption, ASSUMPTION_KEYS, (), assumption_label)
        if reason:
            return reason
        for key in ("item", "impact_on_boundaries"):
            if not is_non_empty_str(assumption.get(key)):
                return f"{assumption_label}.{key} must be a non-empty string"
        if assumption["type"] not in UNCERTAINTY_TYPES:
            return (
                f"{assumption_label}.type must be one of {sorted(UNCERTAINTY_TYPES)} "
                f"(got {assumption['type']!r})"
            )
        if assumption["confidence"] not in CONFIDENCES:
            return (
                f"{assumption_label}.confidence must be one of {sorted(CONFIDENCES)} "
                f"(got {assumption['confidence']!r})"
            )
    return None


def validate_mapping_handoff(handoff, label, context_names):
    reason = check_keys(handoff, MAPPING_HANDOFF_KEYS, (), label)
    if reason:
        return reason
    for key in MAPPING_HANDOFF_KEYS:
        reason = require_string_list(handoff, key, label)
        if reason:
            return reason
    unknown = sorted(
        name for name in handoff["contexts_ready"] if name.strip().casefold() not in context_names
    )
    if unknown:
        return (
            f"{label}.contexts_ready references unknown bounded context name(s): "
            f"{', '.join(unknown)}; use the exact bounded context names"
        )
    return None


def normalize_reference(value):
    return re.sub(r"\s+", " ", value.strip().casefold())


def is_known_context(value, context_names):
    return value.strip().casefold() in context_names


def validate_context_reference(value, context_names, label):
    if not is_non_empty_str(value):
        return f"{label} must be a non-empty string"
    if is_known_context(value, context_names):
        return None
    if value.strip().casefold() in EXTERNAL_MARKERS:
        return None
    return (
        f"{label} references unknown bounded context {value!r}; "
        "use an exact bounded context name or 'external'"
    )


def validate_context_map(context_map, context_names, label):
    if not isinstance(context_map, list):
        return f"{label} must be a list"
    if len(context_names) > 1 and not context_map:
        return f"{label} must contain at least one relationship when more than one context exists"
    for index, relationship in enumerate(context_map):
        relationship_label = f"{label}[{index}]"
        reason = check_keys(relationship, CONTEXT_MAP_KEYS, (), relationship_label)
        if reason:
            return reason
        reason = validate_context_reference(
            relationship.get("upstream"), context_names, f"{relationship_label}.upstream"
        )
        if reason:
            return reason
        reason = validate_context_reference(
            relationship.get("downstream"), context_names, f"{relationship_label}.downstream"
        )
        if reason:
            return reason
        if relationship["relationship"] not in RELATIONSHIPS:
            return (
                f"{relationship_label}.relationship must be one of {sorted(RELATIONSHIPS)} "
                f"(got {relationship['relationship']!r})"
            )
        for key in ("direction", "exchanged_information", "boundary_protection"):
            reason = require_text(relationship, key, relationship_label)
            if reason:
                return reason
    return None


def validate_cross_boundary_flows(flows, context_names, label):
    if not isinstance(flows, list):
        return f"{label} must be a list"
    for index, flow in enumerate(flows):
        flow_label = f"{label}[{index}]"
        reason = check_keys(flow, FLOW_REQUIRED_KEYS, ("notes",), flow_label)
        if reason:
            return reason
        if not is_non_empty_str(flow.get("business_process")):
            return f"{flow_label}.business_process must be a non-empty string"
        reason = require_string_list(flow, "contexts_involved", flow_label, allow_empty=False)
        if reason:
            return reason
        for name in flow["contexts_involved"]:
            reason = validate_context_reference(name, context_names, f"{flow_label}.contexts_involved")
            if reason:
                return reason
        reason = require_text(flow, "consistency_expectation", flow_label)
        if reason:
            return reason
        if "notes" in flow:
            reason = require_text(flow, "notes", flow_label)
            if reason:
                return reason
    return None


def validate_boundary_overview(overview, context_names, label):
    if not isinstance(overview, list):
        return f"{label} must be a list"
    for index, item in enumerate(overview):
        item_label = f"{label}[{index}]"
        if isinstance(item, str):
            if not is_non_empty_str(item):
                return f"{item_label} must be a non-empty string"
            continue
        reason = check_keys(item, BOUNDARY_OVERVIEW_KEYS, (), item_label)
        if reason:
            return reason
        reason = validate_context_reference(item.get("from"), context_names, f"{item_label}.from")
        if reason:
            return reason
        reason = validate_context_reference(item.get("to"), context_names, f"{item_label}.to")
        if reason:
            return reason
        reason = require_text(item, "description", item_label)
        if reason:
            return reason
    return None


def validate_rationale(rationale, label):
    reason = check_keys(rationale, RATIONALE_KEYS, (), label)
    if reason:
        return reason
    for key in RATIONALE_KEYS:
        reason = require_text(rationale, key, label)
        if reason:
            return reason
    return None


def validate_handoff_notes(handoff, label):
    reason = check_keys(handoff, HANDOFF_KEYS, (), label)
    if reason:
        return reason
    for key in HANDOFF_KEYS:
        reason = require_text(handoff, key, label)
        if reason:
            return reason
    return None


def validate_discovery(report):
    reason = check_keys(report, DISCOVERY_KEYS, (), "report")
    if reason:
        return reason
    context_names = validate_bounded_contexts(report.get("bounded_contexts"), "report.bounded_contexts")
    if isinstance(context_names, str):
        return context_names
    reason = validate_mapping_handoff(
        report.get("mapping_handoff"), "report.mapping_handoff", context_names
    )
    if reason:
        return reason
    return None


def validate_final(report):
    reason = check_keys(report, FINAL_KEYS, (), "report")
    if reason:
        return reason
    context_names = validate_bounded_contexts(report.get("bounded_contexts"), "report.bounded_contexts")
    if isinstance(context_names, str):
        return context_names
    reason = validate_context_map(report.get("context_map"), context_names, "report.context_map")
    if reason:
        return reason
    reason = validate_cross_boundary_flows(
        report.get("cross_boundary_flows"), context_names, "report.cross_boundary_flows"
    )
    if reason:
        return reason
    reason = validate_boundary_overview(
        report.get("boundary_overview"), context_names, "report.boundary_overview"
    )
    if reason:
        return reason
    reason = validate_rationale(report.get("boundary_rationale"), "report.boundary_rationale")
    if reason:
        return reason
    return validate_handoff_notes(report.get("handoff_notes"), "report.handoff_notes")


def validate_domain_slice(report):
    """Validate one per-subdomain file consumed by domain-context-mapping."""
    reason = check_keys(report, SLICE_KEYS, (), "report")
    if reason:
        return reason
    reason = validate_metadata(report.get("metadata"), REPORT_TYPE_SLICE, "report.metadata")
    if reason:
        return reason
    reason = validate_subdomains([report.get("subdomain")], "report.subdomain")
    if reason:
        return reason
    reason = validate_language(report.get("ubiquitous_language"), "report.ubiquitous_language")
    if reason:
        return reason
    context_names = validate_bounded_contexts(report.get("bounded_contexts"), "report.bounded_contexts")
    if isinstance(context_names, str):
        return context_names
    return validate_assumptions(report.get("assumptions"), "report.assumptions")


def load_context_names(source_report):
    """Collect bounded context names from every per-domain slice in source_report."""
    directory = Path(source_report).expanduser()
    if not directory.is_absolute():
        directory = Path.cwd() / directory
    if not directory.is_dir():
        return None, f"source report directory not found: {source_report}"
    names = set()
    for path in sorted(directory.glob("domain-boundary-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return None, f"cannot read slice {path}: {exc}"
        contexts = data.get("bounded_contexts") if isinstance(data, dict) else None
        for context in contexts if isinstance(contexts, list) else []:
            if isinstance(context, dict) and is_non_empty_str(context.get("name")):
                names.add(context["name"])
    if not names:
        return None, f"no bounded contexts found in per-domain files under {source_report}"
    return sorted({name.strip().casefold() for name in names}), None


def validate_context_map_file(report):
    """Validate the lightweight context map: relationships and flows only."""
    reason = check_keys(report, CONTEXT_MAP_FILE_KEYS, (), "report")
    if reason:
        return reason
    reason = validate_metadata(report.get("metadata"), REPORT_TYPE_CONTEXT_MAP, "report.metadata")
    if reason:
        return reason
    context_names, reason = load_context_names(report["metadata"]["source_report"])
    if reason:
        return reason
    reason = validate_context_map(report.get("context_map"), context_names, "report.context_map")
    if reason:
        return reason
    return validate_cross_boundary_flows(
        report.get("cross_boundary_flows"), context_names, "report.cross_boundary_flows"
    )


def validate_report(report):
    if not isinstance(report, dict):
        return "report must be a JSON object"
    if report.get("schema_version") != SCHEMA_VERSION:
        return (
            f"report.schema_version must be '{SCHEMA_VERSION}' "
            f"(got {report.get('schema_version')!r})"
        )
    report_type = report.get("report_type")
    if report_type == REPORT_TYPE_SLICE:
        return validate_domain_slice(report)
    if report_type == REPORT_TYPE_CONTEXT_MAP:
        return validate_context_map_file(report)
    if report_type not in REPORT_FILENAMES:
        return (
            f"report.report_type must be one of {sorted([*REPORT_FILENAMES, REPORT_TYPE_SLICE])} "
            f"(got {report_type!r})"
        )
    reason = validate_metadata(report.get("metadata"), report_type, "report.metadata")
    if reason:
        return reason
    reason = validate_business_summary(report.get("business_summary"), "report.business_summary")
    if reason:
        return reason
    reason = validate_language(report.get("ubiquitous_language"), "report.ubiquitous_language")
    if reason:
        return reason
    reason = validate_subdomains(report.get("subdomains"), "report.subdomains")
    if reason:
        return reason
    reason = validate_assumptions(report.get("assumptions"), "report.assumptions")
    if reason:
        return reason
    return validate_final(report) if report_type == REPORT_TYPE_FINAL else validate_discovery(report)


def read_source(source):
    if source == "-":
        return sys.stdin.read(), None
    path = Path(source).expanduser()
    try:
        return path.read_text(encoding="utf-8"), None
    except OSError as exc:
        return None, f"cannot read source {path}: {exc}"


def resolve_report_type(payload, requested_kind):
    payload_type = payload.get("report_type") if isinstance(payload, dict) else None
    if requested_kind:
        expected = REPORT_KINDS[requested_kind]
        if payload_type != expected:
            return (
                None,
                f"--report-type {requested_kind} expects report_type '{expected}' "
                f"(got {payload_type!r})",
            )
        return expected, None
    if payload_type not in REPORT_FILENAMES and payload_type != REPORT_TYPE_SLICE:
        return None, f"unknown report_type {payload_type!r}"
    return payload_type, None


def resolve_target(report_type, output_dir, target):
    if target:
        path = Path(target).expanduser()
        if path.suffix != ".json":
            return None, f"target report must use the .json extension (got {path.name!r})"
        return path, None
    if report_type == REPORT_TYPE_SLICE:
        return None, "--target is required for domain-slice reports (blackboard/domain/domain-boundary-<slug>.json)"
    return Path(output_dir).expanduser() / REPORT_FILENAMES[report_type], None


def check_source_report(report):
    source_report = report["metadata"]["source_report"]
    candidate = Path(source_report).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    if not candidate.is_file():
        return f"source report not found: {source_report}"
    return None


def write_target(path, report, force):
    if path.exists() and not force:
        return f"target already exists: {path} (pass --force to overwrite)"
    temporary = path.with_name(f"{path.name}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    except OSError as exc:
        if temporary.exists():
            temporary.unlink(missing_ok=True)
        return f"cannot write target {path}: {exc}"
    return None


def build_discovery_template():
    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": REPORT_TYPE_DISCOVERY,
        "metadata": {
            "generated_at": "2026-01-01T00:00:00Z",
            "agent": "domain-boundary-discovery-specialist",
            "source_description": "User business description analyzed in this run.",
        },
        "business_summary": {
            "goal": "What the business wants to achieve.",
            "actors": ["Actor or role"],
            "end_to_end_processes": ["End-to-end business process"],
            "key_outcomes": ["Observable business outcome"],
        },
        "ubiquitous_language": [
            {
                "term": "Domain term",
                "context": "Example Context",
                "definition": "What the term means inside that context.",
                "synonyms_conflicts": [],
            }
        ],
        "subdomains": [
            {
                "name": "Example Subdomain",
                "type": "core",
                "capability": "Business capability owned by this subdomain.",
                "why_distinct": "Why this area has its own rules, language, or lifecycle.",
            }
        ],
        "bounded_contexts": [
            {
                "name": "Example Context",
                "responsibility": "Single business responsibility of the context.",
                "in_scope": ["Concept handled inside the context"],
                "out_of_scope": ["Concept handled elsewhere"],
                "ubiquitous_language": ["Domain term"],
                "invariants": ["Business rule owned by this context"],
                "source_of_truth": ["Concept this context owns"],
                "publishes": ["Domain event published"],
                "consumes": [],
                "actors": ["Actor or role"],
                "external_systems": [],
                "confidence": "medium",
            }
        ],
        "assumptions": [
            {
                "item": "Assumption, ambiguity, or open question.",
                "type": "Open question",
                "impact_on_boundaries": "Which boundary could change and why.",
                "confidence": "low",
            }
        ],
        "mapping_handoff": {
            "contexts_ready": ["Example Context"],
            "unresolved_risks": ["Boundary risk still unresolved"],
        },
    }


def build_final_template():
    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": REPORT_TYPE_FINAL,
        "metadata": {
            "generated_at": "2026-01-01T00:00:00Z",
            "agent": "domain-context-mapping-specialist",
            "source_report": "blackboard/domain-boundary-draft.json",
        },
        "business_summary": {
            "goal": "What the business wants to achieve.",
            "actors": ["Actor or role"],
            "end_to_end_processes": ["End-to-end business process"],
            "key_outcomes": ["Observable business outcome"],
        },
        "ubiquitous_language": [
            {
                "term": "Domain term",
                "context": "Example Context",
                "definition": "What the term means inside that context.",
                "synonyms_conflicts": [],
            }
        ],
        "subdomains": [
            {
                "name": "Example Subdomain",
                "type": "core",
                "capability": "Business capability owned by this subdomain.",
                "why_distinct": "Why this area has its own rules, language, or lifecycle.",
            }
        ],
        "bounded_contexts": [
            {
                "name": "Example Context",
                "responsibility": "Single business responsibility of the context.",
                "in_scope": ["Concept handled inside the context"],
                "out_of_scope": ["Concept handled elsewhere"],
                "ubiquitous_language": ["Domain term"],
                "invariants": ["Business rule owned by this context"],
                "source_of_truth": ["Concept this context owns"],
                "publishes": ["Domain event published"],
                "consumes": [],
                "actors": ["Actor or role"],
                "external_systems": [],
                "confidence": "medium",
            }
        ],
        "context_map": [],
        "cross_boundary_flows": [],
        "boundary_overview": [],
        "boundary_rationale": {
            "why_these_boundaries": "Why these boundaries and not adjacent alternatives.",
            "rejected_alternatives": "Splits or merges rejected and the reason.",
            "weakest_boundaries": "Weakest or riskiest boundaries.",
        },
        "assumptions": [],
        "handoff_notes": {
            "modeling_focus": "Core subdomains to model first.",
            "deeper_investigation": "Areas needing deeper investigation.",
            "coupling_risks": "Coupling or model-leak risks.",
            "out_of_scope": "What must remain outside the next analysis.",
        },
    }


def build_slice_template():
    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": REPORT_TYPE_SLICE,
        "metadata": {
            "generated_at": "2026-01-01T00:00:00Z",
            "agent": "domain-boundary-discovery-specialist",
        },
        "subdomain": {
            "name": "Example Subdomain",
            "type": "core",
            "capability": "Business capability owned by this subdomain.",
            "why_distinct": "Why this area has its own rules, language, or lifecycle.",
        },
        "ubiquitous_language": [
            {
                "term": "Domain term",
                "context": "Example Context",
                "definition": "What the term means inside that context.",
            }
        ],
        "bounded_contexts": [
            {
                "name": "Example Context",
                "responsibility": "Single business responsibility of the context.",
                "in_scope": ["Concept handled inside the context"],
                "out_of_scope": ["Concept handled elsewhere"],
                "ubiquitous_language": ["Domain term"],
                "invariants": ["Business rule owned by this context"],
                "source_of_truth": ["Concept this context owns"],
                "publishes": ["Domain event published"],
                "consumes": [],
                "actors": ["Actor or role"],
                "external_systems": [],
                "confidence": "medium",
            }
        ],
        "assumptions": [
            {
                "item": "Assumption, ambiguity, or open question.",
                "type": "Open question",
                "impact_on_boundaries": "Which boundary could change and why.",
                "confidence": "low",
            }
        ],
    }


def build_context_map_template():
    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": REPORT_TYPE_CONTEXT_MAP,
        "metadata": {
            "generated_at": "2026-01-01T00:00:00Z",
            "agent": "domain-context-mapping-specialist",
            "source_report": "blackboard/domain",
        },
        "context_map": [
            {
                "upstream": "Example Context",
                "downstream": "external",
                "relationship": "Open host service / published language",
                "direction": "Example Context -> external",
                "exchanged_information": "Published domain event fields.",
                "boundary_protection": "Versioned event contract.",
            }
        ],
        "cross_boundary_flows": [
            {
                "business_process": "End-to-end business process",
                "contexts_involved": ["Example Context", "external"],
                "consistency_expectation": "Eventual consistency.",
                "notes": "Optional notes.",
            }
        ],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate and write a strategic DDD report to the blackboard.",
        epilog="Exit codes: 0 written, 1 invalid payload, 2 source error, 3 write error.",
    )
    parser.add_argument("--source", metavar="FILE", help="JSON payload file ('-' for stdin)")
    parser.add_argument(
        "--report-type",
        choices=sorted(REPORT_KINDS),
        help="discovery (boundary draft), domain-slice (one subdomain file), or final (context analysis)",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        metavar="DIR",
        help=f"folder receiving the report (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument("--target", metavar="FILE", help="explicit destination .json file")
    parser.add_argument("--force", action="store_true", help="overwrite an existing report")
    parser.add_argument(
        "--check-source",
        action="store_true",
        help="for final reports, require metadata.source_report to exist on disk",
    )
    parser.add_argument(
        "--emit-template",
        choices=sorted(REPORT_KINDS),
        help="print a schema-valid skeleton for the selected report and exit",
    )
    args = parser.parse_args()

    if args.emit_template:
        selected = REPORT_KINDS[args.emit_template]
        template = {
            REPORT_TYPE_FINAL: build_final_template,
            REPORT_TYPE_SLICE: build_slice_template,
            REPORT_TYPE_CONTEXT_MAP: build_context_map_template,
        }.get(selected, build_discovery_template)()
        print(json.dumps(template, indent=2, ensure_ascii=False))
        return EXIT_OK

    if not args.source:
        parser.error("--source is required (use '-' to read the payload from stdin)")

    raw, reason = read_source(args.source)
    if reason:
        print(f"[writer-file] {reason}", file=sys.stderr)
        return EXIT_SOURCE

    try:
        report = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"[writer-file] source is not valid JSON: {exc}", file=sys.stderr)
        return EXIT_INVALID

    report_type, reason = resolve_report_type(report, args.report_type)
    if reason:
        print(f"[writer-file] {reason}", file=sys.stderr)
        return EXIT_INVALID

    reason = validate_report(report)
    if reason:
        print(f"[writer-file] invalid report: {reason}", file=sys.stderr)
        return EXIT_INVALID

    if args.check_source and report_type == REPORT_TYPE_FINAL:
        reason = check_source_report(report)
        if reason:
            print(f"[writer-file] {reason}", file=sys.stderr)
            return EXIT_SOURCE

    path, reason = resolve_target(report_type, args.output_dir, args.target)
    if reason:
        print(f"[writer-file] {reason}", file=sys.stderr)
        return EXIT_INVALID

    reason = write_target(path, report, args.force)
    if reason:
        print(f"[writer-file] {reason}", file=sys.stderr)
        return EXIT_IO

    if report_type == REPORT_TYPE_CONTEXT_MAP:
        print(
            f"[writer-file] wrote {path} ({report_type}, {len(report['context_map'])} "
            f"relationship(s), {len(report['cross_boundary_flows'])} flow(s))"
        )
        return EXIT_OK

    context_count = len(report["bounded_contexts"])
    print(
        f"[writer-file] wrote {path} ({report_type}, {context_count} context(s), "
        f"{len(report['assumptions'])} assumption(s))"
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
