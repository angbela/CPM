from collections import defaultdict, deque
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.patches import Rectangle, FancyArrowPatch
from matplotlib.path import Path


def critical_path_method(tasks):
    successors = defaultdict(list)
    in_degree = defaultdict(int)
    for t in tasks:
        in_degree[t] = in_degree.get(t, 0)
    for task, data in tasks.items():
        for pred in data["predecessors"]:
            if pred not in tasks:
                raise ValueError(f"Task '{task}' references missing predecessor '{pred}'.")
            successors[pred].append(task)
            in_degree[task] += 1
    queue = deque([t for t in tasks if in_degree[t] == 0])
    topo_order = []
    while queue:
        t = queue.popleft()
        topo_order.append(t)
        for succ in successors[t]:
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                queue.append(succ)
    if len(topo_order) != len(tasks):
        raise ValueError("Cycle detected in dependencies (CPM requires a DAG).")
    ES, EF = {}, {}
    for task in topo_order:
        preds = tasks[task]["predecessors"]
        ES[task] = 0 if not preds else max(EF[p] for p in preds)
        EF[task] = ES[task] + tasks[task]["duration"]
    project_duration = max(EF.values()) if EF else 0
    LS, LF = {}, {}
    for task in reversed(topo_order):
        succs = successors.get(task, [])
        LF[task] = project_duration if not succs else min(LS[s] for s in succs)
        LS[task] = LF[task] - tasks[task]["duration"]
    total_float = {t: LS[t] - ES[t] for t in tasks}
    critical_tasks = {t for t in tasks if total_float[t] == 0}
    critical_edges = set()
    for u in tasks:
        for v in successors.get(u, []):
            if u in critical_tasks and v in critical_tasks and ES[v] == EF[u]:
                critical_edges.add((u, v))
    return {
        "ES": ES,
        "EF": EF,
        "LS": LS,
        "LF": LF,
        "Float": total_float,
        "Critical Tasks": sorted(critical_tasks, key=lambda x: topo_order.index(x)),
        "Critical Edges": critical_edges,
        "Project Duration": project_duration,
        "Topo Order": topo_order,
        "Successors": successors,
    }


def wrap_words(text, words_per_line=2):
    words = text.split()
    return "\n".join(" ".join(words[i : i + words_per_line]) for i in range(0, len(words), words_per_line))


def compute_levels(tasks):
    preds = {t: tasks[t]["predecessors"][:] for t in tasks}
    succ = defaultdict(list)
    indeg = {t: len(preds[t]) for t in tasks}
    for t in tasks:
        for p in preds[t]:
            succ[p].append(t)
    q = deque([t for t in tasks if indeg[t] == 0])
    topo = []
    while q:
        u = q.popleft()
        topo.append(u)
        for v in succ[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    level = {t: 0 for t in topo}
    for t in topo:
        if preds[t]:
            level[t] = 1 + max(level[p] for p in preds[t])
    return level


def draw_cpm_network(tasks, cpm_result, words_per_line=2):
    G = nx.DiGraph()
    levels = compute_levels(tasks)
    critical = set(cpm_result["Critical Tasks"])
    for t, data in tasks.items():
        d = data["duration"]
        es = cpm_result["ES"][t]
        ef = cpm_result["EF"][t]
        ls = cpm_result["LS"][t]
        lf = cpm_result["LF"][t]
        fl = cpm_result["Float"][t]
        title = wrap_words(t, words_per_line)
        metrics = f"D={d}\nES={es} EF={ef}\nLS={ls} LF={lf}\nF={fl}"
        G.add_node(t, title=title, metrics=metrics)
    for t, data in tasks.items():
        for p in data["predecessors"]:
            G.add_edge(p, t)
    from collections import defaultdict as _dd
    cols = _dd(list)
    for n in G.nodes():
        cols[levels[n]].append(n)
    for l in cols:
        cols[l].sort(key=lambda n: (0 if n in critical else 1, n))
    x_gap = 4.0
    y_gap = 5.0
    pos = {}
    for l in sorted(cols):
        col = cols[l]
        mid = (len(col) - 1) / 2
        for i, n in enumerate(col):
            pos[n] = (l * x_gap, -(i - mid) * y_gap)
    crit_edges = list(cpm_result["Critical Edges"])
    noncrit_edges = [e for e in G.edges() if e not in crit_edges]
    fig = plt.figure(figsize=(36, 10))
    nx.draw_networkx_nodes(G, pos, node_size=8200)
    nx.draw_networkx_edges(
        G,
        pos,
        edgelist=noncrit_edges,
        edge_color="gray",
        alpha=0.35,
        style="dashed",
        width=1.0,
        arrows=True,
        arrowsize=14,
        connectionstyle="arc3,rad=0.15",
    )
    nx.draw_networkx_edges(G, pos, edgelist=crit_edges, edge_color="red", width=7, arrows=True, arrowsize=24)
    nx.draw_networkx_labels(G, pos, labels=nx.get_node_attributes(G, "title"), font_size=12, font_weight="bold", verticalalignment="bottom")
    nx.draw_networkx_labels(G, pos, labels=nx.get_node_attributes(G, "metrics"), font_size=9, verticalalignment="top")
    plt.title("Critical Path Method (CPM) – Logical Network", fontsize=16)
    plt.axis("off")
    plt.tight_layout()
    return fig


def plot_cpm_timeline_quarterly(tasks, cpm_result, show_float=True, start_year=2026, start_quarter=1, ascending=True):
    order = sorted(tasks, key=lambda t: (cpm_result["ES"][t], t))
    if not ascending:
        order = list(reversed(order))
    fig, ax = plt.subplots(figsize=(18, max(7, 0.55 * len(order))))
    for y, t in enumerate(order):
        es, ef = cpm_result["ES"][t], cpm_result["EF"][t]
        ls, lf = cpm_result["LS"][t], cpm_result["LF"][t]
        dur = tasks[t]["duration"]
        fl = cpm_result["Float"][t]
        ax.barh(y, ef - es, left=es, color=("red" if fl == 0 else "lightgray"), edgecolor="black", height=0.6)
        if show_float and fl > 0:
            ax.barh(y, lf - ef, left=ef, height=0.25, facecolor="none", edgecolor="black", linestyle="--")
        ax.text(ef + 0.3, y, f"D={dur}  LS={ls}", va="center", fontsize=9)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order)
    ax.invert_yaxis()
    pdur = cpm_result["Project Duration"]
    max_q = int(np.ceil(pdur / 3))
    ticks = [i * 3 for i in range(max_q + 1)]
    labels = []
    for i in range(max_q + 1):
        q_index = (start_quarter - 1) + i
        year = start_year + q_index // 4
        q = q_index % 4 + 1
        labels.append(f"Q{q} {year}")
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels)
    ax.grid(True, axis="x", linestyle="--")
    ax.axvline(pdur, linestyle="--", linewidth=2)
    ax.text(pdur, len(order) - 0.5, f" Finish = {pdur} mo")
    ax.set_title("Project Timeline (Quarterly, CPM-Based)")
    plt.tight_layout()
    return fig


def draw_cpm_aon(tasks, cpm_result, words_per_line=2, size_scale=1.0):
    levels = compute_levels(tasks)
    crit_edges = set(cpm_result["Critical Edges"])
    preds_map = {t: tasks[t].get("predecessors", []) for t in tasks}
    succ = defaultdict(list)
    for t, preds in preds_map.items():
        for p in preds:
            succ[p].append(t)
    cols = defaultdict(list)
    for n in tasks:
        cols[levels[n]].append(n)
    for l in cols:
        cols[l].sort(key=lambda n: (0 if cpm_result["Float"][n] == 0 else 1, n))
    cols_count = max(levels.values()) + 1 if tasks else 1
    rows_count = max((len(v) for v in cols.values()), default=1)
    x_gap = 3.2 * size_scale
    y_gap = 2.2 * size_scale
    pos = {}
    for l in sorted(cols):
        col = cols[l]
        mid = (len(col) - 1) / 2
        for i, n in enumerate(col):
            pos[n] = (l * x_gap, -(i - mid) * y_gap)
    indeg0 = [t for t in tasks if not preds_map[t]]
    outdeg0 = [t for t in tasks if not succ.get(t)]
    minx = min(x for x, _ in pos.values()) if pos else 0
    maxx = max(x for x, _ in pos.values()) if pos else 0
    y0 = 0.0
    start_xy = (minx - x_gap, y0)
    finish_xy = (maxx + x_gap, y0)
    fig_w = min(max(cols_count * 3.6 * size_scale + 4, 10), 28)
    fig_h = min(max(rows_count * 2.4 * size_scale + 3, 6), 18)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_axis_off()
    for n, (x, y) in pos.items():
        es = cpm_result["ES"][n]
        ef = cpm_result["EF"][n]
        ls = cpm_result["LS"][n]
        lf = cpm_result["LF"][n]
        d = tasks[n]["duration"]
        fl = cpm_result["Float"][n]
        w = 2.8 * size_scale
        h = 1.8 * size_scale
        r = Rectangle((x - w / 2, y - h / 2), w, h, facecolor="#223B56", edgecolor="#89CFF0" if fl == 0 else "#C0C0C0", linewidth=2, zorder=2)
        ax.add_patch(r)
        fs_small = max(8, int(9 * size_scale))
        fs_med = max(9, int(11 * size_scale))
        fs_big = max(10, int(12 * size_scale))
        ax.text(x, y + h * 0.55, f"Slack = {fl}", color="#FFFF66", ha="center", va="center", fontsize=fs_small)
        ax.text(x - w * 0.35, y + h * 0.15, f"{es}", color="#ADE1FA", fontsize=fs_med, ha="left", va="center")
        ax.text(x + w * 0.35, y + h * 0.15, f"{ef}", color="#ADE1FA", fontsize=fs_med, ha="right", va="center")
        ax.text(x, y, f"D={d}", color="#FFFFFF", fontsize=fs_med, ha="center", va="center")
        ax.text(x - w * 0.35, y - h * 0.2, f"{ls}", color="#FFEE99", fontsize=fs_med, ha="left", va="center")
        ax.text(x + w * 0.35, y - h * 0.2, f"{lf}", color="#FFEE99", fontsize=fs_med, ha="right", va="center")
        display_name = n
        ax.text(x, y - h * 0.55, display_name, color="#FFFFFF", fontsize=fs_small, ha="center", va="center")
    lr_offset = (w / 2) + (0.4 * size_scale)
    for u, vs in succ.items():
        for v in vs:
            x1, y1 = pos[u]
            x2, y2 = pos[v]
            color = "#FFD84D" if (u, v) in crit_edges else "#AAAAAA"
            lw = 3 if (u, v) in crit_edges else 1.5
            arr = FancyArrowPatch((x1 + lr_offset, y1), (x2 - lr_offset, y2), arrowstyle="-|>", mutation_scale=12 * size_scale, linewidth=lw, color=color, zorder=1, connectionstyle="arc3,rad=0.0")
            ax.add_patch(arr)
    sbw = 1.8 * size_scale
    sbh = 1.0 * size_scale
    ax.add_patch(Rectangle((start_xy[0] - sbw / 2, start_xy[1] - sbh / 2), sbw, sbh, facecolor="#1A2A3A", edgecolor="#FFFFFF", linewidth=2))
    ax.text(start_xy[0], start_xy[1], "Start", color="#FFFFFF", ha="center", va="center", fontsize=fs_small)
    fbw = 2.2 * size_scale
    fbh = 1.0 * size_scale
    ax.add_patch(Rectangle((finish_xy[0] - fbw / 2, finish_xy[1] - fbh / 2), fbw, fbh, facecolor="#1A2A3A", edgecolor="#FFFFFF", linewidth=2))
    ax.text(finish_xy[0], finish_xy[1], "Finish", color="#FFFFFF", ha="center", va="center", fontsize=fs_small)
    for s in indeg0:
        xs, ys = pos[s]
        arr = FancyArrowPatch((start_xy[0] + sbw / 2, start_xy[1]), (xs - lr_offset, ys), arrowstyle="-|>", mutation_scale=12 * size_scale, linewidth=1.5, color="#AAAAAA")
        ax.add_patch(arr)
    for t in outdeg0:
        xt, yt = pos[t]
        arr = FancyArrowPatch((xt + lr_offset, yt), (finish_xy[0] - fbw / 2, finish_xy[1]), arrowstyle="-|>", mutation_scale=12 * size_scale, linewidth=1.5, color="#AAAAAA")
        ax.add_patch(arr)
    plt.tight_layout()
    return fig


def draw_cpm_blocks(tasks, cpm_result, size_scale=1.0, show_name=False):
    levels = compute_levels(tasks)
    preds_map = {t: tasks[t].get("predecessors", []) for t in tasks}
    succ = defaultdict(list)
    for t, preds in preds_map.items():
        for p in preds:
            succ[p].append(t)
    cols = defaultdict(list)
    for n in tasks:
        cols[levels[n]].append(n)
    for l in cols:
        cols[l].sort(key=lambda n: (0 if cpm_result["Float"][n] == 0 else 1, n))
    cols_count = max(levels.values()) + 1 if tasks else 1
    rows_count = max((len(v) for v in cols.values()), default=1)
    x_gap = 2.6 * size_scale
    y_gap = 1.9 * size_scale
    pos = {}
    for l in sorted(cols):
        col = cols[l]
        mid = (len(col) - 1) / 2
        for i, n in enumerate(col):
            pos[n] = (l * x_gap, -(i - mid) * y_gap)
    minx = min((x for x, _ in pos.values()), default=0.0)
    maxx = max((x for x, _ in pos.values()), default=0.0)
    fig_w = min(max(cols_count * 2.2 * size_scale + 2, 8), 20)
    fig_h = min(max(rows_count * 2.2 * size_scale + 2, 8), 16)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_axis_off()
    w = 2.0 * size_scale
    h = 1.6 * size_scale
    pad = 0.08 * size_scale
    fs_num = max(7, int(9 * size_scale))
    fs_name = max(7, int(8 * size_scale))
    crit_edges = set(cpm_result["Critical Edges"])
    # Nodes as 3x3 style (top merged for slack; second row: ID | ES | EF; third row: D | LS | LF)
    for n, (x, y) in pos.items():
        es = cpm_result["ES"][n]
        ef = cpm_result["EF"][n]
        ls = cpm_result["LS"][n]
        lf = cpm_result["LF"][n]
        d = tasks[n]["duration"]
        fl = cpm_result["Float"][n]
        border = "#FFCC00" if fl == 0 else "#AAC3D5"
        r = Rectangle((x - w / 2, y - h / 2), w, h, facecolor="#1E3347", edgecolor=border, linewidth=2, zorder=5)
        ax.add_patch(r)
        # Grid: top merged row height ratio and two equal lower rows with 3 cols
        top_h = 0.33 * h
        row_h = (h - top_h) / 2.0
        col_w = w / 3.0
        # Horizontal lines: bottom of top row, and bottom of second row
        ax.plot([x - w / 2, x + w / 2], [y + h / 2 - top_h, y + h / 2 - top_h], color="#4A6A80", linewidth=1, zorder=5)
        ax.plot([x - w / 2, x + w / 2], [y - h / 2 + row_h, y - h / 2 + row_h], color="#4A6A80", linewidth=1, zorder=5)
        # Vertical lines for 3 columns (only for lower 2 rows)
        for i in (1, 2):
            cx = x - w / 2 + i * col_w
            ax.plot([cx, cx], [y - h / 2, y + h / 2 - top_h], color="#4A6A80", linewidth=1, zorder=5)
        # Slack (top merged)
        ax.text(x, y + h / 2 - top_h / 2, f"Slack = {fl}", ha="center", va="center", color="#FFFF66", fontsize=fs_num, zorder=6)
        # ID in row2-col1
        id_label = n.split(" - ", 1)[0] if " - " in n else n
        ax.text(x - w / 2 + col_w / 2, y + h / 2 - top_h - row_h / 2, f"{id_label}", ha="center", va="center", color="#ADE1FA", fontsize=fs_num, zorder=6)
        # ES (row2-col2), EF (row2-col3)
        ax.text(x - w / 2 + col_w * 1.5, y + h / 2 - top_h - row_h / 2, f"{es}", ha="center", va="center", color="#ADE1FA", fontsize=fs_num, zorder=6)
        ax.text(x - w / 2 + col_w * 2.5, y + h / 2 - top_h - row_h / 2, f"{ef}", ha="center", va="center", color="#ADE1FA", fontsize=fs_num, zorder=6)
        # D (row3-col1), LS (row3-col2), LF (row3-col3)
        ax.text(x - w / 2 + col_w / 2, y - h / 2 + row_h / 2, f"{d}", ha="center", va="center", color="#FFFFFF", fontsize=fs_num, zorder=6)
        ax.text(x - w / 2 + col_w * 1.5, y - h / 2 + row_h / 2, f"{ls}", ha="center", va="center", color="#FFEE99", fontsize=fs_num, zorder=6)
        ax.text(x - w / 2 + col_w * 2.5, y - h / 2 + row_h / 2, f"{lf}", ha="center", va="center", color="#FFEE99", fontsize=fs_num, zorder=6)
        # Name below
        if show_name:
            ax.text(x, y - h / 2 - 0.12 * size_scale, n if " - " not in n else n.split(" - ", 1)[1], ha="center", va="top", color="#E0E0E0", fontsize=fs_name, zorder=6)
    # Edges (diagonal routing; draw underneath nodes)
    lr_offset = (w / 2) - 0.02
    for u, vs in succ.items():
        for v in vs:
            x1, y1 = pos[u]
            x2, y2 = pos[v]
            on_crit = (u, v) in crit_edges
            color = "#00BCD4" if on_crit else "#8FA6B8"
            lw = 2.5 if on_crit else 1.5
            arrow = FancyArrowPatch(
                (x1 + lr_offset, y1),
                (x2 - lr_offset, y2),
                arrowstyle="-|>",
                mutation_scale=10 * size_scale,
                linewidth=lw,
                color=color,
                zorder=1,
                connectionstyle="arc3,rad=0.0",
            )
            ax.add_patch(arrow)
    plt.tight_layout()
    return fig

