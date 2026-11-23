import random
import time

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from matplotlib.patches import Circle, Rectangle

st.set_page_config(page_title="Adaptive junction control", layout="wide")

# ---------- configuration ----------
DIRS = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}
NAMES = {"N": "North", "E": "East", "S": "South", "W": "West"}
PH = [("N", "S"), ("E", "W")]
PHN = ["North–South", "East–West"]
DEFAULT_RATE = {"N": 21, "E": 30, "S": 12, "W": 15}  # vehicles per minute
CFG = dict(headway=2, yellow=2, allred=1, gmin=6, gmax=30,
           amb_approach=3, amb_pass=3, amb_green=8, starve=45)
STOP, HALF, M_PER_CAR = 66, 48, 7


def fmt(s):
    return f"{int(s // 60)}:{int(s % 60):02d}"


def log(msg):
    sim = st.session_state.sim
    sim["log"].insert(0, f"**{fmt(sim['clock'])}**  {msg}")
    del sim["log"][40:]


def reset():
    st.session_state.sim = dict(
        rate={k: DEFAULT_RATE[k] / 60 for k in DIRS},
        q={k: 0 for k in DIRS}, acc={k: 0.0 for k in DIRS},
        leaving={k: [] for k in DIRS},
        mode="green", phase=0, t=0.0, dur=12.0, last=1, idle=[0, 0],
        amb=None, served=0, arrivals=0, greens=0, clock=0.0, log=[],
    )
    log("Junction reset. North–South has green.")


def demand(s, p):
    return sum(s["q"][k] for k in PH[p])


def choose_next(s):
    other = 1 - s["last"]
    if s["idle"][other] >= CFG["starve"]:       # anti-starvation
        return other
    d0, d1 = demand(s, 0), demand(s, 1)
    if d0 == d1:
        return other
    return 0 if d0 > d1 else 1                  # heavier queue gets priority


def end_green(s, reason):
    s["mode"], s["t"], s["last"] = "yellow", 0.0, s["phase"]
    s["greens"] += 1
    log(f"{PHN[s['phase']]} amber ({reason})")


def start_green(s):
    amb = s["amb"]
    if amb and amb["stage"] == "wait":
        p = 0 if amb["app"] in PH[0] else 1
        amb["stage"], amb["p"] = "pass", 0.0
        s["dur"] = CFG["amb_green"]
        log(f"Emergency green for {PHN[p]}")
    else:
        p = choose_next(s)
        s["dur"] = min(CFG["gmax"], max(CFG["gmin"], 4 + 2.5 * demand(s, p)))
        log(f"{PHN[p]} green for {round(s['dur'])} s ({demand(s, p)} waiting)")
    s["phase"], s["mode"], s["t"] = p, "green", 0.0


def step(s, dt=1.0):
    # arrivals
    for k in DIRS:
        if random.random() < s["rate"][k] * dt:
            s["q"][k] += 1
            s["arrivals"] += 1
    # discharge on green, one car per headway
    for k in DIRS:
        green = s["mode"] == "green" and k in PH[s["phase"]]
        if green and s["q"][k] > 0:
            s["acc"][k] += dt
            while s["acc"][k] >= CFG["headway"] and s["q"][k] > 0:
                s["acc"][k] -= CFG["headway"]
                s["q"][k] -= 1
                s["served"] += 1
                s["leaving"][k].append(0.0)
        else:
            s["acc"][k] = 0.0
        s["leaving"][k] = [p + dt / 1.2 for p in s["leaving"][k] if p + dt / 1.2 < 1]
    # idle time per phase
    for p in (0, 1):
        if s["mode"] == "green" and s["phase"] == p:
            s["idle"][p] = 0.0
        else:
            s["idle"][p] += dt
    # ambulance
    amb = s["amb"]
    if amb:
        if amb["stage"] == "approach":
            amb["p"] = min(1.0, amb["p"] + dt / CFG["amb_approach"])
            if amb["p"] >= 1:
                amb["stage"] = "wait"
                log(f"Ambulance detected at {NAMES[amb['app']]} stop line")
        elif amb["stage"] == "pass":
            amb["p"] += dt / CFG["amb_pass"]
            if amb["p"] >= 1:
                log("Ambulance cleared the junction. Normal control resumes")
                s["amb"] = None
    amb = s["amb"]
    if amb and amb["stage"] == "wait" and s["mode"] == "green" and amb["app"] in PH[s["phase"]]:
        amb["stage"], amb["p"] = "pass", 0.0
        s["dur"] = s["t"] + CFG["amb_green"]
        log(f"Green extended for ambulance on {NAMES[amb['app']]}")
    # signal state machine
    s["t"] += dt
    s["clock"] += dt
    if s["mode"] == "green":
        cur, oth = s["phase"], 1 - s["phase"]
        amb = s["amb"]
        if amb and amb["stage"] == "wait":
            end_green(s, "ambulance priority")
        elif s["t"] >= s["dur"]:
            end_green(s, "time up")
        elif (not (amb and amb["stage"] == "pass") and s["t"] >= CFG["gmin"]
              and demand(s, cur) == 0 and demand(s, oth) > 0):
            end_green(s, "queue cleared early")
    elif s["mode"] == "yellow":
        if s["t"] >= CFG["yellow"]:
            s["mode"], s["t"] = "allred", 0.0
    else:
        if s["t"] >= CFG["allred"]:
            start_green(s)


def signal_state(s, k):
    if s["mode"] == "green":
        return "g" if k in PH[s["phase"]] else "r"
    if s["mode"] == "yellow":
        return "a" if k in PH[s["phase"]] else "r"
    return "r"


def draw(s):
    def pt(k, r, off):
        dx, dy = DIRS[k]
        return dx * r - dy * off, dy * r + dx * off

    fig, ax = plt.subplots(figsize=(6, 6), dpi=110)
    fig.patch.set_facecolor("#1b2126")
    ax.set_facecolor("#1b2126")
    ax.set_xlim(-280, 280)
    ax.set_ylim(-280, 280)
    ax.set_aspect("equal")
    ax.axis("off")

    ax.add_patch(Rectangle((-280, -HALF), 560, 2 * HALF, color="#2a3137"))
    ax.add_patch(Rectangle((-HALF, -280), 2 * HALF, 560, color="#2a3137"))
    ax.add_patch(Rectangle((-HALF, -HALF), 2 * HALF, 2 * HALF, color="#323b43"))
    dash = (0, (4, 4))
    for xs, ys in [([0, 0], [HALF, 280]), ([0, 0], [-HALF, -280]),
                   ([HALF, 280], [0, 0]), ([-HALF, -280], [0, 0])]:
        ax.plot(xs, ys, color="#c9b86a", linestyle=dash, linewidth=1.5)

    for k in DIRS:
        p1, p2 = pt(k, STOP, -HALF), pt(k, STOP, HALF)
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color="#e8ecef", linewidth=3)

    def car(k, r, off, color):
        x, y = pt(k, r, off)
        vertical = DIRS[k][1] != 0
        w, h = (10, 14) if vertical else (14, 10)
        ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, color=color))

    for k in DIRS:
        for p in s["leaving"][k]:
            car(k, STOP + (-STOP - 170 - STOP) * p, -10, "#7f909c")
        n = min(s["q"][k], 9)
        for i in range(n):
            car(k, STOP + 8 + 16 * i, -10, "#b8c4cc")
        if s["q"][k] > 9:
            x, y = pt(k, STOP + 8 + 16 * 9, -10)
            ax.text(x + 10, y, f"+{s['q'][k] - 9}", color="#e6e9eb", fontsize=9, va="center")

        colour = {"g": "#4fd18b", "a": "#f0b429", "r": "#ef5b5b"}[signal_state(s, k)]
        x, y = pt(k, STOP + 14, HALF + 12)
        ax.add_patch(Circle((x, y), 8, color=colour, ec="#0d1114", lw=1.5))

    for lbl, (x, y) in {"N": (0, 268), "S": (0, -272), "E": (268, 0), "W": (-272, 0)}.items():
        ax.text(x, y, lbl, color="#8d99a3", fontsize=11, ha="center", va="center", fontweight="bold")

    amb = s["amb"]
    if amb:
        if amb["stage"] == "approach":
            r = 260 + (STOP - 260) * amb["p"]
        elif amb["stage"] == "wait":
            r = STOP
        else:
            r = STOP + (-260 - STOP) * amb["p"]
        x, y = pt(amb["app"], r, 12)
        vertical = DIRS[amb["app"]][1] != 0
        flash = int(time.time() * 5) % 2
        w, h = (10, 16) if vertical else (16, 10)
        ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h,
                               color="#ff7a59" if flash else "white"))
    return fig


# ---------- app ----------
if "sim" not in st.session_state:
    reset()

st.sidebar.header("Controls")
if st.sidebar.button("Reset junction"):
    reset()
sim = st.session_state.sim

st.sidebar.subheader("Traffic arrivals (vehicles per minute)")
for k in DIRS:
    sim["rate"][k] = st.sidebar.slider(NAMES[k], 0, 60, DEFAULT_RATE[k], key=f"rate_{k}") / 60

st.sidebar.subheader("Emergency")
amb_pick = st.sidebar.selectbox("Ambulance from", list(DIRS), format_func=lambda k: NAMES[k])
if st.sidebar.button("Send ambulance", type="primary"):
    if sim["amb"]:
        log("An ambulance is already on its way")
    else:
        sim["amb"] = {"app": amb_pick, "stage": "approach", "p": 0.0}
        log(f"Ambulance requested from {NAMES[amb_pick]}")

paused = st.sidebar.toggle("Pause simulation", key="paused")

st.title("Adaptive junction control")
st.caption("Live simulation of North, South, East and West approaches")

@st.fragment(run_every=1)
def live():
    if not st.session_state.get("paused", False):
        step(st.session_state.sim)
    s = st.session_state.sim

    left, right = st.columns([1.1, 1])
    with left:
        fig = draw(s)
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)
        st.caption("Each car is one waiting vehicle. Green time grows with the queue (6 to 30 s). "
                   "An ambulance triggers early green on its approach.")

    with right:
        if s["amb"]:
            stage = {"approach": "approaching, not yet at the stop line",
                     "wait": "waiting for green", "pass": "passing with green"}[s["amb"]["stage"]]
            st.warning(f"Emergency priority: ambulance from {NAMES[s['amb']['app']]} {stage}")

        c1, c2, c3 = st.columns(3)
        c1.metric("Vehicles arrived", s["arrivals"])
        c2.metric("Vehicles through", s["served"])
        c3.metric("Green phases done", s["greens"])

        if s["mode"] == "green":
            st.subheader(f"{PHN[s['phase']]} green")
            st.write(f"{max(0, s['dur'] - s['t']):.0f} s left")
            st.progress(min(1.0, s["t"] / s["dur"]))
        else:
            st.subheader("Clearing" if s["mode"] == "allred" else f"{PHN[s['phase']]} amber")

        rows = []
        for k in DIRS:
            sig = signal_state(s, k)
            rows.append({
                "Road": NAMES[k],
                "Waiting": s["q"][k],
                "Queue length": f"{s['q'][k] * M_PER_CAR} m",
                "Signal": {"g": "Green", "a": "Amber", "r": "Red"}[sig],
            })
        st.table(pd.DataFrame(rows).set_index("Road"))

        st.subheader("Event log")
        for line in s["log"][:12]:
            st.markdown(f"- {line}")


live()
