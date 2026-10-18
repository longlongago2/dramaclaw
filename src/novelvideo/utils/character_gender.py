"""Normalize gender labels returned by the two character extraction pipelines."""

from typing import Annotated, Literal

from pydantic import BeforeValidator


def normalize_character_gender(value: object) -> str:
    if value is not None and not isinstance(value, str):
        raise ValueError("Character gender must be a string")
    original = str(value or "").strip()
    label = original.casefold()
    if label in {"male", "m", "man", "boy", "男", "男性", "男生", "雄", "雄性", "公"}:
        return "male"
    if label in {"female", "f", "woman", "girl", "女", "女性", "女生", "雌", "雌性", "母"}:
        return "female"
    if label in {"agender", "genderless", "无性别"}:
        return "agender"
    if label in {"non_binary", "non-binary", "nonbinary", "非二元", "非二元性别"}:
        return "non_binary"
    if label in {"", "unknown", "unspecified", "未设定", "未知", "不明", "不详", "未说明", "性别不明", "性别不明确", "无性别设定"}:
        return ""
    # Preserve unrecognized legacy labels; the Literal validates new API/LLM
    # writes instead of silently replacing unsupported input with an empty value.
    return original


CharacterGender = Annotated[
    Literal["male", "female", "agender", "non_binary", ""], BeforeValidator(normalize_character_gender)
]
