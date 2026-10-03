"""Evaluate reviewable validation rules and optionally persist them to DuckDB.

The rule catalog is intentionally data-driven: reviewers edit
`rules/validation_rule_catalog.yaml`, while this runner only extracts measurements,
evaluates simple predicates, and stores the catalog/run history in a lightweight DuckDB
file for later audit queries.

Paper inspiration:
    "Liaison-Based Enriched CAD Model Representation for Assembly Tasks"
    DOI: https://doi.org/10.14733/cadaps.2024.1045-1062

Examples:
    rtk uv run python studies/xl430_lowcost/validate_rule_catalog.py \
      --profile candidate_preservation --sync-db --store-run --fail-on-blocking

    rtk uv run python studies/xl430_lowcost/validate_rule_catalog.py \
      --profile assembly_characterization --store-run
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import duckdb
import yaml

_STUDY_DIR = Path(__file__).resolve().parent
if str(_STUDY_DIR) not in sys.path:
    sys.path.insert(0, str(_STUDY_DIR))

import build_liaison_interfaces as liaison_interface  # noqa: E402
import validate_assembly_liaisons as assembly_liaison  # noqa: E402
import validate_extension_preservation as extension_preservation  # noqa: E402
import validate_fastening_interfaces as fastening_interface  # noqa: E402

DEFAULT_CATALOG = _STUDY_DIR / "rules" / "validation_rule_catalog.yaml"
DEFAULT_DB = _STUDY_DIR / "rules" / "validation_rules.duckdb"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_catalog(path: Path = DEFAULT_CATALOG) -> dict:
    with Path(path).open("r", encoding="utf-8") as fh:
        catalog = yaml.safe_load(fh)
    if not isinstance(catalog, dict) or "rules" not in catalog:
        raise ValueError(f"invalid rule catalog: {path}")
    return catalog


def _parse_vec3(value: str) -> tuple[float, float, float]:
    parts = [float(x.strip()) for x in value.split(",") if x.strip()]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("expected comma-separated vector x,y,z")
    return (parts[0], parts[1], parts[2])


def _profile_group_ids(catalog: dict, profile_id: str) -> set[str]:
    for profile in catalog.get("profiles", []):
        if profile.get("profile_id") == profile_id:
            return set(profile.get("enabled_group_ids", []))
    raise ValueError(f"profile not found in rule catalog: {profile_id}")


def _group_by_id(catalog: dict) -> dict[str, dict]:
    return {group["group_id"]: group for group in catalog.get("groups", [])}


def _selected_rules(catalog: dict, profile_id: str) -> list[dict]:
    group_ids = _profile_group_ids(catalog, profile_id)
    return [
        rule for rule in catalog.get("rules", [])
        if rule.get("enabled", True) and rule.get("group_id") in group_ids
    ]


def _extract_sources(
    needed_sources: Iterable[str],
    candidate_translate: tuple[float, float, float],
    preservation_samples: int,
) -> dict[str, dict]:
    out: dict[str, dict] = {}
    needed = set(needed_sources)
    if "extension_preservation" in needed:
        _, out["extension_preservation"] = extension_preservation._run(samples=preservation_samples)
    if "fastening_interface" in needed:
        _, out["fastening_interface"] = fastening_interface._run(
            candidate_translate=candidate_translate,
            fail_on_mismatch=False,
        )
    if "liaison_interface" in needed:
        _, out["liaison_interface"] = liaison_interface._run(
            candidate_translate=candidate_translate,
            fail_on_mismatch=False,
        )
    if "assembly_liaison" in needed:
        _, out["assembly_liaison"] = assembly_liaison._run(fail_on_mismatch=False)
    return out


def _flatten(items: Iterable[Any]) -> list[Any]:
    flat: list[Any] = []
    for item in items:
        if isinstance(item, list):
            flat.extend(_flatten(item))
        else:
            flat.append(item)
    return flat


def _path_values(data: Any, path: str) -> list[Any]:
    """Resolve a small JSONPath-like subset: dotted keys plus [*] list expansion."""
    current = [data]
    for raw_part in path.split("."):
        expand_list = raw_part.endswith("[*]")
        part = raw_part[:-3] if expand_list else raw_part
        next_values: list[Any] = []
        for value in current:
            if isinstance(value, dict):
                if part not in value:
                    continue
                child = value[part]
            else:
                continue
            if expand_list:
                if isinstance(child, list):
                    next_values.extend(child)
            else:
                next_values.append(child)
        current = next_values
    return _flatten(current)


def _aggregate(values: list[Any], aggregate: str) -> Any:
    if aggregate == "value":
        return values[0] if values else None
    if aggregate == "len":
        return len(values[0]) if len(values) == 1 and isinstance(values[0], list) else len(values)
    if aggregate == "max":
        numeric = [float(v) for v in values if v is not None]
        return max(numeric) if numeric else None
    if aggregate == "min":
        numeric = [float(v) for v in values if v is not None]
        return min(numeric) if numeric else None
    if aggregate == "all":
        return all(bool(v) for v in values) if values else False
    if aggregate == "any":
        return any(bool(v) for v in values) if values else False
    if aggregate == "all_in":
        return values
    raise ValueError(f"unsupported aggregate: {aggregate}")


def _compare(measured: Any, operator: str, rule: dict) -> bool:
    expected = rule.get("expected")
    threshold = rule.get("threshold")
    if operator == "eq":
        return measured == expected
    if operator == "ne":
        return measured != expected
    if operator == "le":
        return measured is not None and float(measured) <= float(threshold)
    if operator == "lt":
        return measured is not None and float(measured) < float(threshold)
    if operator == "ge":
        return measured is not None and float(measured) >= float(threshold)
    if operator == "gt":
        return measured is not None and float(measured) > float(threshold)
    if operator == "in":
        return measured in expected
    if operator == "all_in":
        if not isinstance(measured, list):
            return False
        return all(value in expected for value in measured)
    raise ValueError(f"unsupported operator: {operator}")


def _rule_blocking(rule: dict, groups: dict[str, dict]) -> bool:
    if "blocking" in rule:
        return bool(rule["blocking"])
    group = groups.get(rule.get("group_id"), {})
    return bool(group.get("default_blocking", True))


def _rule_severity(rule: dict, groups: dict[str, dict]) -> str:
    if rule.get("severity"):
        return str(rule["severity"])
    group = groups.get(rule.get("group_id"), {})
    return str(group.get("default_severity", "blocker"))


def _evaluate_rule(rule: dict, groups: dict[str, dict], sources: dict[str, dict]) -> dict:
    source_name = rule["extractor"]
    values = _path_values(sources[source_name], rule["metric_path"])
    measured = _aggregate(values, rule.get("aggregate", "value"))
    operator = rule.get("operator", "eq")
    passed = _compare(measured, operator, rule)
    return {
        "rule_id": rule["rule_id"],
        "group_id": rule["group_id"],
        "feature_type": rule.get("feature_type"),
        "extractor": source_name,
        "metric_path": rule["metric_path"],
        "aggregate": rule.get("aggregate", "value"),
        "operator": operator,
        "expected": rule.get("expected"),
        "threshold": rule.get("threshold"),
        "unit": rule.get("unit"),
        "blocking": _rule_blocking(rule, groups),
        "severity": _rule_severity(rule, groups),
        "passed": bool(passed),
        "measured": measured,
        "raw_values": values,
        "source_requirement": groups.get(rule["group_id"], {}).get("source_requirement"),
        "failure_message": None if passed else rule.get("failure_message"),
    }


def _connect(db_path: Path):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))


def _create_schema(con) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS rule_catalogs (
            catalog_id VARCHAR,
            catalog_version VARCHAR,
            schema VARCHAR,
            description VARCHAR,
            paper_title VARCHAR,
            paper_doi VARCHAR,
            synced_at TIMESTAMP,
            catalog_json JSON,
            PRIMARY KEY (catalog_id, catalog_version)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS rule_profiles (
            catalog_id VARCHAR,
            catalog_version VARCHAR,
            profile_id VARCHAR,
            description VARCHAR,
            enabled_group_ids_json JSON,
            PRIMARY KEY (catalog_id, catalog_version, profile_id)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS rule_groups (
            catalog_id VARCHAR,
            catalog_version VARCHAR,
            group_id VARCHAR,
            default_severity VARCHAR,
            default_blocking BOOLEAN,
            review_status VARCHAR,
            source_requirement VARCHAR,
            group_json JSON,
            PRIMARY KEY (catalog_id, catalog_version, group_id)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS rules (
            catalog_id VARCHAR,
            catalog_version VARCHAR,
            rule_id VARCHAR,
            group_id VARCHAR,
            feature_type VARCHAR,
            extractor VARCHAR,
            metric_path VARCHAR,
            aggregate VARCHAR,
            operator VARCHAR,
            expected_json JSON,
            threshold DOUBLE,
            unit VARCHAR,
            severity VARCHAR,
            blocking BOOLEAN,
            enabled BOOLEAN,
            failure_message VARCHAR,
            rule_json JSON,
            PRIMARY KEY (catalog_id, catalog_version, rule_id)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS validation_runs (
            run_id VARCHAR PRIMARY KEY,
            catalog_id VARCHAR,
            catalog_version VARCHAR,
            profile_id VARCHAR,
            started_at TIMESTAMP,
            passed BOOLEAN,
            failed_count INTEGER,
            blocking_failed_count INTEGER,
            input_json JSON
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS rule_results (
            run_id VARCHAR,
            rule_id VARCHAR,
            group_id VARCHAR,
            passed BOOLEAN,
            blocking BOOLEAN,
            severity VARCHAR,
            measured_json JSON,
            threshold_json JSON,
            detail_json JSON
        )
        """
    )


def _catalog_ids(catalog: dict) -> tuple[str, str]:
    return str(catalog["catalog_id"]), str(catalog.get("catalog_version", "unversioned"))


def _sync_catalog(con, catalog: dict) -> None:
    _create_schema(con)
    catalog_id, catalog_version = _catalog_ids(catalog)
    paper = catalog.get("paper_inspiration", {})
    con.execute(
        "DELETE FROM rule_catalogs WHERE catalog_id=? AND catalog_version=?",
        [catalog_id, catalog_version],
    )
    con.execute(
        """
        INSERT INTO rule_catalogs VALUES (?, ?, ?, ?, ?, ?, ?, ?::JSON)
        """,
        [
            catalog_id,
            catalog_version,
            catalog.get("schema"),
            catalog.get("description"),
            paper.get("title"),
            paper.get("doi"),
            _now_iso(),
            json.dumps(catalog, ensure_ascii=False),
        ],
    )
    for table in ("rule_profiles", "rule_groups", "rules"):
        con.execute(
            f"DELETE FROM {table} WHERE catalog_id=? AND catalog_version=?",
            [catalog_id, catalog_version],
        )
    for profile in catalog.get("profiles", []):
        con.execute(
            "INSERT INTO rule_profiles VALUES (?, ?, ?, ?, ?::JSON)",
            [
                catalog_id,
                catalog_version,
                profile["profile_id"],
                profile.get("description"),
                json.dumps(profile.get("enabled_group_ids", []), ensure_ascii=False),
            ],
        )
    groups = _group_by_id(catalog)
    for group in catalog.get("groups", []):
        con.execute(
            "INSERT INTO rule_groups VALUES (?, ?, ?, ?, ?, ?, ?, ?::JSON)",
            [
                catalog_id,
                catalog_version,
                group["group_id"],
                group.get("default_severity"),
                bool(group.get("default_blocking", True)),
                group.get("review_status"),
                group.get("source_requirement"),
                json.dumps(group, ensure_ascii=False),
            ],
        )
    for rule in catalog.get("rules", []):
        con.execute(
            """
            INSERT INTO rules VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?::JSON, ?, ?, ?, ?, ?, ?, ?::JSON
            )
            """,
            [
                catalog_id,
                catalog_version,
                rule["rule_id"],
                rule["group_id"],
                rule.get("feature_type"),
                rule.get("extractor"),
                rule.get("metric_path"),
                rule.get("aggregate", "value"),
                rule.get("operator", "eq"),
                json.dumps(rule.get("expected"), ensure_ascii=False),
                rule.get("threshold"),
                rule.get("unit"),
                _rule_severity(rule, groups),
                _rule_blocking(rule, groups),
                bool(rule.get("enabled", True)),
                rule.get("failure_message"),
                json.dumps(rule, ensure_ascii=False),
            ],
        )


def _store_run(con, catalog: dict, profile_id: str, result: dict) -> None:
    _create_schema(con)
    catalog_id, catalog_version = _catalog_ids(catalog)
    con.execute(
        """
        INSERT INTO validation_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?::JSON)
        """,
        [
            result["run_id"],
            catalog_id,
            catalog_version,
            profile_id,
            result["started_at"],
            bool(result["passed"]),
            int(result["failed_count"]),
            int(result["blocking_failed_count"]),
            json.dumps(result["inputs"], ensure_ascii=False),
        ],
    )
    for item in result["rule_results"]:
        con.execute(
            """
            INSERT INTO rule_results VALUES (?, ?, ?, ?, ?, ?, ?::JSON, ?::JSON, ?::JSON)
            """,
            [
                result["run_id"],
                item["rule_id"],
                item["group_id"],
                bool(item["passed"]),
                bool(item["blocking"]),
                item["severity"],
                json.dumps(item.get("measured"), ensure_ascii=False),
                json.dumps({"threshold": item.get("threshold"), "expected": item.get("expected")}, ensure_ascii=False),
                json.dumps(item, ensure_ascii=False),
            ],
        )


def _inspect_db(db_path: Path) -> dict:
    with _connect(db_path) as con:
        _create_schema(con)
        tables = [
            "rule_catalogs",
            "rule_profiles",
            "rule_groups",
            "rules",
            "validation_runs",
            "rule_results",
        ]
        counts = {
            table: int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in tables
        }
        recent_runs = con.execute(
            """
            SELECT run_id, profile_id, passed, failed_count, blocking_failed_count, started_at
            FROM validation_runs
            ORDER BY started_at DESC
            LIMIT 5
            """
        ).fetchall()
    return {
        "db": str(db_path),
        "counts": counts,
        "recent_runs": [
            {
                "run_id": row[0],
                "profile_id": row[1],
                "passed": bool(row[2]),
                "failed_count": int(row[3]),
                "blocking_failed_count": int(row[4]),
                "started_at": str(row[5]),
            }
            for row in recent_runs
        ],
    }


def _run(
    catalog_path: Path = DEFAULT_CATALOG,
    profile_id: str = "candidate_preservation",
    candidate_translate: tuple[float, float, float] = (0.0, 0.0, 0.0),
    preservation_samples: int = 500,
    db_path: Path | None = None,
    sync_db: bool = False,
    store_run: bool = False,
) -> tuple[int, dict]:
    catalog = _load_catalog(catalog_path)
    groups = _group_by_id(catalog)
    rules = _selected_rules(catalog, profile_id)
    sources = _extract_sources(
        [rule["extractor"] for rule in rules],
        candidate_translate=candidate_translate,
        preservation_samples=preservation_samples,
    )
    rule_results = [_evaluate_rule(rule, groups, sources) for rule in rules]
    failed = [item for item in rule_results if not item["passed"]]
    blocking_failed = [item for item in failed if item["blocking"]]
    result = {
        "schema": "validation-rule-run/v0",
        "run_id": str(uuid.uuid4()),
        "started_at": _now_iso(),
        "catalog": {
            "path": str(catalog_path),
            "catalog_id": catalog.get("catalog_id"),
            "catalog_version": catalog.get("catalog_version"),
            "paper_inspiration": catalog.get("paper_inspiration"),
        },
        "profile_id": profile_id,
        "inputs": {
            "candidate_translate_mm": [float(x) for x in candidate_translate],
            "preservation_samples": int(preservation_samples),
        },
        "passed": len(blocking_failed) == 0,
        "failed_count": len(failed),
        "blocking_failed_count": len(blocking_failed),
        "rule_results": rule_results,
        "failed_rules": [
            {
                "rule_id": item["rule_id"],
                "group_id": item["group_id"],
                "blocking": item["blocking"],
                "measured": item["measured"],
                "threshold": item.get("threshold"),
                "expected": item.get("expected"),
                "failure_message": item.get("failure_message"),
            }
            for item in failed
        ],
    }
    if db_path is not None and (sync_db or store_run):
        with _connect(db_path) as con:
            if sync_db or store_run:
                _sync_catalog(con, catalog)
            if store_run:
                _store_run(con, catalog, profile_id, result)
        result["duckdb"] = _inspect_db(db_path)
    code = 0 if result["passed"] else 2
    return code, result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--profile", default="candidate_preservation")
    parser.add_argument("--candidate-translate", type=_parse_vec3, default=(0.0, 0.0, 0.0))
    parser.add_argument("--preservation-samples", type=int, default=500)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--sync-db", action="store_true")
    parser.add_argument("--store-run", action="store_true")
    parser.add_argument("--inspect-db", action="store_true")
    parser.add_argument("--fail-on-blocking", action="store_true")
    args = parser.parse_args(argv)

    if args.inspect_db:
        print(json.dumps(_inspect_db(args.db), indent=2, ensure_ascii=False))
        return 0

    code, result = _run(
        catalog_path=args.catalog,
        profile_id=args.profile,
        candidate_translate=args.candidate_translate,
        preservation_samples=args.preservation_samples,
        db_path=args.db,
        sync_db=args.sync_db,
        store_run=args.store_run,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return code if args.fail_on_blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
