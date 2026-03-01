from typing import List, Dict, Any, Tuple, Set
from collections import deque, defaultdict
from graphviz import Digraph
import html
from itertools import chain
from io import BytesIO
try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None
import math
 
def _measure(draw, text, font):
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        if hasattr(font, "getsize"):
            return font.getsize(text)
        return (len(text) * 6, 12)

def parse_pred_string(s: str) -> List[str]:
    if not s or s.strip() in {"-", "None", "none"}:
        return []
    parts = [p.strip() for p in s.split(",")]
    return [p for p in parts if p]

def _esc(s: str) -> str:
    return html.escape(s or "")

def _wrap_center_lines(text: str, max_chars: int = 21, max_lines: int | None = None) -> List[str]:
    words = (text or "").split()
    if not words:
        return [""]
    lines: List[str] = []
    cur = ""
    i = 0
    while i < len(words) and (max_lines is None or len(lines) < max_lines):
        w = words[i]
        tentative = (w if not cur else cur + " " + w)
        if len(tentative) <= max_chars:
            cur = tentative
            i += 1
        else:
            if cur:
                lines.append(cur)
                cur = ""
            else:
                # very long word; break hard
                lines.append(w[:max_chars])
                words[i] = w[max_chars:]
                if not words[i]:
                    i += 1
    if cur and (max_lines is None or len(lines) < max_lines):
        lines.append(cur)
    # no trimming or ellipsis; show full content across as many lines as needed
    # if max_lines is not None and text overflows, additional words will continue in the last line without ellipsis
    return lines

def normalize_activities(activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    seen = set()
    for item in activities:
        i = str(item["id"]).strip()
        if not i or i in seen:
            raise ValueError("Activity IDs must be unique and non-empty")
        seen.add(i)
        d = int(item.get("duration", 0))
        p = item.get("preds") or []
        n = str(item.get("name", "")).strip()
        out.append({"id": i, "duration": max(0, d), "preds": list(p), "name": n})
    return out

def topo_order(ids: List[str], preds: Dict[str, List[str]]) -> List[str]:
    indeg = {i: 0 for i in ids}
    succs = defaultdict(list)
    for v, ps in preds.items():
        for p in ps:
            succs[p].append(v)
            indeg[v] += 1
    q = deque([i for i in ids if indeg[i] == 0])
    order = []
    while q:
        u = q.popleft()
        order.append(u)
        for v in succs[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    if len(order) != len(ids):
        raise ValueError("Cycle detected in activities")
    return order

def compute_cpm(activities: List[Dict[str, Any]]) -> Dict[str, Any]:
    acts = normalize_activities(activities)
    id_index = {a["id"]: a for a in acts}
    ids = [a["id"] for a in acts]
    for a in acts:
        for p in a["preds"]:
            if p not in id_index:
                raise ValueError(f"Predecessor {p} not found for {a['id']}")
            if p == a["id"]:
                raise ValueError(f"Activity {a['id']} cannot depend on itself")
    preds = {a["id"]: list(a["preds"]) for a in acts}
    succs = defaultdict(list)
    for v, ps in preds.items():
        for p in ps:
            succs[p].append(v)
    order = topo_order(ids, preds)
    ES: Dict[str, int] = {}
    EF: Dict[str, int] = {}
    for v in order:
        if preds[v]:
            es = max(EF[p] for p in preds[v])
        else:
            es = 0
        ES[v] = es
        EF[v] = es + id_index[v]["duration"]
    sinks = [i for i in ids if len(succs[i]) == 0]
    project_duration = max(EF[i] for i in sinks) if sinks else 0
    LF: Dict[str, int] = {}
    LS: Dict[str, int] = {}
    for v in reversed(order):
        if succs[v]:
            lf = min(LS[s] for s in succs[v])
        else:
            lf = project_duration
        LF[v] = lf
        LS[v] = lf - id_index[v]["duration"]
    slack = {v: LS[v] - ES[v] for v in ids}
    critical_set: Set[str] = {v for v in ids if slack[v] == 0}
    critical_edges: Set[Tuple[str, str]] = set()
    for v in ids:
        for s in succs[v]:
            if v in critical_set and s in critical_set and EF[v] == ES[s]:
                critical_edges.add((v, s))
    return {
        "activities": acts,
        "ES": ES,
        "EF": EF,
        "LS": LS,
        "LF": LF,
        "slack": slack,
        "critical_set": critical_set,
        "critical_edges": critical_edges,
        "project_duration": project_duration,
        "preds": preds,
        "succs": succs,
        "order": order,
    }

def _graph_for_result(result: Dict[str, Any], rankdir: str = "LR", show_times: bool = True, hide_start_finish: bool = False) -> Digraph:
    g = Digraph(
        "CPM",
        graph_attr={
            "rankdir": rankdir,
            "splines": "ortho",
            "nodesep": "0.35",
            "ranksep": "0.7",
            "fontname": "Helvetica",
        },
        node_attr={"fontname": "Helvetica"},
        edge_attr={"fontname": "Helvetica"},
    )
    ES = result["ES"]
    EF = result["EF"]
    LS = result["LS"]
    LF = result["LF"]
    SL = result["slack"]
    crit = result["critical_set"]
    preds = result["preds"]
    hidden = set()
    if hide_start_finish:
        for a in result["activities"]:
            if a["id"].strip().lower() in {"start", "finish"}:
                hidden.add(a["id"])
    for a in result["activities"]:
        i = a["id"]
        if i in hidden:
            continue
        d = a["duration"]
        nm_raw = a.get("name", "")
        nm_lines = _wrap_center_lines(nm_raw, max_chars=21, max_lines=None)
        nm_html = "<BR/>".join(_esc(x) for x in nm_lines)
        if show_times:
            label = f"""<
<TABLE BORDER="1" CELLBORDER="1" CELLSPACING="0" CELLPADDING="2" ALIGN="CENTER" WIDTH="100">
  <TR>
    <TD WIDTH="30">{ES[i]}</TD>
    <TD WIDTH="40"><B>{d}</B></TD>
    <TD WIDTH="30">{EF[i]}</TD>
  </TR>
  <TR>
    <TD COLSPAN="3" BGCOLOR="#eef7ff" ALIGN="CENTER" VALIGN="MIDDLE"><B>{_esc(i)}</B><BR/><FONT POINT-SIZE="10">{nm_html}</FONT></TD>
  </TR>
  <TR>
    <TD WIDTH="30">{LS[i]}</TD>
    <TD WIDTH="40">{SL[i]}</TD>
    <TD WIDTH="30">{LF[i]}</TD>
  </TR>
</TABLE>
>"""
            # Use plain shape for HTML-like table
            node_kwargs = {"shape": "plain"}
        else:
            label = f"{i}\\n" + "\\n".join(nm_lines)
            node_kwargs = {"shape": "box", "style": "rounded"}
        color = "crimson" if i in crit else "#4444aa"
        penwidth = "2" if i in crit else "1"
        g.node(i, label=label, color=color, penwidth=penwidth, **node_kwargs)
    for v, ps in preds.items():
        if v in hidden:
            continue
        for p in ps:
            if p in hidden:
                continue
            attrs = {}
            if (p, v) in result["critical_edges"]:
                attrs["color"] = "crimson"
                attrs["penwidth"] = "2"
            g.edge(p, v, **attrs)
    # Legend cluster
    legend_label = """<
<TABLE BORDER="1" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4">
  <TR>
    <TD>ES</TD>
    <TD><B>Duration</B></TD>
    <TD>EF</TD>
  </TR>
  <TR>
    <TD COLSPAN="3" BGCOLOR="#eef7ff"><B>Activity</B><BR/><FONT POINT-SIZE="10">Description</FONT></TD>
  </TR>
  <TR>
    <TD>LS</TD>
    <TD>Total Float</TD>
    <TD>LF</TD>
  </TR>
</TABLE>
>"""
    legend = Digraph("cluster_legend")
    legend.attr(label="Legend", color="#8888cc", style="dotted", fontsize="12")
    legend.node("__legend", label=legend_label, shape="plain")
    g.subgraph(legend)
    return g

def build_graphviz(result: Dict[str, Any], rankdir: str = "LR", show_times: bool = True, hide_start_finish: bool = False) -> str:
    g = _graph_for_result(result, rankdir=rankdir, show_times=show_times, hide_start_finish=hide_start_finish)
    return g.source
 
def render_gantt_png(result: Dict[str, Any], sort_desc: bool = False, hide_start_finish: bool = True) -> bytes:
    if Image is None:
        raise RuntimeError("Pillow not available")
    ES = result["ES"]
    EF = result["EF"]
    LS = result["LS"]
    LF = result["LF"]
    SL = result["slack"]
    crit_set = result.get("critical_set", set())
    acts = []
    for a in result["activities"]:
        i = a["id"]
        if hide_start_finish and i.strip().lower() in {"start", "finish"}:
            continue
        acts.append({"id": i, "name": a.get("name", ""), "es": ES[i], "ef": EF[i], "ls": LS[i], "lf": LF[i], "sl": SL[i]})
    if sort_desc:
        acts.sort(key=lambda x: (x["es"], str(x["id"])), reverse=True)
    else:
        acts.sort(key=lambda x: (x["es"], str(x["id"])))
    if not acts:
        raise RuntimeError("No activities to draw")
    max_time = max(x["lf"] for x in acts)
    px_per = 10
    left_w = 260
    row_h = 26
    gap = 6
    pad_left, pad_right, pad_top, pad_bottom = 20, 160, 20, 40
    width = left_w + pad_left + max_time * px_per + pad_right
    height = pad_top + len(acts) * (row_h + gap) + pad_bottom
    img = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    for t in range(0, max_time + 1):
        x = left_w + pad_left + int(t * px_per)
        draw.line([(x, pad_top), (x, height - pad_bottom)], fill=(230, 230, 230, 255), width=1)
        if t % 5 == 0:
            tw, th = _measure(draw, str(t), font)
            draw.text((x - tw // 2, height - pad_bottom + 2), str(t), fill=(80, 80, 80, 255), font=font)
    y = pad_top
    def dashed_rect(x1, y1, x2, y2, color=(120,120,120,255), dash=4, gap=3, width=1):
        if x2 < x1:
            x1, x2 = x2, x1
        if y2 < y1:
            y1, y2 = y2, y1
        # top
        cx = x1
        while cx <= x2:
            nx = min(cx + dash, x2)
            draw.line([(cx, y1), (nx, y1)], fill=color, width=width)
            cx = nx + gap
        # bottom
        cx = x1
        while cx <= x2:
            nx = min(cx + dash, x2)
            draw.line([(cx, y2), (nx, y2)], fill=color, width=width)
            cx = nx + gap
        # left
        cy = y1
        while cy <= y2:
            ny = min(cy + dash, y2)
            draw.line([(x1, cy), (x1, ny)], fill=color, width=width)
            cy = ny + gap
        # right
        cy = y1
        while cy <= y2:
            ny = min(cy + dash, y2)
            draw.line([(x2, cy), (x2, ny)], fill=color, width=width)
            cy = ny + gap
    for a in acts:
        label = f'{a["id"]} - {a["name"]}'
        tw, th = _measure(draw, label, font)
        ly = y + (row_h - th) // 2
        draw.text((pad_left, ly), label, fill=(0, 0, 0, 255), font=font)
        # Late window outline as dashed if slack > 0
        if a["lf"] != a["ef"]:
            x_l = left_w + pad_left + int(a["ls"] * px_per)
            w_l = max(1, int((a["lf"] - a["ls"]) * px_per))
            dashed_rect(x_l, y + 4, x_l + w_l, y + row_h - 4, color=(120,120,120,255))
        x_e = left_w + pad_left + int(a["es"] * px_per)
        w_e = max(1, int((a["ef"] - a["es"]) * px_per))
        is_crit = a["id"] in crit_set
        col_fill = (220, 20, 60, 255) if is_crit else (180, 180, 180, 255)
        col_outline = (200, 0, 40, 255) if is_crit else (140, 140, 140, 255)
        draw.rectangle([x_e, y + 6, x_e + w_e, y + row_h - 6], outline=col_outline, fill=col_fill)
        info = f'D:{a["ef"]-a["es"]}  LS:{a["ls"]}'
        tiw, tih = _measure(draw, info, font)
        # place to the right of the early bar, horizontally centered in row
        info_x = min(x_e + w_e + 6, width - pad_right - tiw - 2)
        info_y = y + (row_h - tih) // 2
        draw.text((info_x, info_y), info, fill=(60, 60, 60, 255), font=font)
        y += row_h + gap
    x_dead = left_w + pad_left + int(max_time * px_per)
    draw.line([(x_dead, pad_top), (x_dead, height - pad_bottom)], fill=(30, 120, 200, 255), width=2)
    # Finish label near latest row
    finish_label = f"Finish = {max_time}"
    ftw, fth = _measure(draw, finish_label, font)
    y_last = pad_top + (len(acts) - 1) * (row_h + gap) + row_h // 2 - fth // 2
    draw.text((min(x_dead + 6, width - ftw - 2), y_last), finish_label, fill=(50,50,50,255), font=font)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def render_graph_png(result: Dict[str, Any], rankdir: str = "LR", show_times: bool = True, hide_start_finish: bool = False) -> bytes:
    g = _graph_for_result(result, rankdir=rankdir, show_times=show_times, hide_start_finish=hide_start_finish)
    try:
        return g.pipe(format="png")
    except Exception as e:
        raise RuntimeError("PNG export requires Graphviz system binary. " + str(e))

def render_graph_png_pure(result: Dict[str, Any], rankdir: str = "LR", show_times: bool = True, hide_start_finish: bool = False) -> bytes:
    if Image is None:
        raise RuntimeError("Pillow not available for pure-Python PNG rendering")
    ES = result["ES"]; EF = result["EF"]; LS = result["LS"]; LF = result["LF"]; SL = result["slack"]
    preds = result["preds"]; succs = result["succs"]; crit_nodes = result["critical_set"]; crit_edges = result["critical_edges"]
    hidden = set()
    if hide_start_finish:
        for a in result["activities"]:
            if a["id"].strip().lower() in {"start", "finish"}:
                hidden.add(a["id"])
    nodes = [a for a in result["activities"] if a["id"] not in hidden]
    if not nodes:
        raise RuntimeError("No nodes to render")
    # Layout by ES as column
    col_map = {}
    for a in nodes:
        col_map[a["id"]] = ES[a["id"]]
    # Normalize columns to [0..]
    cols_sorted = sorted({col_map[n["id"]] for n in nodes})
    col_index = {c:i for i,c in enumerate(cols_sorted)}
    for nid in list(col_map.keys()):
        col_map[nid] = col_index[col_map[nid]]
    # Rows per column: stable order by topological order
    order = result["order"]
    per_col = {}
    for nid in [n for n in order if n in col_map and n not in hidden]:
        c = col_map[nid]
        per_col.setdefault(c, []).append(nid)
    # Constants
    node_w = 100
    hgap, vgap = 18, 18
    pad = 40
    ncols = max(col_map.values()) + 1
    width = pad*2 + ncols * node_w + (ncols-1) * hgap
    # Precompute node heights based on wrapped lines
    id_index = {a["id"]: a for a in nodes}
    def node_size(nid: str) -> tuple[int,int]:
        top_h = 18; bottom_h = 18
        desc_lines = _wrap_center_lines(str(id_index[nid].get("name","")), max_chars=21, max_lines=None)
        tmp_img = Image.new("RGB", (1, 1))
        tmp_draw = ImageDraw.Draw(tmp_img)
        _, lh = _measure(tmp_draw, "A", ImageFont.load_default())
        id_h = lh
        mid_h = id_h + lh * max(1, len(desc_lines)) + 6
        return node_w, top_h + mid_h + bottom_h
    heights_per_col = {}
    for c, ids in per_col.items():
        y = pad
        for nid in ids:
            _, nh = node_size(nid)
            y += nh + vgap
        heights_per_col[c] = y - vgap
    height = max(heights_per_col.values()) + pad
    img = Image.new("RGBA", (width, height), (255,255,255,255))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    # Positions
    pos = {}
    size_map: Dict[str, Tuple[int, int]] = {}
    for c in range(ncols):
        ys = per_col.get(c, [])
        y_cursor = pad
        for r, nid in enumerate(ys):
            x = pad + c * (node_w + hgap)
            pos[nid] = (x, y_cursor)
            _, nh = node_size(nid)
            size_map[nid] = (node_w, nh)
            y_cursor += nh + vgap
    # Edges with orth routing and vertical line jumps
    horiz_segments = []
    vert_segments = []
    seg_styles = {}
    for v, ps in preds.items():
        if v in hidden or v not in pos:
            continue
        for p in ps:
            if p in hidden or p not in pos:
                continue
            x1, y1 = pos[p]
            x2, y2 = pos[v]
            # anchor at mid-height of each node box
            _, ph = size_map.get(p, (node_w, 54))
            _, vh = size_map.get(v, (node_w, 54))
            start = (x1 + node_w, y1 + ph//2)
            end = (x2, y2 + vh//2)
            xm = (start[0] + end[0]) // 2
            pts = [(start[0], start[1]), (xm, start[1]), (xm, end[1]), (end[0], end[1])]
            color = (220,20,60,255) if (p, v) in crit_edges else (68,68,170,255)
            width_px = 3 if (p, v) in crit_edges else 1
            for i in range(3):
                xA, yA = pts[i]
                xB, yB = pts[i+1]
                if yA == yB:
                    seg_id = ("h", min(xA, xB), yA, max(xA, xB))
                    horiz_segments.append(seg_id)
                    seg_styles[seg_id] = (color, width_px)
                elif xA == xB:
                    seg_id = ("v", xA, min(yA, yB), max(yA, yB))
                    vert_segments.append(seg_id)
                    seg_styles[seg_id] = (color, width_px)
            seg_styles[("arrow", end[0], end[1])] = (color, width_px)
    for kind, x1, y, x2 in horiz_segments:
        color, width_px = seg_styles[(kind, x1, y, x2)]
        draw.line([(x1, y), (x2, y)], fill=color, width=width_px)
    r = 6
    for kind, x, y1, y2 in vert_segments:
        color, width_px = seg_styles[(kind, x, y1, y2)]
        ys = []
        for hk, hx1, hy, hx2 in horiz_segments:
            if hx1 <= x <= hx2 and y1 < hy < y2:
                if hy - y1 > r and y2 - hy > r:
                    ys.append(hy)
        ys.sort()
        last = y1
        for cy in ys:
            draw.line([(x, last), (x, cy - r)], fill=color, width=width_px)
            bbox = [x, cy - r, x + 2*r, cy + r]
            draw.arc(bbox, start=90, end=-90, fill=color, width=width_px)
            last = cy + r
        draw.line([(x, last), (x, y2)], fill=color, width=width_px)
    for key in seg_styles:
        if isinstance(key, tuple) and key and key[0] == "arrow":
            _, ex, ey = key
            color, width_px = seg_styles[key]
            ah = 6
            draw.polygon([(ex, ey), (ex-ah, ey-ah), (ex-ah, ey+ah)], fill=color)
    # Nodes
    for a in nodes:
        nid = a["id"]; x, y = pos[nid]
        color = (220,20,60,255) if nid in crit_nodes else (68,68,170,255)
        bg_mid = (238,247,255,255)
        # compute dynamic height
        top_h = 18; bottom_h = 18
        # wrapped lines for description
        nm_lines = _wrap_center_lines(str(a.get("name","")), max_chars=21, max_lines=None)
        _, lh = _measure(draw, "A", font)
        id_h = lh
        mid_h = id_h + lh * max(1, len(nm_lines)) + 6
        node_h = top_h + mid_h + bottom_h
        # outer rect
        draw.rectangle([x, y, x+node_w, y+node_h], outline=color, width=2 if nid in crit_nodes else 1)
        # horizontal separators
        draw.line([ (x, y+top_h), (x+node_w, y+top_h) ], fill=color, width=1)
        draw.line([ (x, y+node_h-bottom_h), (x+node_w, y+node_h-bottom_h) ], fill=color, width=1)
        # vertical lines for top and bottom cells
        # top row split 30 | 40 | 30
        draw.line([ (x+30, y), (x+30, y+top_h) ], fill=color, width=1)
        draw.line([ (x+70, y), (x+70, y+top_h) ], fill=color, width=1)
        # bottom row split 30 | 40 | 30
        by1 = y+node_h-bottom_h
        draw.line([ (x+30, by1), (x+30, y+node_h) ], fill=color, width=1)
        draw.line([ (x+70, by1), (x+70, y+node_h) ], fill=color, width=1)
        # middle bg
        draw.rectangle([x+1, y+top_h+1, x+node_w-1, y+node_h-bottom_h-1], outline=None, fill=bg_mid)
        # text helpers
        def center_text(tx, bx, ty, by, text, bold=False):
            tw, th = _measure(draw, text, font)
            cx = tx + (bx - tx - tw)//2
            cy = ty + (by - ty - th)//2
            draw.text((cx, cy), text, fill=(0,0,0,255), font=font)
        # Top row ES | Dur | EF
        center_text(x, x+30, y, y+top_h, str(ES[nid]))
        center_text(x+30, x+70, y, y+top_h, str(a["duration"]))
        center_text(x+70, x+100, y, y+top_h, str(EF[nid]))
        # Middle row: ID + wrapped name lines
        mid_top = y+top_h; mid_bot = y+node_h-bottom_h
        center_text(x, x+node_w, mid_top, mid_top + id_h + 6, _esc(nid))
        # description lines stacked below ID
        line_y = mid_top + id_h + 6
        for ln in nm_lines:
            tw, th = _measure(draw, ln, font)
            cx = x + (node_w - tw)//2
            line_y += th
            draw.text((cx, line_y), ln, fill=(0,0,0,255), font=font)
        # Bottom LS | Slack | LF
        center_text(x, x+30, y+node_h-bottom_h, y+node_h, str(LS[nid]))
        center_text(x+30, x+70, y+node_h-bottom_h, y+node_h, str(SL[nid]))
        center_text(x+70, x+100, y+node_h-bottom_h, y+node_h, str(LF[nid]))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
