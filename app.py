import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils import load_excel, validate_columns, clean_data, load_sample_data

st.set_page_config(page_title="Real Estate Comps Dashboard", page_icon="🏠", layout="wide")
st.title("🏠 Real Estate Comps Dashboard")
st.caption("Upload comps Excel → select a metric → compare subject vs. other properties")

# ── File upload ──
uploaded = st.file_uploader("Upload comps Excel (.xlsx)", type=["xlsx"], label_visibility="collapsed")
if uploaded:
    try:
        df_raw = load_excel(uploaded)
        ok, missing, _ = validate_columns(df_raw)
        if not ok:
            st.error(f"Missing columns: {', '.join(missing)}")
            st.info("Expected: Address (style code), ID, Status, N'hood, List $, Sell $, BR, BA, ASF")
            st.stop()
        st.session_state["df"] = clean_data(df_raw)
        st.session_state["src"] = "uploaded"
    except Exception as e:
        st.error(f"Read error: {e}")
        st.stop()
elif "df" not in st.session_state:
    st.session_state["df"] = load_sample_data()
    st.session_state["src"] = "sample"

df = st.session_state["df"]
if df is None or df.empty:
    st.info("No data. Upload an Excel file to begin.")
    st.stop()

subjects = df[df["Status"] == "Subject"]
if subjects.empty:
    st.error("No row with Status = 'Subject'. Set one row's Status to 'Subject'.")
    st.stop()

subject = subjects.iloc[0]
comps = df[df["Status"] != "Subject"]

# ── Detect numeric columns usable as comparison metrics ──
METRIC_LABELS = {
    "List $":       "List Price ($)",
    "Sell $":       "Sale Price ($)",
    "$/sqft":       "$ per sqft",
    "Sold $/sqft":  "Sold $ per sqft",
    "List as % of TAV": "List % of TAV",
    "Sale as % of TAV": "Sale % of TAV",
    "Equiv $$ vs TAV %": "Equiv $$ vs TAV %",
    "CDOM":         "Days on Market",
    "BR":           "Bedrooms",
    "BA":           "Bathrooms",
    "ASF":          "Above-Grade Sqft",
    "LSF":          "Lot Size (acres)",
    "Prk":          "Parking",
    "YBT":          "Year Built",
    "Dist":         "Distance (mi)",
}
numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
metric_options = {c: METRIC_LABELS.get(c, c) for c in numeric_cols if c != "ID"}
metric_cols = list(metric_options.keys())

# ── Sidebar filters ──
with st.sidebar:
    st.subheader("🔍 Filters")
    available_statuses = sorted(comps["Status"].dropna().unique())
    sel_status = st.multiselect("Status", available_statuses, default=available_statuses)
    if "N'hood" in comps.columns:
        hoods = sorted(comps["N'hood"].dropna().unique())
        sel_hood = st.selectbox("Neighborhood", ["All"] + hoods)
    else:
        sel_hood = "All"
    if "Dist" in comps.columns and pd.notna(comps["Dist"].max()):
        max_d = float(comps["Dist"].max())
        dist_cutoff = st.slider("Max Distance (mi)", 0.0, max_d, max_d, 0.1)
    else:
        dist_cutoff = None
    if "BR" in comps.columns:
        min_br, max_br = int(comps["BR"].min()), int(comps["BR"].max())
        br_range = st.slider("Bedrooms", min_br, max_br, (min_br, max_br))
    else:
        br_range = None

    st.divider()
    st.caption(f"📊 {len(comps)} comps loaded ({st.session_state['src']})")

# Apply filters
c = comps.copy()
if sel_status:
    c = c[c["Status"].isin(sel_status)]
if sel_hood != "All":
    c = c[c["N'hood"] == sel_hood]
if dist_cutoff is not None and "Dist" in c.columns:
    c = c[c["Dist"] <= dist_cutoff]
if br_range is not None and "BR" in c.columns:
    c = c[(c["BR"] >= br_range[0]) & (c["BR"] <= br_range[1])]

comps_f = c

# ── Subject property card ──
st.subheader("🏡 Subject Property")
scols = st.columns(7)
with scols[0]:
    addr = subject.get("Address (style code)", "—")
    st.metric("Address", str(addr)[:25])
with scols[1]:
    st.metric("List Price", f"${subject['List $']:,.0f}" if pd.notna(subject.get("List $")) else "—")
with scols[2]:
    st.metric("BR", f"{int(subject['BR'])}" if pd.notna(subject.get("BR")) else "—")
with scols[3]:
    st.metric("BA", f"{subject['BA']:.1f}" if pd.notna(subject.get("BA")) else "—")
with scols[4]:
    st.metric("Sqft", f"{int(subject['ASF']):,}" if pd.notna(subject.get("ASF")) else "—")
with scols[5]:
    st.metric("$/sqft", f"${subject['$/sqft']:,.0f}" if pd.notna(subject.get("$/sqft")) else "—")
with scols[6]:
    st.metric("N'hood", str(subject.get("N'hood", "—"))[:20])

st.divider()

# ── Metric selector ──
st.subheader("📊 Compare Subject vs. Comps")
mcol1, mcol2 = st.columns([1, 4])
with mcol1:
    metric_key = st.selectbox("Select metric", metric_cols, format_func=lambda x: metric_options[x], index=0 if "List $" in metric_cols else 0)

# ── Chart row ──
chart_col1, chart_col2 = st.columns(2)

comps_vals = comps_f[metric_key].dropna()
sub_val = subject.get(metric_key)
has_sub = pd.notna(sub_val)

with chart_col1:
    # Box plot + swarm: comps distribution vs subject
    if not comps_vals.empty:
        fig = go.Figure()
        fig.add_trace(go.Box(
            x=comps_vals, name="Comps", orientation="h",
            marker_color="#3498db", boxmean="sd",
            hovertemplate="%{x:,.1f}<extra>Comps</extra>"
        ))
        if has_sub:
            fig.add_trace(go.Scatter(
                x=[sub_val], y=["Comps"], mode="markers",
                marker=dict(size=16, color="#FFD700", symbol="star", line=dict(width=2, color="black")),
                name="Subject", hovertemplate=f"<b>Subject</b><br>{sub_val:,.1f}<extra></extra>"
            ))
        label = metric_options.get(metric_key, metric_key)
        fig.update_layout(title=f"{label} — Distribution", margin=dict(l=10, r=10, t=40, b=10), height=350,
                          xaxis_title=label, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

with chart_col2:
    # Scatter: selected metric vs ASF
    if "ASF" in comps_f.columns and not comps_vals.empty:
        scatter_df = comps_f.dropna(subset=["ASF", metric_key])
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=scatter_df["ASF"], y=scatter_df[metric_key],
            mode="markers", name="Comps",
            marker=dict(size=10, color="#3498db", opacity=0.7),
            text=scatter_df.get("Address (style code)", scatter_df.index),
            hovertemplate="%{text}<br>ASF: %{x:,}<br>" + metric_key + ": %{y:,.1f}<extra></extra>"
        ))
        if has_sub and "ASF" in subject.index and pd.notna(subject.get("ASF")):
            fig.add_trace(go.Scatter(
                x=[subject["ASF"]], y=[sub_val],
                mode="markers",
                marker=dict(size=18, color="#FFD700", symbol="star", line=dict(width=2, color="black")),
                name="Subject",
                hovertemplate=f"<b>Subject</b><br>ASF: {int(subject['ASF']):,}<br>" + metric_key + f": {sub_val:,.1f}<extra></extra>"
            ))
        x_label = "ASF (sqft)"
        y_label = metric_options.get(metric_key, metric_key)
        fig.update_layout(title=f"{y_label} vs {x_label}", height=350,
                          xaxis_title=x_label, yaxis_title=y_label)
        st.plotly_chart(fig, use_container_width=True)

# ── Quick comparison stats ──
if not comps_vals.empty and has_sub:
    st.subheader("📈 Quick Stats")
    kcol1, kcol2, kcol3, kcol4, kcol5 = st.columns(5)
    median = comps_vals.median()
    mean = comps_vals.mean()
    p_min = comps_vals.min()
    p_max = comps_vals.max()
    diff_pct = ((sub_val - median) / median * 100) if median != 0 else 0
    rank = (comps_vals < sub_val).sum()
    total = len(comps_vals)
    label = metric_options.get(metric_key, metric_key)
    with kcol1:
        st.metric(f"Subject {label}", f"{sub_val:,.1f}")
    with kcol2:
        st.metric(f"Comps Median", f"{median:,.1f}", delta=f"{diff_pct:+.1f}% vs subject")
    with kcol3:
        st.metric("Comps Range", f"{p_min:,.1f} — {p_max:,.1f}")
    with kcol4:
        st.metric("Comps Mean ± SD", f"{mean:,.1f} ± {comps_vals.std():,.1f}")
    with kcol5:
        st.metric("Subject Rank", f"#{rank} of {total}", delta=f"top {rank/total*100:.0f}%" if total > 0 else None)

# ── Data table ──
st.divider()
with st.expander(f"📋 Filtered Comps ({len(comps_f)} properties)", expanded=False):
    st.dataframe(comps_f, use_container_width=True, hide_index=True)
    csv = comps_f.to_csv(index=False)
    st.download_button("📥 Download CSV", csv, "filtered_comps.csv", "text/csv")
