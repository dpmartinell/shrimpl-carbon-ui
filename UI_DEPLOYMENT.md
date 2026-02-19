# Shrimpl Carbon Footprint Prototype UI (Streamlit)

This folder contains a Streamlit prototype that wraps the cycle-based estimator.

## Run locally

From this folder:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## How the polygon/soil part works (prototype)

- You paste polygon coordinates as JSON (lon/lat, EPSG:4326).
- The app computes **geodesic area** (ha) with `pyproj.Geod`.
- For soil/LULUC automation, the app tries to fetch **SoilGrids SOC** through the **WCS** service (more stable than the REST API).
  - It currently computes a *bbox mean* for simplicity; for production, clip to polygon.

If SoilGrids is unreachable, you can still run the tool by selecting the soil type manually.

## Deploy online (simple)

### Option A — Streamlit Community Cloud
1) Push this folder to a GitHub repo.
2) In Streamlit Community Cloud, select the repo and set:
   - **Main file path:** `estimation_final/streamlit_app.py`
3) Streamlit will install `requirements.txt` automatically.

### Option B — Render
Render supports Streamlit with a simple web service. Use:
- Build command: `pip install -r requirements.txt`
- Start command: `streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0`

(You can use Community Cloud first; it's easiest for a prototype.)
