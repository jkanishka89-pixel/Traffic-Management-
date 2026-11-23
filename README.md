Adaptive Junction Control: Intelligent Traffic Management Demo

A live, interactive simulation of a four-way junction (North, South, East, West) that shows how an intelligent traffic system can monitor vehicle counts, estimate queue length, prioritise heavier traffic, adjust signal timings, and give way to emergency vehicles. No cameras or hardware are needed.

Features

• Live junction: Four approaches with queues, stop lines and signal lights.
• Vehicle counting: Each road has its own arrival rate, adjustable with sliders.
• Queue length estimate: Waiting vehicles converted to metres (about 7 m per vehicle).
• Smart signal: The phase with more waiting vehicles gets green first. A phase that has waited 45 seconds is served regardless, so no road is starved.
• Adaptive timing: Green lasts 6 to 30 seconds, growing with the queue, and switches early when a queue clears.
• Emergency priority: Send an ambulance from any approach. It gets green as soon as it reaches the stop line, then normal control resumes.
• Live dashboard: Vehicle counts, signal status, current phase with countdown, completed green phases, and an event log.

Two versions

File
What it is
How to run
junction_app.py
Streamlit app (Python)
streamlit run junction_app.py
adaptive_junction_demo.html
Single-file browser demo
Double-click to open in Chrome

Both versions use the same logic.

Requirements

• Python 3.9 or newer
• Chrome, Edge, or any modern browser

Setup and run (Streamlit version)

# 1. Create and activate a virtual environment (recommended)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the demo
streamlit run junction_app.py

Streamlit opens the demo at http://localhost:8501. If it does not open automatically, paste that address into Chrome.

How the control logic works

1. Vehicles arrive randomly on each road at the rate set by its slider.
2. The signal chooses the next phase (North–South or East–West). It picks the one with more vehicles waiting. If both are equal, it alternates. If one phase has been waiting 45 seconds, it goes next.
3. Green time is 4 + 2.5 × waiting vehicles on the phase, clamped to 6–30 seconds.
4. Green ends early if the phase's queue clears after the minimum 6 seconds.
5. Each phase change includes 2 seconds of amber and 1 second of all-red.
6. An ambulance is detected 3 seconds after it is sent. Its approach gets green after the current amber, with 8 seconds of priority. Then normal control resumes.

Limitations

This is a teaching simulation, not a real traffic model:

• Arrivals are random, and a car leaves every 2 seconds while its approach has green.
• Queue length is estimated from the vehicle count, not measured.
• The ambulance drives through the junction on a simplified path.
• The demo does not model turning movements, pedestrians, or sensors.

Ideas for extension

• Add a fixed-timing mode and compare average waiting time against the adaptive mode.
• Replace the random arrivals with recorded or real camera counts.
• Add more phases for turning lanes or a pedestrian crossing.

Project structure

.
├── junction_app.py          # Streamlit app: simulation, controller and dashboard
├── requirements.txt         # Python dependencies
├── adaptive_junction_demo.html  # Standalone browser version
├── README.md
└── .gitignore

Deploying a public link (optional)

1. Push this folder to a GitHub repository.
2. Sign in at share.streamlit.io with your GitHub account.
3. Click Create app, pick the repository, and set the main file to junction_app.py.

Streamlit Community Cloud gives you a public https:// link.
