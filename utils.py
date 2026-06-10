import pandas as pd
import numpy as np
import streamlit as st

CORE_COLUMNS = ["Address (style code)", "ID", "Status", "N'hood", "List $", "Sell $", "BR", "BA", "ASF"]
OPTIONAL_COLUMNS = ["2026 TAV", "List as % of TAV", "Sale as % of TAV", "Equiv $$ vs TAV %", "CDOM", "Prk", "LSF", "YBT", "Dist", "Close Date", "Note"]


def load_excel(file) -> pd.DataFrame:
    return pd.read_excel(file, engine="openpyxl")


def validate_columns(df: pd.DataFrame) -> tuple[bool, list[str], list[str]]:
    missing_core = [c for c in CORE_COLUMNS if c not in df.columns]
    missing_opt = [c for c in OPTIONAL_COLUMNS if c not in df.columns]
    return len(missing_core) == 0, missing_core, missing_opt


def parse_price(val):
    if pd.isna(val):
        return np.nan
    val_str = str(val).replace("$", "").replace(",", "").strip()
    if "was" in val_str.lower():
        val_str = val_str.split("was")[0].strip()
    try:
        return float(val_str)
    except ValueError:
        return np.nan


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["List $"] = df["List $"].apply(parse_price)
    df["List $"] = pd.to_numeric(df["List $"], errors="coerce")

    if "Sell $" in df.columns:
        df["Sell $"] = df["Sell $"].apply(parse_price)
        df["Sell $"] = pd.to_numeric(df["Sell $"], errors="coerce")

    for col in ["CDOM", "BA", "LSF", "Dist"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in ["BR", "PRK", "Prk", "ASF", "YBT"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    if "Close Date" in df.columns:
        df["Close Date"] = pd.to_datetime(df["Close Date"], errors="coerce")

    # Add derived columns
    df["$/sqft"] = np.where(df["ASF"] > 0, df["List $"] / df["ASF"], np.nan)
    if "Sell $" in df.columns:
        df["Sold $/sqft"] = np.where(df["ASF"] > 0, df["Sell $"] / df["ASF"], np.nan)

    if "LSF" in df.columns:
        df["$/sqft_lot"] = np.where(df["LSF"] > 0, df["List $"] / (df["LSF"] * 43560), np.nan)

    return df


def get_subject(df: pd.DataFrame):
    subjects = df[df["Status"] == "Subject"]
    if len(subjects) == 0:
        return None
    return subjects.iloc[0]


def get_comps(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["Status"] != "Subject"]


def find_subject_column(df: pd.DataFrame, candidate_cols: list[str]):
    for col in candidate_cols:
        if col in df.columns:
            return df[col]
    return None


@st.cache_data
def load_sample_data() -> pd.DataFrame:
    """Load the built-in sample data from the repo root."""
    import os
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(repo_root, "RealEstateComps.xlsx")
    if os.path.exists(path):
        df = load_excel(path)
        return clean_data(df)
    return pd.DataFrame()
