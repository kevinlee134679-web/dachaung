from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import torch
from torch import nn

from .cas_questionnaire import SPEC

MODEL_INPUTS = {
    "stable_experience": "stable_use",
    "special_requirements": "requirements",
}


class MultiHeadAttentionMLP(nn.Module):
    def __init__(self, n_features, hidden=48, dropout=0.25, n_heads=4):
        super().__init__()
        head_dim = max(4, n_features // n_heads)
        self.attn_heads = nn.ModuleList(
            [
                nn.Sequential(
                    nn.Linear(n_features, head_dim),
                    nn.GELU(),
                    nn.Linear(head_dim, n_features),
                )
                for _ in range(n_heads)
            ]
        )
        self.attn_combine = nn.Sequential(
            nn.Linear(n_features * n_heads, n_features), nn.Softmax(dim=-1)
        )
        self.fc1 = nn.Linear(n_features, hidden)
        self.bn1 = nn.BatchNorm1d(hidden)
        self.dropout = nn.Dropout(dropout)
        self.fc2 = nn.Linear(hidden, 1)

    def forward(self, x):
        head_outputs = torch.cat([head(x) for head in self.attn_heads], dim=-1)
        attn_w = self.attn_combine(head_outputs)
        x_w = x * attn_w
        h = self.dropout(torch.relu(self.bn1(self.fc1(x_w))))
        return self.fc2(h).squeeze(-1)


class Ensemble(nn.Module):
    def __init__(self, members):
        super().__init__()
        self.members = nn.ModuleList(members)

    def forward(self, x):
        return torch.stack([member(x) for member in self.members]).mean(0)


def encode(answers, preprocessing) -> np.ndarray:
    codes = preprocessing["category_codes"]
    c = {field: allowed[answers[field]] for field, allowed in codes.items()}
    drug = answers["drug_type"]
    drugs = preprocessing["drug_columns"]
    requirements = answers["requirements"]
    parts = {
        "drug_count": c["drug_count"],
        "drug_freq": c["drug_freq"],
        "req_count": 0
        if requirements == [preprocessing["no_requirements"]]
        else len(requirements),
    }
    base = np.array([parts[k] for k in preprocessing["complexity_order"]], dtype=float)
    complexity = (
        (base - preprocessing["complexity_mean"])
        / preprocessing["complexity_sample_std"]
    ).sum()
    items = [answers[k] for k in preprocessing["scale_order"]]
    scores = (np.asarray(items) - preprocessing["pca_center"]) @ np.asarray(
        preprocessing["pca_projection"]
    )
    features = {
        "age": c["age"],
        "gender": c["gender"],
        "income": c["income"],
        "live_alone": c["living"],
        "duration": c["drug_duration"],
        "complexity_z": complexity,
        "social_support": c["social_support"],
        "followup": c["followup"],
        **{col: int(col == f"drug_{drug}") for col in drugs},
        **dict(zip(preprocessing["factor_names"], scores, strict=True)),
        **{k: answers[k] for k in ("self_efficacy", "tech_accept", "health_literacy")},
    }
    vector = np.asarray(
        [features[k] for k in preprocessing["feature_order"]], dtype=float
    )
    return (
        (vector - preprocessing["scaler_mean"]) / preprocessing["scaler_scale"]
    ).astype(np.float32)


class CasModel:
    def __init__(self, preprocessing, model):
        self.preprocessing = preprocessing
        self.model_version = preprocessing["version"]
        self.model = model

    @classmethod
    def load(cls, folder: Path) -> CasModel:
        preprocessing = json.loads((folder / "preprocessing.json").read_text("utf-8"))
        torch.set_num_threads(1)
        with (folder / "ensemble.pt").open("rb") as stream:
            checkpoint = torch.load(stream, map_location="cpu", weights_only=True)
        model = Ensemble(
            [
                MultiHeadAttentionMLP(checkpoint["input_size"])
                for _ in checkpoint["seeds"]
            ]
        )
        model.load_state_dict(checkpoint["state_dict"], strict=True)
        return cls(preprocessing, model.eval())

    def predict(self, response) -> dict:
        result = {
            "status": "insufficient",
            "value": None,
            "model_version": self.model_version,
            "reason": None,
        }
        if response["respondent_mode"] != "self":
            return {**result, "reason": "研究模型需要本人填写 Q5–Q8。"}
        answers = response["answers"]
        if answers["Q8"]["value"].get("stable_experience") == "否":
            return {
                **result,
                "reason": "Q8 回答无稳定用药经历，超出此研究模型的适用范围。",
            }
        raw = {}
        missing = []
        for theme in SPEC["themes"][4:]:
            question = theme["question_id"]
            values = answers[question]["value"]
            if any(
                values.get(field["key"]) in (None, "unknown", [])
                for field in theme["fields"]
            ):
                missing.append(question)
            raw.update(
                {MODEL_INPUTS.get(key, key): value for key, value in values.items()}
            )
        if missing:
            return {**result, "reason": "预测所需补充项：" + "、".join(missing)}
        inputs = encode(raw, self.preprocessing)
        with torch.inference_mode():
            value = self.model(torch.from_numpy(inputs[None, :])).item()
        return {**result, "status": "estimated", "value": value}
