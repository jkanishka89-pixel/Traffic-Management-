import random
import time

import matplotlib.pyplot as plt
import streamlit as st
from matplotlib.patches import Circle, Rectangle

st.set_page_config(page_title="Adaptive junction control", page_icon="🚦", layout="wide")

# ---------- configuration ----------
DIRS = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}
NAMES = {"N": "North", "E": "East", "S": "South", "W": "West"}
PH = [("N", "S"), ("E", "W")]
PHN = ["North–South", "East–West"]
PH_COLOURS = ["#00c9a7", "#ff6f91"]
DEFAULT_RATE = {"N": 21, "E": 30, "S": 12, "W": 15}  # vehicles per minute
CFG = dict(headway=2, yellow=2, allred=1, gmin=6, gmax=30,
           amb_approach=3, amb_pass=3, amb_green=8, starve=45)
STOP, HALF, M_PER_CAR = 66, 48, 7
SIG_STYLE = {
    "g": ("🟢 Green", "linear-gradient(135deg,#11998e,#38ef7d)"),
    "a": ("🟡 Amber", "linear-gradient(135deg,#f7971e,#ffd200)"),
    "r": ("🔴 Red", "linear-gradient(135deg,#cb2d3e,#ef473a)"),
}


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
    log("Junction reset. North–South has green. 🚦")


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
        log(f"🚑 Emergency green for {PHN[p]}")
    else:
        p = choose_next(s)
        s["dur"] = min(CFG["gmax"], max(CFG["gmin"], 4 + 2.5 * demand(s, p)))
        log(f"{PHN[p]} green for {round(s['dur'])} s ({demand(s, p)} waiting)")
    s["phase"], s["mode"], s["t"] = p, "green", 0.0


def step(s, dt=1.0):
    for k in DIRS:
        if random.random() < s["rate"][k] * dt:
            s["q"][k] += 1
            s["arrivals"] += 1
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
    for p in (0, 1):
        if s["mode"] == "green" and s["phase"] == p:
            s["idle"][p] = 0.0
        else:
            s["idle"][p] += dt
    amb = s["amb"]
    if amb:
        if amb["stage"] == "approach":
            amb["p"] = min(1.0, amb["p"] + dt / CFG["amb_approach"])
            if amb["p"] >= 1:
                amb["stage"] = "wait"
                log(f"🚑 Ambulance detected at {NAMES[amb['app']]} stop line")
        elif amb["stage"] == "pass":
            amb["p"] += dt / CFG["amb_pass"]
            if amb["p"] >= 1:
                log("🚑 Ambulance cleared the junction. Normal control resumes")
                s["amb"] = None
    amb = s["amb"]
    if amb and amb["stage"] == "wait" and s["mode"] == "green" and amb["app"] in PH[s["phase"]]:
        amb["stage"], amb["p"] = "pass", 0.0
        s["dur"] = s["t"] + CFG["amb_green"]
        log(f"Green extended for ambulance on {NAMES[amb['app']]}")
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
    fig.patch.set_facecolor("#0f172a")
    ax.set_facecolor("#0f172a")
    ax.set_xlim(-280, 280)
    ax.set_ylim(-280, 280)
    ax.set_aspect("equal")
    ax.axis("off")

    ax.add_patch(Rectangle((-280, -HALF), 560, 2 * HALF, color="#334155"))
    ax.add_patch(Rectangle((-HALF, -280), 2 * HALF, 560, color="#334155"))
    ax.add_patch(Rectangle((-HALF, -HALF), 2 * HALF, 2 * HALF, color="#475569"))
    for xs, ys in [([0, 0], [HALF, 280]), ([0, 0], [-HALF, -280]),
                   ([HALF, 280], [0, 0]), ([-HALF, -280], [0, 0])]:
        ax.plot(xs, ys, color="#facc15", linestyle=(0, (4, 4)), linewidth=1.6)

    for k in DIRS:
        p1, p2 = pt(k, STOP, -HALF), pt(k, STOP, HALF)
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color="white", linewidth=3)

    def car(k, r, off, color):
        x, y = pt(k, r, off)
        vertical = DIRS[k][1] != 0
        w, h = (10, 14) if vertical else (14, 10)
        ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, color=color, ec="#0f172a", lw=0.8))

    car_colours = ["#f472b6", "#60a5fa", "#a3e635", "#fb923c", "#c084fc", "#2dd4bf"]
    for k in DIRS:
        for p in s["leaving"][k]:
            car(k, STOP + (-STOP - 170 - STOP) * p, -10, "#94a3b8")
        n = min(s["q"][k], 9)
        for i in range(n):
            car(k, STOP + 8 + 16 * i, -10, car_colours[(i + len(k)) % len(car_colours)])
        if s["q"][k] > 9:
            x, y = pt(k, STOP + 8 + 16 * 9, -10)
            ax.text(x + 10, y, f"+{s['q'][k] - 9}", color="white", fontsize=9, va="center")
        colour = {"g": "#22c55e", "a": "#fbbf24", "r": "#ef4444"}[signal_state(s, k)]
        x, y = pt(k, STOP + 14, HALF + 12)
        ax.add_patch(Circle((x, y), 8, color=colour, ec="white", lw=1.5))

    for lbl, (x, y) in {"N": (0, 268), "S": (0, -272), "E": (268, 0), "W": (-272, 0)}.items():
        ax.text(x, y, lbl, color="#93c5fd", fontsize=12, ha="center", va="center", fontweight="bold")

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
                               color="#ff3d00" if flash else "white", ec="white", lw=1))
    return fig


# ---------- styling ----------
st.markdown("""
<style>
@keyframes pulse {0%{box-shadow:0 0 0 0 rgba(255,61,0,.7)}70%{box-shadow:0 0 0 14px rgba(255,61,0,0)}100%{box-shadow:0 0 0 0 rgba(255,61,0,0)}}
.hero{background:linear-gradient(120deg,#6a11cb,#2575fc,#00c9a7);border-radius:18px;padding:18px 22px;color:white;margin-bottom:14px;box-shadow:0 6px 20px rgba(0,0,0,.25)}
.hero h2{margin:0;font-size:28px;color:white}
.hero p{margin:4px 0 0 0;opacity:.95}
.card{border-radius:16px;padding:14px 10px;color:white;text-align:center;box-shadow:0 4px 14px rgba(0,0,0,.25)}
.card .num{font-size:32px;font-weight:800;line-height:1.1}
.card .lbl{font-size:13px;opacity:.95}
.c1{background:linear-gradient(135deg,#ff6a88,#ff99ac)}
.c2{background:linear-gradient(135deg,#f9d423,#ff8c42)}
.c3{background:linear-gradient(135deg,#43e97b,#38f9d7)}
.road{border-radius:14px;padding:10px 14px;margin:8px 0;color:white;box-shadow:0 3px 10px rgba(0,0,0,.2)}
.road .top{display:flex;justify-content:space-between;font-weight:700;font-size:16px}
.road .bar{height:8px;background:rgba(255,255,255,.35);border-radius:6px;margin-top:8px;overflow:hidden}
.road .bar i{display:block;height:100%;background:white;border-radius:6px}
.phase{border-radius:16px;padding:14px 18px;color:white;font-weight:700;font-size:20px;margin-bottom:10px;box-shadow:0 4px 14px rgba(0,0,0,.25)}
.amb{border-radius:16px;padding:12px 16px;color:white;font-weight:700;background:linear-gradient(90deg,#ff512f,#dd2476);animation:pulse 1.6s infinite;margin-bottom:12px}
.panel{border-radius:16px;padding:12px 16px;background:linear-gradient(135deg,#1e293b,#312e81);color:white;margin-bottom:10px}
.logline{border-left:4px solid #f472b6;padding:4px 10px;margin:6px 0;background:rgba(255,255,255,.05);border-radius:6px}
</style>
""", unsafe_allow_html=True)

# ---------- app ----------
if "sim" not in st.session_state:
    reset()

st.sidebar.header("⚙️ Settings")
if st.sidebar.button("🔄 Reset junction", use_container_width=True):
    reset()
sim = st.session_state.sim

st.sidebar.subheader("🚗 Traffic arrivals (vehicles per minute)")
for k in DIRS:
    sim["rate"][k] = st.sidebar.slider(NAMES[k], 0, 60, DEFAULT_RATE[k], key=f"rate_{k}") / 60
st.sidebar.toggle("⏸️ Pause simulation", key="paused")

st.markdown("""
<div class="hero">
  <h2>🚦 Adaptive junction control</h2>
  <p>Live simulation of North, South, East and West roads. Heavier queues get green first.</p>
</div>
""", unsafe_allow_html=True)

# Ambulance controls on the main page so they are visible on phones too
with st.container(border=True):
    st.markdown("#### 🚑 Emergency priority")
    c_a, c_b = st.columns([2, 1])
    amb_pick = c_a.selectbox("Ambulance approaching from", list(DIRS),
                             format_func=lambda k: f"{NAMES[k]} road", label_visibility="collapsed")
    if c_b.button("🚑 Send ambulance", type="primary", use_container_width=True):
        if sim["amb"]:
            log("An ambulance is already on its way")
        else:
            sim["amb"] = {"app": amb_pick, "stage": "approach", "p": 0.0}
            log(f"🚑 Ambulance requested from {NAMES[amb_pick]}")


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
        st.caption("Each coloured car is one waiting vehicle. Green time grows with the queue (6 to 30 s).")

    with right:
        if s["amb"]:
            stage = {"approach": "is on its way", "wait": "is waiting for green",
                     "pass": "is passing with green"}[s["amb"]["stage"]]
            st.markdown(f'<div class="amb">🚑 Ambulance from {NAMES[s["amb"]["app"]]} road {stage}</div>',
                        unsafe_allow_html=True)

        st.markdown(f"""
        <div class="card-row" style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:12px">
          <div class="card c1"><div class="num">{s['arrivals']}</div><div class="lbl">🚗 Arrived</div></div>
          <div class="card c2"><div class="num">{s['served']}</div><div class="lbl">✅ Through</div></div>
          <div class="card c3"><div class="num">{s['greens']}</div><div class="lbl">🔁 Cycles done</div></div>
        </div>
        """, unsafe_allow_html=True)

        if s["mode"] == "green":
            p = s["phase"]
            pct = min(100, s["t"] / s["dur"] * 100)
            st.markdown(f"""
            <div class="phase" style="background:linear-gradient(135deg,{PH_COLOURS[p]},#6a11cb)">
              🟢 {PHN[p]} green · {max(0, s['dur'] - s['t']):.0f} s left
              <div class="bar" style="height:8px;background:rgba(255,255,255,.35);border-radius:6px;margin-top:8px;overflow:hidden">
                <i style="display:block;height:100%;background:white;width:{pct:.0f}%"></i>
              </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            label = "🟡 Amber" if s["mode"] == "yellow" else "🧹 All red, clearing"
            st.markdown(f'<div class="phase" style="background:linear-gradient(135deg,#f7971e,#ffd200)">'
                        f'{label}</div>', unsafe_allow_html=True)

        for k in DIRS:
            sig = signal_state(s, k)
            text, grad = SIG_STYLE[sig]
            fill = min(100, s["q"][k] / 15 * 100)
            st.markdown(f"""
            <div class="road" style="background:{grad}">
              <div class="top"><span>{NAMES[k]}</span><span>{text}</span></div>
              <div style="font-size:14px;margin-top:4px">
                🚗 {s['q'][k]} waiting · ~{s['q'][k] * M_PER_CAR} m queue
              </div>
              <div class="bar"><i style="width:{fill:.0f}%"></i></div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("#### 📜 Event log")
        for line in s["log"][:10]:
            st.markdown(f'<div class="logline">{line}</div>', unsafe_allow_html=True)


live()

