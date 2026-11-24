"""CPU inference port of the verified cas-dl2-retrain-20261124 research bundle."""

import json

import numpy as np
import torch
from torch import nn


class MultiHeadAttentionMLP(nn.Module):
    """
    Multi-Head Attention + MLP
    - n_heads个并行注意力头，各自学习不同的特征交互模式
    - 合并后通过可学习线性层+Softmax生成最终特征权重
    - 1隐层MLP进行非线性变换
    """

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

    def forward(self, x, return_attention=False):
        head_outputs = torch.cat([head(x) for head in self.attn_heads], dim=-1)
        attn_w = self.attn_combine(head_outputs)
        x_w = x * attn_w
        h = self.dropout(torch.relu(self.bn1(self.fc1(x_w))))
        out = self.fc2(h).squeeze(-1)
        if return_attention:
            return out, attn_w
        return out


class Ensemble(nn.Module):
    def __init__(self, members):
        super().__init__()
        self.members = nn.ModuleList(members)

    def forward(self, x):
        return torch.stack([member(x) for member in self.members]).mean(0)


def restore_model(path):
    with path.open("rb") as stream:
        checkpoint = torch.load(stream, map_location="cpu", weights_only=True)
    model = Ensemble(
        [MultiHeadAttentionMLP(checkpoint["input_size"]) for _ in checkpoint["seeds"]]
    )
    model.load_state_dict(checkpoint["state_dict"], strict=True)
    return model.eval()


class InputError(ValueError):
    """A questionnaire input is missing, unsupported or internally inconsistent."""


def encode(raw, frozen):
    if not isinstance(raw, dict):
        raise InputError("需要一份 Q5–Q8 原始答案对象")
    if raw.get("stable_use") != frozen["eligibility"]["stable_use"]:
        raise InputError("缺少符合原研究范围的稳定用药经历")
    codes = frozen["category_codes"]
    fields = (
        set(codes)
        | set(frozen["scale_order"])
        | {"stable_use", "drug_type", "requirements"}
    )
    if set(raw) != fields:
        raise InputError(
            "请核对字段，缺少："
            + ", ".join(sorted(fields - set(raw)))
            + "；多出："
            + ", ".join(sorted(set(raw) - fields))
        )
    c = {}
    for field, allowed in codes.items():
        value = raw[field]
        if not isinstance(value, str) or value not in allowed:
            raise InputError(f"{field} 需要有效的原问卷选项")
        c[field] = allowed[value]
    drug = raw["drug_type"]
    drugs = frozen["drug_columns"]
    if not isinstance(drug, str) or (
        drug != frozen["other_drug"] and f"drug_{drug}" not in drugs
    ):
        raise InputError("drug_type 未知")
    req = raw["requirements"]
    none = frozen["no_requirements"]
    allowed = [*frozen["requirements"], none]
    if (
        not isinstance(req, list)
        or not req
        or any(not isinstance(r, str) or r not in allowed for r in req)
        or len(req) != len(set(req))
        or (none in req and len(req) > 1)
    ):
        raise InputError("requirements 缺失、重复或互斥")
    n_req = 0 if req == [none] else len(req)
    parts = {
        "drug_count": c["drug_count"],
        "drug_freq": c["drug_freq"],
        "req_count": n_req,
    }
    base = np.array([parts[k] for k in frozen["complexity_order"]], dtype=float)
    complexity = (
        (base - frozen["complexity_mean"]) / frozen["complexity_sample_std"]
    ).sum()
    items = [raw[k] for k in frozen["scale_order"]]
    if any(type(n) is not int or not 1 <= n <= 5 for n in items):
        raise InputError("14 个原量表项均需填写 1–5 的整数")
    scores = (np.asarray(items) - frozen["pca_center"]) @ np.asarray(
        frozen["pca_projection"]
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
        **dict(zip(frozen["factor_names"], scores, strict=True)),
        **{k: raw[k] for k in ("self_efficacy", "tech_accept", "health_literacy")},
    }
    vector = np.asarray([features[k] for k in frozen["feature_order"]], dtype=float)
    scaled = ((vector - frozen["scaler_mean"]) / frozen["scaler_scale"]).astype(
        np.float32
    )
    return vector, scaled


def verify(folder, frozen, model):
    cases = json.loads((folder / "reference_cases.json").read_text(encoding="utf-8"))
    for case in cases:
        vector, scaled = encode(case["input"], frozen)
        np.testing.assert_allclose(
            vector, case["expected_features"], rtol=0, atol=1e-10
        )
        np.testing.assert_array_equal(
            scaled, np.array(case["expected_scaled_float32"], dtype=np.float32)
        )
        observed = model(torch.from_numpy(scaled[None, :])).item()
        np.testing.assert_allclose(
            observed, case["expected_prediction"], rtol=0, atol=1e-5
        )
