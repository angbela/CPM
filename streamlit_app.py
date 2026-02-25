import streamlit as st
from cpm_lib import critical_path_method, draw_cpm_network, plot_cpm_timeline_quarterly, draw_cpm_aon, draw_cpm_blocks
import io
import pandas as pd
import math
from typing import Tuple


def tasks_to_indexed_lines(tasks):
    names = list(tasks.keys())
    ids = []
    for i in range(len(names)):
        n = i
        s = ""
        while True:
            s = chr(ord("A") + (n % 26)) + s
            n = n // 26 - 1
            if n < 0:
                break
        ids.append(s)
    name_to_id = {name: id_ for name, id_ in zip(names, ids)}
    lines = []
    for name, id_ in zip(names, ids):
        duration = tasks[name]["duration"]
        preds_names = tasks[name].get("predecessors", [])
        preds_ids = [name_to_id[p] for p in preds_names if p in name_to_id]
        preds_field = ",".join(preds_ids)
        lines.append(f"{id_};{name};{duration};{preds_field}")
    return "\n".join(lines)


def parse_tasks_text(text):
    raw_lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not raw_lines:
        return {}
    def is_number(s):
        try:
            float(s)
            return True
        except Exception:
            return False
    first_parts = [p.strip() for p in raw_lines[0].split(";")]
    if len(first_parts) >= 3 and is_number(first_parts[2]):
        entries = []
        for raw in raw_lines:
            parts = [p.strip() for p in raw.split(";")]
            if len(parts) < 3:
                raise ValueError(f"Invalid line (need 'ID;Name;Duration;PredIDs'): {raw}")
            id_ = parts[0]
            name = parts[1]
            try:
                duration = int(float(parts[2]))
            except Exception:
                raise ValueError(f"Invalid duration for '{name}': {parts[2]}")
            preds_str = parts[3] if len(parts) > 3 else ""
            pred_ids = [p.strip() for p in preds_str.split(",") if p.strip()]
            entries.append((id_, name, duration, pred_ids))
        id_to_key = {id_: f"{id_} - {name}" for id_, name, _, _ in entries}
        tasks = {}
        for id_, name, duration, pred_ids in entries:
            key = id_to_key[id_]
            pred_keys = [id_to_key[p] for p in pred_ids if p in id_to_key]
            tasks[key] = {"duration": duration, "predecessors": pred_keys}
        return tasks
    else:
        tasks = {}
        for raw in raw_lines:
            parts = [p.strip() for p in raw.split(";")]
            if len(parts) < 2:
                raise ValueError(f"Invalid line (need 'Name;Duration;Pred1,Pred2'): {raw}")
            name = parts[0]
            try:
                duration = int(float(parts[1]))
            except Exception:
                raise ValueError(f"Invalid duration for '{name}': {parts[1]}")
            preds_str = parts[2] if len(parts) > 2 else ""
            preds = [p.strip() for p in preds_str.split(",") if p.strip()]
            tasks[name] = {"duration": duration, "predecessors": preds}
        return tasks

st.set_page_config(page_title="CPM & Gantt", layout="wide")
st.title("CPM Network and Project Timeline")

default_tasks = {
    "FS Bisnis": {"duration": 3, "predecessors": []},
    "Studi dan Penetapan DLKr/p": {"duration": 6, "predecessors": ["FS Bisnis"]},
    "JV Signing": {"duration": 2, "predecessors": ["FS Bisnis"]},
    "Pembentukan BUP": {"duration": 2, "predecessors": ["JV Signing"]},
    "Persiapan Proses Pembelian Lahan": {"duration": 4, "predecessors": ["FS Bisnis"]},
    "Proses Pembelian Lahan": {"duration": 2, "predecessors": ["Persiapan Proses Pembelian Lahan", "Pembentukan BUP"]},
    "Proses Alih HGB ke HPL": {"duration": 4, "predecessors": ["Proses Pembelian Lahan"]},
    "Studi Basic Design": {"duration": 6, "predecessors": ["FS Bisnis"]},
    "Penyusunan Dokumen Konsesi": {"duration": 2, "predecessors": ["FS Bisnis", "Pembentukan BUP"]},
    "Pengajuan Konsesi": {"duration": 1, "predecessors": ["Proses Pembelian Lahan", "Penyusunan Dokumen Konsesi", "Studi dan Penetapan DLKr/p"]},
    "Proses Konsesi": {"duration": 3, "predecessors": ["Pengajuan Konsesi"]},
    "Penandatanganan Konsesi": {"duration": 2, "predecessors": ["Proses Alih HGB ke HPL", "Proses Konsesi"]},
    "Penyusunan Dokumen Reviu RIP": {"duration": 6, "predecessors": ["FS Bisnis"]},
    "Penetapan RIP": {"duration": 5, "predecessors": ["Pengajuan Konsesi", "Penyusunan Dokumen Reviu RIP"]},
    "Penyusunan Dokumen PKKPRL": {"duration": 2, "predecessors": ["Penyusunan Dokumen Reviu RIP"]},
    "Permohonan PKKPRL": {"duration": 4, "predecessors": ["Penyusunan Dokumen PKKPRL", "Pembentukan BUP"]},
    "Penyusunan Dokumen Studi Lingkungan": {"duration": 4, "predecessors": ["Penyusunan Dokumen Reviu RIP"]},
    "Proses Pengesahan Dokumen Lingkungan": {"duration": 4, "predecessors": ["Penyusunan Dokumen Studi Lingkungan", "Penetapan RIP", "Permohonan PKKPRL"]},
    "Tender EPC": {"duration": 4, "predecessors": ["Studi Basic Design", "Penandatanganan Konsesi"]},
    "Tender Peralatan": {"duration": 4, "predecessors": ["Studi Basic Design", "Penandatanganan Konsesi"]},
    "Detailed Design": {"duration": 4, "predecessors": ["Tender EPC"]},
    "Izin Pembangunan": {"duration": 1, "predecessors": ["Penetapan RIP", "Permohonan PKKPRL", "Proses Pengesahan Dokumen Lingkungan", "Studi Basic Design"]},
    "Izin Reklamasi": {"duration": 6, "predecessors": ["Tender EPC", "Proses Pengesahan Dokumen Lingkungan"]},
    "Izin Pengerukan": {"duration": 6, "predecessors": ["Tender EPC", "Proses Pengesahan Dokumen Lingkungan"]},
    "Pengadaan Peralatan": {"duration": 24, "predecessors": ["Tender Peralatan"]},
    "Konstruksi Terminal": {"duration": 24, "predecessors": ["Detailed Design", "Izin Pembangunan"]},
    "Reklamasi dan Pengerukan": {"duration": 12, "predecessors": ["Izin Reklamasi", "Izin Pengerukan"]},
    "Izin Operasi": {"duration": 1, "predecessors": ["Konstruksi Terminal", "Reklamasi dan Pengerukan", "Pengadaan Peralatan"]},
}

default_text = tasks_to_indexed_lines(default_tasks)

with st.sidebar:
    st.header("Options")
    graph_style = st.selectbox("Graph style", ["Blocks (AON compact)", "Classic (networkx)"], index=0)
    start_year = st.number_input("Start year", min_value=2000, max_value=2100, value=2026, step=1)
    start_quarter = st.selectbox("Start quarter", [1, 2, 3, 4], index=0)
    show_float = st.checkbox("Show float on timeline", value=True)
    timeline_order = st.selectbox("Timeline order", ["Ascending (Earliest first)", "Descending (Latest first)"], index=0)
    fig_dpi = st.slider("Figure DPI", 80, 140, 110, 5)

st.subheader("Paste Tasks")
st.caption("Format: ID;Name;Duration;PredIDs")
text_input = st.text_area("Tasks", value=default_text, height=300)

analyze = st.button("Analyze")
if not analyze:
    st.info("Paste or edit tasks above, then click Analyze.")
    st.stop()
try:
    user_tasks = parse_tasks_text(text_input)
    cpm = critical_path_method(user_tasks)
except Exception as e:
    st.error(str(e))
    st.stop()

st.subheader(f"Project Duration: {cpm['Project Duration']} months")
st.subheader(f"Critical Tasks: {', '.join(cpm['Critical Tasks'])}")

def _safe_dpi_limits(fig, desired_dpi, max_pixels=120_000_000, max_width_px=3200, max_height_px=2200) -> int:
    w_in, h_in = fig.get_size_inches()
    w_in = max(w_in, 1e-6)
    h_in = max(h_in, 1e-6)
    # Pixel-cap based DPI
    max_dpi_by_pixels = int(math.sqrt(max_pixels / (w_in * h_in)))
    # Width/height hard caps
    max_dpi_by_w = int(max_width_px / w_in)
    max_dpi_by_h = int(max_height_px / h_in)
    dpi_safe = min(desired_dpi, max_dpi_by_pixels, max_dpi_by_w, max_dpi_by_h)
    return max(1, dpi_safe)


def fig_to_png_bytes(fig, desired_dpi) -> Tuple[bytes, int]:
    dpi_safe = _safe_dpi_limits(fig, desired_dpi)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi_safe, bbox_inches="tight")
    return buf.getvalue(), dpi_safe

tab1, tab2 = st.tabs(["CPM Network", "Project Timeline"])
with tab1:
    if graph_style.startswith("Blocks"):
        fig = draw_cpm_blocks(user_tasks, cpm, size_scale=1.0, show_name=False)
    else:
        fig = draw_cpm_network(user_tasks, cpm, words_per_line=2)
    png_bytes, dpi_used = fig_to_png_bytes(fig, fig_dpi)
    st.image(png_bytes, use_container_width=True)
    st.download_button("Download CPM Network (PNG)", data=png_bytes, file_name="cpm_network.png", mime="image/png")
    rows = []
    for key in cpm["Topo Order"]:
        es = cpm["ES"][key]; ef = cpm["EF"][key]
        ls = cpm["LS"][key]; lf = cpm["LF"][key]
        fl = cpm["Float"][key]
        d = user_tasks[key]["duration"]
        id_label = key.split(" - ", 1)[0] if " - " in key else key
        name_label = key.split(" - ", 1)[1] if " - " in key else key
        rows.append([id_label, name_label, d, es, ef, ls, lf, fl])
    df = pd.DataFrame(rows, columns=["ID", "Name", "Duration", "ES", "EF", "LS", "LF", "Slack"])
    st.dataframe(df, use_container_width=True)
with tab2:
    asc = timeline_order.startswith("Ascending")
    fig2 = plot_cpm_timeline_quarterly(user_tasks, cpm, show_float=show_float, start_year=int(start_year), start_quarter=int(start_quarter), ascending=asc)
    png_bytes2, dpi_used2 = fig_to_png_bytes(fig2, fig_dpi)
    st.image(png_bytes2, use_container_width=True)
    st.download_button("Download Project Timeline (PNG)", data=png_bytes2, file_name="project_timeline.png", mime="image/png")
