"""Normalize financial values imported from provider exports."""

import re

import pandas as pd


def normalize_header(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()


def normalize_company(value: object) -> str:
    normalized = normalize_header(value)
    normalized = re.sub(r"\b(limited|ltd|private|pvt|company|co)\b", "", normalized)
    return " ".join(normalized.split())


def number(value: object) -> float:
    if pd.isna(value):
        return float("nan")
    text = str(value).replace(",", "").replace("%", "").strip()
    if text in ("", "-", "--", "NA", "N/A"):
        return float("nan")
    try:
        return float(text)
    except ValueError:
        return float("nan")
