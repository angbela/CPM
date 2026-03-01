import streamlit as st
import pandas as pd
from typing import List, Dict, Any
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
import cpm

st.set_page_config(page_title="Critical Path Method (AON)", layout="wide")

DEFAULT_ROWS = [
    {"id": "A", "duration": 3, "predecessors": "", "name": "FS Bisnis"},
    {"id": "B", "duration": 6, "predecessors": "A", "name": "Studi dan Penetapan DLKr/p"},
    {"id": "C", "duration": 2, "predecessors": "A", "name": "JV Signing"},
    {"id": "D", "duration": 2, "predecessors": "C", "name": "Pembentukan BUP"},
    {"id": "E", "duration": 4, "predecessors": "A", "name": "Persiapan Proses Pembelian Lahan"},
    {"id": "F", "duration": 2, "predecessors": "E,D", "name": "Proses Pembelian Lahan"},
    {"id": "G", "duration": 4, "predecessors": "F", "name": "Proses Alih HGB ke HPL"},
    {"id": "H", "duration": 6, "predecessors": "A", "name": "Studi Basic Design"},
    {"id": "I", "duration": 2, "predecessors": "A,D", "name": "Penyusunan Dokumen Konsesi"},
    {"id": "J", "duration": 1, "predecessors": "F,I,B", "name": "Pengajuan Konsesi"},
    {"id": "K", "duration": 3, "predecessors": "J", "name": "Proses Konsesi"},
    {"id": "L", "duration": 2, "predecessors": "G,K", "name": "Penandatanganan Konsesi"},
    {"id": "M", "duration": 6, "predecessors": "A", "name": "Penyusunan Dokumen Reviu RIP"},
    {"id": "N", "duration": 5, "predecessors": "J,M", "name": "Penetapan RIP"},
    {"id": "O", "duration": 2, "predecessors": "M", "name": "Penyusunan Dokumen PKKPRL"},
    {"id": "P", "duration": 4, "predecessors": "O,D", "name": "Permohonan PKKPRL"},
    {"id": "Q", "duration": 4, "predecessors": "M", "name": "Penyusunan Dokumen Studi Lingkungan"},
    {"id": "R", "duration": 4, "predecessors": "Q,N,P", "name": "Proses Pengesahan Dokumen Lingkungan"},
    {"id": "S", "duration": 4, "predecessors": "H,L", "name": "Tender EPC"},
    {"id": "T", "duration": 4, "predecessors": "H,L", "name": "Tender Peralatan"},
    {"id": "U", "duration": 4, "predecessors": "S", "name": "Detailed Design"},
    {"id": "V", "duration": 1, "predecessors": "N,P,R,H", "name": "Izin Pembangunan"},
    {"id": "W", "duration": 6, "predecessors": "S,R", "name": "Izin Reklamasi"},
    {"id": "X", "duration": 6, "predecessors": "S,R", "name": "Izin Pengerukan"},
    {"id": "Y", "duration": 24, "predecessors": "T", "name": "Pengadaan Peralatan"},
    {"id": "Z", "duration": 24, "predecessors": "U,V", "name": "Konstruksi Terminal"},
    {"id": "AA", "duration": 12, "predecessors": "W,X", "name": "Reklamasi dan Pengerukan"},
    {"id": "AB", "duration": 1, "predecessors": "Z,AA,Y", "name": "Izin Operasi"},
]

def to_dataframe(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["id", "duration", "predecessors", "name"])
    return df

def parse_editor(df: pd.DataFrame) -> List[Dict[str, Any]]:
    records = []
    for _, r in df.iterrows():
        idv = str(r.get("id", "")).strip()
        if not idv:
            continue
        try:
            dur = int(r.get("duration", 0)) if str(r.get("duration", "")).strip() != "" else 0
        except Exception:
            dur = 0
        preds_raw = str(r.get("predecessors", "") or "").strip()
        preds = cpm.parse_pred_string(preds_raw)
        records.append(
            {"id": idv, "duration": max(dur, 0), "preds": preds, "name": str(r.get("name", "")).strip()}
        )
    return records

st.title("Critical Path Method: Activity-on-Node")
st.caption("Streamlit version of the interactive CPM spreadsheet and diagram.")

left, right = st.columns([3, 2])
with left:
    st.subheader("Activities")
    if "activities_df" not in st.session_state:
        st.session_state.activities_df = to_dataframe(DEFAULT_ROWS)
    if st.button("Load project defaults"):
        st.session_state.activities_df = to_dataframe(DEFAULT_ROWS)
    # CSV paste/upload removed for cleaner UI
    # Toolbar: Add row, Delete rows, Download CSV
    t1, t2, t3 = st.columns([1, 3, 1])
    with t1:
        if st.button("Add row", key="add_row_btn", help="Append a blank activity"):
            df = st.session_state.activities_df.copy()
            df.loc[len(df)] = {"id": "", "duration": 0, "predecessors": "", "name": ""}
            st.session_state.activities_df = df
    with t2:
        cur_ids = [str(x) for x in st.session_state.activities_df["id"].fillna("").astype(str).tolist() if str(x).strip()]
        ids_to_delete = st.multiselect("IDs to delete", options=cur_ids, key="ids_to_delete_select")
        if st.button("Delete selected", key="delete_rows_btn", help="Remove selected activities and clean predecessors"):
            if ids_to_delete:
                ids_set = set(ids_to_delete)
                df0 = st.session_state.activities_df.copy()
                df1 = df0[~df0["id"].isin(ids_set)].copy()
                def clean_preds(s: Any) -> str:
                    preds = cpm.parse_pred_string(str(s or ""))
                    preds = [p for p in preds if p not in ids_set]
                    return ",".join(preds)
                df1["predecessors"] = df1["predecessors"].apply(clean_preds)
                st.session_state.activities_df = df1
                st.success("Deleted selected rows and cleaned predecessor references.")
            else:
                st.info("Select one or more IDs to delete.")
    with t3:
        csv_bytes = st.session_state.activities_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", data=csv_bytes, file_name="activities.csv", mime="text/csv", key="download_csv_btn")

    # Editor in a form to avoid auto-rerun during paste
    with st.form("activities_form"):
        edited_df = st.data_editor(
            st.session_state.activities_df,
            key="activities_editor",
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "id": st.column_config.TextColumn("Activity ID", required=True, width="small", help="e.g., A"),
                "duration": st.column_config.NumberColumn("Duration", min_value=0, step=1, width="small", help="Non-negative integer"),
                "predecessors": st.column_config.TextColumn("Predecessors (comma-separated)", width="medium", help="e.g., A,B"),
                "name": st.column_config.TextColumn("Name/Description", width="large", help="Short description"),
            },
            hide_index=True,
        )
        save_changes = st.form_submit_button("Save changes")
    if save_changes and edited_df is not None:
        # Normalize columns order and types
        cols = ["id", "duration", "predecessors", "name"]
        for c in cols:
            if c not in edited_df.columns:
                edited_df[c] = ""
        st.session_state.activities_df = edited_df[cols]

with right:
    st.subheader("Settings")
    auto_layout = st.checkbox("Auto layout diagram left-to-right", value=True)
    show_times = st.checkbox("Show ES/EF/LS/LF on nodes", value=True)
    gantt_sort = st.radio("Timeline sort by earliest", ["Ascending", "Descending"], horizontal=True)
    start_date = st.date_input("Timeline start date", value=date.today())
    dur_unit = st.radio("Duration unit", ["Days", "Weeks", "Months"], horizontal=True)
    run_btn = st.button("Compute CPM")

if run_btn:
    try:
        acts = parse_editor(st.session_state.activities_df)
        result = cpm.compute_cpm(acts)
        st.success(f"Project duration: {result['project_duration']}")
        sched_df = pd.DataFrame(
            [
                {
                    "id": a["id"],
                    "duration": a["duration"],
                    "preds": ",".join(a["preds"]),
                    "ES": result["ES"][a["id"]],
                    "EF": result["EF"][a["id"]],
                    "LS": result["LS"][a["id"]],
                    "LF": result["LF"][a["id"]],
                    "Slack": result["slack"][a["id"]],
                    "critical": a["id"] in result["critical_set"],
                    "name": a.get("name", ""),
                }
                for a in result["activities"]
            ]
        )
        st.dataframe(sched_df, use_container_width=True)
        rankdir = "LR" if auto_layout else "TB"
        dot = cpm.build_graphviz(result, rankdir=rankdir, show_times=show_times, hide_start_finish=False)
        st.graphviz_chart(dot, use_container_width=True)
        st.subheader("Project Timeline (Gantt)")
        # Build interactive Gantt with Plotly
        base = pd.Timestamp(start_date)
        df_plot = pd.DataFrame(
            {
                "Task": sched_df["id"] + " - " + sched_df["name"].astype(str),
                "ID": sched_df["id"],
                "ES": sched_df["ES"],
                "EF": sched_df["EF"],
                "LS": sched_df["LS"],
                "LF": sched_df["LF"],
                "Slack": sched_df["Slack"],
                "critical": sched_df["critical"],
            }
        )
        # Sort by ES with ID tie-breaker
        if gantt_sort == "Descending":
            df_plot = df_plot.sort_values(by=["ES", "ID"], ascending=[False, False])
        else:
            df_plot = df_plot.sort_values(by=["ES", "ID"], ascending=[True, True])
        if dur_unit == "Months":
            df_plot["EarlyStart"] = df_plot["ES"].apply(lambda n: base + pd.DateOffset(months=int(n)))
            df_plot["EarlyFinish"] = df_plot["EF"].apply(lambda n: base + pd.DateOffset(months=int(n)))
            df_plot["LateStart"] = df_plot["LS"].apply(lambda n: base + pd.DateOffset(months=int(n)))
            df_plot["LateFinish"] = df_plot["LF"].apply(lambda n: base + pd.DateOffset(months=int(n)))
        elif dur_unit == "Weeks":
            df_plot["EarlyStart"] = base + pd.to_timedelta(df_plot["ES"] * 7, unit="D")
            df_plot["EarlyFinish"] = base + pd.to_timedelta(df_plot["EF"] * 7, unit="D")
            df_plot["LateStart"] = base + pd.to_timedelta(df_plot["LS"] * 7, unit="D")
            df_plot["LateFinish"] = base + pd.to_timedelta(df_plot["LF"] * 7, unit="D")
        else:
            df_plot["EarlyStart"] = base + pd.to_timedelta(df_plot["ES"], unit="D")
            df_plot["EarlyFinish"] = base + pd.to_timedelta(df_plot["EF"], unit="D")
            df_plot["LateStart"] = base + pd.to_timedelta(df_plot["LS"], unit="D")
            df_plot["LateFinish"] = base + pd.to_timedelta(df_plot["LF"], unit="D")
        # Early bars
        fig = px.timeline(
            df_plot,
            y="Task",
            x_start="EarlyStart",
            x_end="EarlyFinish",
            color="critical",
            color_discrete_map={True: "crimson", False: "lightgray"},
            hover_data={"ES": True, "EF": True, "LS": True, "LF": True, "Slack": True, "ID": True, "Task": False},
        )
        # Late windows where slack > 0 as translucent overlays
        has_slack = df_plot["Slack"] > 0
        if has_slack.any():
            fig2 = px.timeline(
                df_plot[has_slack],
                y="Task",
                x_start="LateStart",
                x_end="LateFinish",
            )
            for tr in fig2.data:
                tr.update(marker_color="rgba(160,160,160,0.25)", marker_line_color="#777", marker_line_width=1, showlegend=False, hoverinfo="skip")
                fig.add_trace(tr)
        fig.update_layout(
            height=min(1200, 60 * max(4, len(df_plot)) + 160),
            xaxis_title=("Month" if dur_unit == "Months" else ("Week" if dur_unit == "Weeks" else "Day")),
            yaxis_title="",
            legend_title_text="Critical",
            margin=dict(l=10, r=10, t=40, b=10),
            bargap=0.3,
        )
        fig.update_yaxes(autorange="reversed", categoryorder="array", categoryarray=list(df_plot["Task"]))
        # Monthly gridlines regardless of unit
        first_month = pd.Timestamp(start_date).replace(day=1)
        fig.update_xaxes(
            showgrid=True,
            gridcolor="#eee",
            dtick="M1",
            tick0=first_month,
            tickformat="%b %Y",
        )
        st.plotly_chart(fig, use_container_width=True, theme="streamlit")
    except Exception as e:
        st.error(str(e))

