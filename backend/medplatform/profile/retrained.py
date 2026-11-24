"""Local research prediction from the explicitly selected, verified model release."""

import hashlib
import json
import math

from ..core.errors import AppError
from . import mapped_review

MODEL = "cas-dl2-retrain-20261124"
PREPROCESSING = "cas-dl2-preprocessing-20261124-9a34dc48"
METHOD = "observed-barrier-demo-and-retrained-cas-v1"
HASHES = {
    "preprocessing.json": "9a34dc489fa29abcf8cb31d4453453906b25bc0bdc7fbe876b8b1d224c6ad081",
    "ensemble.pt": "31665b76184babb0d36622790bb44f9dad9cddc9aa2f3732cad71655f9931314",
    "reference_cases.json": "6e19e8e425b0fc1b3957fe8084778ecbec458c9dbc8f8df7401f5713ce76a2ab",
}
ALIASES = {"stable_experience": "stable_use", "special_requirements": "requirements"}


class Predictor:
    def __init__(self, frozen, model, runtime):
        self.frozen = frozen
        self.model = model
        self.runtime = runtime

    @classmethod
    def load(cls, folder):
        try:
            for name, expected in HASHES.items():
                with (folder / name).open("rb") as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                        raise ValueError(name)
            from . import retrained_runtime as runtime

            frozen = json.loads((folder / "preprocessing.json").read_text("utf-8"))
            runtime.torch.set_num_threads(1)
            model = runtime.restore_model(folder / "ensemble.pt")
            with runtime.torch.inference_mode():
                runtime.verify(folder, frozen, model)
            return cls(frozen, model, runtime)
        except (OSError, ImportError, ValueError, AssertionError, RuntimeError) as exc:
            raise AppError(
                503,
                "CAS_BUNDLE_INVALID",
                "CAS 重训包启动校验失败，请核对依赖、权重、冻结参数和四个对照样例",
            ) from exc

    def assess(self, response):
        result = {
            "status": "insufficient",
            "value": None,
            "model_version": MODEL,
            "preprocessing_version": PREPROCESSING,
            "reason": None,
        }
        if response["respondent_mode"] != "self":
            return {**result, "reason": "研究模型需要本人填写 Q5–Q8。"}
        raw = {}
        missing = []
        for q in ("Q5", "Q6", "Q7", "Q8"):
            answer = response["answers"][q]
            if answer["state"] != "answered":
                missing.append(q + " " + mapped_review.THEMES[int(q[1:]) - 1]["prompt"])
                continue
            values = answer["value"]
            for key, field in mapped_review.FIELDS[q].items():
                if key in values:
                    raw[ALIASES.get(key, key)] = values[key]
                else:
                    missing.append(q + " " + field["prompt"])
        if raw.get("stable_use") == "否":
            return {
                **result,
                "reason": "Q8 回答无稳定用药经历，超出此研究模型的适用范围。",
            }
        if missing:
            return {**result, "reason": "预测所需补充项：" + "、".join(missing)}
        try:
            runtime = self.runtime
            _, inputs = runtime.encode(raw, self.frozen)
            with runtime.torch.inference_mode():
                value = self.model(runtime.torch.from_numpy(inputs[None, :])).item()
            if not math.isfinite(value):
                raise ValueError("non-finite prediction")
        except ValueError, RuntimeError:
            return {
                **result,
                "status": "unavailable",
                "reason": "本次模型计算失败，可重新生成画像。",
            }
        return {**result, "status": "estimated", "value": value}
