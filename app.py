import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from utils import load_excel, validate_columns, clean_data, load_sample_data

st.set_page_config(page_title="Real Estate Comps Dashboard", page_icon="🏠", layout="wide")

# Smaller metric font
st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.2rem; }
[data-testid="stMetricLabel"] { font-size: 0.75rem; }
</style>
""", unsafe_allow_html=True)

st.title("🏠 Real Estate Comps Dashboard")
st.caption("Upload comps Excel → select a metric → compare subject vs. other properties")

STATUS_COLORS = {
    "Active":  "#1B3A5C",
    "Pending": "#2E5B88",
    "Sold":    "#4A7FB5",
    "Subject": "#FFD700",
}

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
        sel_hood = st.multiselect("Neighborhood", hoods, default=hoods)
    else:
        sel_hood = []
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
    if "BA" in comps.columns:
        min_ba, max_ba = float(comps["BA"].min()), float(comps["BA"].max())
        ba_range = st.slider("Bathrooms", min_ba, max_ba, (min_ba, max_ba), 0.5)
    else:
        ba_range = None

    st.divider()
    st.caption(f"📊 {len(comps)} comps loaded ({st.session_state['src']})")

# Apply filters
c = comps.copy()
if sel_status:
    c = c[c["Status"].isin(sel_status)]
if sel_hood:
    c = c[c["N'hood"].isin(sel_hood)]
if dist_cutoff is not None and "Dist" in c.columns:
    c = c[c["Dist"] <= dist_cutoff]
if br_range is not None and "BR" in c.columns:
    c = c[(c["BR"] >= br_range[0]) & (c["BR"] <= br_range[1])]
if ba_range is not None and "BA" in c.columns:
    c = c[(c["BA"] >= ba_range[0]) & (c["BA"] <= ba_range[1])]

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
    if not comps_vals.empty:
        fig = go.Figure()
        fig.add_trace(go.Box(
            x=comps_vals, name="Comps", orientation="h",
            marker_color="#1B3A5C", boxmean="sd",
            hovertemplate="%{x:,.1f}<extra>Comps</extra>"
        ))
        if has_sub:
            fig.add_trace(go.Scatter(
                x=[sub_val], y=["Comps"], mode="markers",
                marker=dict(size=12, color="#FFD700", symbol="star", line=dict(width=1.5, color="black")),
                name="Subject", hovertemplate=f"<b>Subject</b><br>{sub_val:,.1f}<extra></extra>"
            ))
        label = metric_options.get(metric_key, metric_key)
        fig.update_layout(title=f"{label} Distribution", margin=dict(l=10, r=10, t=40, b=10), height=350,
                          xaxis_title=label, showlegend=True, font=dict(size=11))
        st.plotly_chart(fig, use_container_width=True)

with chart_col2:
    if "ASF" in comps_f.columns and not comps_vals.empty:
        scatter_df = comps_f.dropna(subset=["ASF", metric_key])
        fig = go.Figure()
        for status_name in sorted(scatter_df["Status"].dropna().unique()):
            sub_df = scatter_df[scatter_df["Status"] == status_name]
            if not sub_df.empty:
                color = STATUS_COLORS.get(status_name, "#1B3A5C")
                fig.add_trace(go.Scatter(
                    x=sub_df["ASF"], y=sub_df[metric_key],
                    mode="markers", name=status_name,
                    marker=dict(size=10, color=color, opacity=0.85),
                    text=sub_df.get("Address (style code)", sub_df.index),
                    hovertemplate="%{text}<br>ASF: %{x:,}<br>" + metric_options.get(metric_key, metric_key) + ": %{y:,.1f}<extra></extra>"
                ))
        if has_sub and "ASF" in subject.index and pd.notna(subject.get("ASF")):
            fig.add_trace(go.Scatter(
                x=[subject["ASF"]], y=[sub_val],
                mode="markers",
                marker=dict(size=14, color="#FFD700", symbol="star", line=dict(width=1.5, color="black")),
                name="Subject",
                hovertemplate=f"<b>Subject</b><br>ASF: {int(subject['ASF']):,}<br>" + metric_key + f": {sub_val:,.1f}<extra></extra>"
            ))
        x_label = "ASF (sqft)"
        y_label = metric_options.get(metric_key, metric_key)
        fig.update_layout(title=f"{y_label} vs ASF", height=350,
                          xaxis_title=x_label, yaxis_title=y_label, font=dict(size=11))
        fig.update_xaxes(range=[0, None])
        fig.update_yaxes(range=[0, None])
        st.plotly_chart(fig, use_container_width=True)

# ── Column chart: property-by-property comparison ──
st.subheader(f"📊 Property Ranking: {metric_options.get(metric_key, metric_key)}")
if not comps_vals.empty:
    bar_df = comps_f.dropna(subset=[metric_key]).copy()
    bar_df = bar_df.sort_values(metric_key, ascending=True)
    display_col = "Address (style code)" if "Address (style code)" in bar_df.columns else bar_df.index
    bar_labels = bar_df[display_col].apply(lambda x: str(x)[:30])

    bar_colors = [STATUS_COLORS.get(s, "#1B3A5C") for s in bar_df["Status"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=bar_labels, y=bar_df[metric_key],
        name="Comps",
        marker_color=bar_colors,
        marker_line=dict(width=0),
        text=bar_df[metric_key].apply(lambda v: f"{v:,.0f}" if abs(v) >= 100 else f"{v:,.2f}"),
        textposition="outside",
        textfont=dict(size=9, color="#333"),
        hovertemplate="%{x}<br>" + metric_key + ": %{y:,.1f}<extra></extra>"
    ))
    if has_sub:
        fig.add_hline(y=sub_val, line_width=2, line_dash="dash", line_color="#e74c3c",
                      annotation_text=f"Subject: {sub_val:,.0f}" if abs(sub_val) >= 100 else f"Subject: {sub_val:,.2f}",
                      annotation_position="right")
    label = metric_options.get(metric_key, metric_key)
    fig.update_layout(height=max(350, 50 + len(bar_df) * 12), margin=dict(l=10, r=10, t=20, b=80 if len(bar_df) > 10 else 40),
                      xaxis_title="", yaxis_title=label, font=dict(size=11), showlegend=False,
                      xaxis=dict(tickfont=dict(size=10), tickangle=-45))
    st.plotly_chart(fig, use_container_width=True)

    legend_html = "".join(
        f'<span style="display:inline-block;width:12px;height:12px;background:{c};border-radius:2px;margin-right:4px;vertical-align:middle"></span>{s}&nbsp;&nbsp;'
        for s, c in STATUS_COLORS.items() if s != "Subject"
    )
    st.markdown(legend_html, unsafe_allow_html=True)
if not comps_vals.empty and has_sub:
    st.subheader("📈 Quick Stats")
    kcol1, kcol2, kcol3, kcol4, kcol5 = st.columns(5)
    median = comps_vals.median()
    mean = comps_vals.mean()
    p_min = comps_vals.min()
    p_max = comps_vals.max()
    diff_pct = ((sub_val - median) / median * 100) if median != 0 else 0
    rank = (comps_vals < sub_val).sum() + 1
    total = len(comps_vals)
    label = metric_options.get(metric_key, metric_key)
    with kcol1:
        st.metric(f"Subject {label}", f"{sub_val:,.2f}")
    with kcol2:
        st.metric(f"Comps Median", f"{median:,.2f}", delta=f"{diff_pct:+.2f}% vs subject")
    with kcol3:
        st.metric("Comps Range", f"{p_min:,.2f} — {p_max:,.2f}")
    with kcol4:
        st.metric("Comps Mean ± SD", f"{mean:,.2f} ± {comps_vals.std():,.2f}")
    with kcol5:
        st.metric("Subject Rank", f"#{rank} of {total}", delta=f"top {rank/total*100:.2f}%" if total > 0 else None)

# ── Data table ──
st.divider()
with st.expander(f"📋 Filtered Comps ({len(comps_f)} properties)", expanded=False):
    st.dataframe(comps_f, use_container_width=True, hide_index=True)
    csv = comps_f.to_csv(index=False)
    st.download_button("📥 Download CSV", csv, "filtered_comps.csv", "text/csv")
