"""Offline research audit. Only aggregate counts/errors are printed; no files are written."""

import argparse
import ast
import csv
import json
from pathlib import Path

import numpy as np
from medplatform.profile.cas_review import (
    FREQUENCY,
    research_group,
    score,
    valid_field,
)
from medplatform.profile.mapped_review import FIELDS, SPEC


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def literals(script):
    result = {}
    for node in ast.parse(script.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try:
                result[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError, TypeError:
                continue
    return result


def audit(clean, archive, script):
    config = literals(script)
    if config["freq_map"] != FREQUENCY:
        raise ValueError("原脚本频率映射与本版不一致")
    raw = read_rows(clean)
    archived = read_rows(archive)
    by_id = {row["作答ID"]: row for row in archived}
    ids = {row["作答ID"] for row in raw}
    if len(ids) != len(raw) or len(by_id) != len(archived) or ids != by_id.keys():
        raise ValueError("历史表不能一对一配对")
    source = [
        {code: r[header] for header, code in config["COL_MAP"].items()} for r in raw
    ]
    reference = [by_id[r["作答ID"]] for r in raw]

    requirement_conflicts = 0
    for original, renamed in zip(raw, source, strict=True):
        for group, fields in FIELDS.items():
            if group == "Q4":  # The new direct evidence was never collected.
                continue
            for key, field in fields.items():
                if key == "special_requirements":
                    value = [
                        o["code"]
                        for o in field["options"]
                        if float(renamed[o["code"]] or 0) == 1
                    ]
                elif key == "stable_experience":
                    value = original[field["prompt"]]
                elif field["kind"] == "scale":
                    value = int(renamed[key])
                else:
                    value = renamed[key]
                if (
                    key == "special_requirements"
                    and "req_none" in value
                    and len(value) > 1
                ):
                    # The archive counted the selected specific requirements.
                    # Keep the original record, but flag it under the new form rules.
                    requirement_conflicts += 1
                    continue
                if not valid_field(field, value):
                    raise ValueError(f"{group}.{key} 历史输入与采集选项不一致")

    values = [
        score(int(r["knowledge"]), r["adherence_freq"], int(r["difficulty"]))
        for r in source
    ]
    matches = sum(v == float(r["CAS"]) for v, r in zip(values, reference, strict=True))
    predictor = SPEC["original_predictor"]
    projection = predictor["factor_projection"]
    if config["scale_features"] != projection["source_inputs"]:
        raise ValueError("原始量表项顺序不一致")
    scale = np.array(
        [[int(r[k]) for k in config["scale_features"]] for r in source], dtype=float
    )
    factors = (scale - projection["center"]) @ np.asarray(
        projection["components_input_by_output"]
    )

    def complexity_parts(row):
        requirements = sum(int(float(row[k] or 0)) for k in config["req_cols"])
        if not requirements and row["req_none"] not in ("1", "1.0"):
            raise ValueError("历史记录未明确特殊要求是否为零")
        return [
            config["drug_count_map"][row["drug_count"]],
            config["drug_freq_map"][row["drug_freq"]],
            requirements,
        ]

    parts = np.array([complexity_parts(r) for r in source], dtype=float)
    complexity = (
        (parts - predictor["complexity"]["mean"]) / predictor["complexity"]["std"]
    ).sum(axis=1)
    drug_cols = [k for k in archived[0] if k.startswith("drug_")]
    factor_cols = [
        "F1_adherence_resistance",
        "F2_burden_perception",
        "F3_lifestyle_regularity",
    ]
    order = [
        "age",
        "gender",
        "income",
        "live_alone",
        "duration",
        "complexity_z",
        "social_support",
        "followup",
        *drug_cols,
        *factor_cols,
        *config["scale_features"][-3:],
    ]
    if (
        order != predictor["ordered_feature_names"]
        or order != predictor["deep_learning_standard_scaler"]["ordered_feature_names"]
        or len(order) != 21
    ):
        raise ValueError("历史特征维度不匹配")

    def vector(i, r):
        if r["drug_type"] != "其他" and "drug_" + r["drug_type"] not in drug_cols:
            raise ValueError("历史药类未知")
        return [
            config["age_map"][r["age"]],
            {"男": 1, "女": 0}[r["gender"]],
            config["income_map"][r["income"]],
            int(r["living"] == "独居"),
            config["duration_map"][r["drug_duration"]],
            complexity[i],
            config["support_map"][r["social_support"]],
            config["followup_map"][r["followup"]],
            *[int("drug_" + r["drug_type"] == k) for k in drug_cols],
            *factors[i],
            *scale[i, -3:],
        ]

    actual = np.array([vector(i, r) for i, r in enumerate(source)])
    numeric_bool = {"True": "1", "False": "0"}
    expected = np.array(
        [[float(numeric_bool.get(r[k], r[k])) for k in order] for r in reference]
    )
    # Reconstruct the historical whole-sample scaler for comparison only.
    mean, std = expected.mean(axis=0), expected.std(axis=0)

    frozen = predictor["deep_learning_standard_scaler"]
    actual_scaled = ((actual - frozen["mean"]) / frozen["scale"]).astype(np.float32)
    expected_scaled = ((expected - mean) / std).astype(np.float32)
    error = float(np.abs(actual - expected).max())
    scaled_matches = int(np.all(actual_scaled == expected_scaled, axis=1).sum())
    print(
        json.dumps(
            {
                "rows": len(raw),
                "observed_matches": matches,
                "groups": {
                    g: sum(research_group(v) == g for v in values)
                    for g in ("low", "middle", "high")
                },
                "feature_count": len(order),
                "conflicting_requirement_rows": requirement_conflicts,
                "max_abs_error": error,
                "float32_row_matches": scaled_matches,
            },
            ensure_ascii=False,
        )
    )
    return matches == len(raw) and error < 1e-10 and scaled_matches == len(raw)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("clean", "archive", "script"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    raise SystemExit(0 if audit(args.clean, args.archive, args.script) else 1)
