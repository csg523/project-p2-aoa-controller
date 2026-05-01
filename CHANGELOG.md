# Changelog

## Unreleased

### Changes
- **Added AoA Controller GUI** (`tools/gui.py`) — PyQt5 desktop application with:
  - Static input mode (manual S1/S2/S3/Airspeed entry)
  - Dynamic input mode (real-time CSV streaming from `sim_input.csv`)
  - Real-time AoA signal plot (PyQtGraph)
  - Flight animation with pitch rotation and submode color coding
  - Submode indicators (NORMAL / CAUTION / PROTECTION / OVERRIDE)
  - LED simulation (green steady / amber-orange-red blinking)
  - Pilot / Autopilot toggle (locked during OVERRIDE)
  - Live threshold info display showing CAUTION/PROTECTION/OVERRIDE boundaries
- **Added backend bridge** (`tools/aoa_backend.py`) — reuses all core logic from `simulate_pipeline.py` (validator, Kalman estimator, FSM, thresholds)
- Gate control loop until the first UART data arrives.
- CSV sender now converts rows into firmware UART messages ($AOA, $FLIGHT_MODE, $FLIGHT_PARAMS) with trailing `*` for parsing.
- Added a single-process serial duplex helper to send and receive on one COM port.
- Added a multi-mode demo dataset that exercises NORMAL/CAUTION/PROTECTION/OVERRIDE and returns to NORMAL.
- LED blinking now runs in a dedicated FreeRTOS task so it can blink independently of log writes.

### Bug Fixes (v2)
- **Fixed LED not blinking in static mode** — Increased Kalman convergence iterations from 30 → 50 so the filter fully reaches the true AoA value when the user enters sensor readings above the threshold.
- **Fixed dynamic mode always showing NORMAL** — The `sim_input.csv` dataset had no stall conditions. Replaced with a comprehensive dataset that includes gradual ramps into CAUTION, PROTECTION, and OVERRIDE zones across TAKEOFF, CRUISE, and LANDING modes. Each stall region has enough sustained high-AoA rows (8–14 rows) for the Kalman filter to converge before recovery.
- **Added threshold info bar** — Displays the active CAUTION/PROTECTION/OVERRIDE boundaries for the current flight mode so users know what sensor values are needed to trigger each submode.

---

### Setup & Run (Quick Start)

#### Prerequisites

- **Python 3.8+** (tested with Anaconda Python 3.13)
- **pip** package manager

#### 1. Install Dependencies

```bash
pip install PyQt5 pyqtgraph numpy pyserial
```

#### 2. Flash Firmware to ESP32-CAM

```bash
idf.py build
idf.py flash
```

#### 3. Launch the GUI

**Option A** — Using the shell script:

```bash
chmod +x run_gui.sh
./run_gui.sh
```

**Option B** — Direct Python launch (recommended if Option A fails):

```bash
cd <project-root>
python tools/gui.py
```

#### 4. Connect ESP32 Serial Port

1. Plug in the ESP32-CAM via USB.
2. In the **ESP32 SERIAL PORT** panel at the bottom of the GUI:
   - Select the port (e.g. `/dev/cu.usbserial-0001`) from the dropdown.
   - Click **🔌 CONNECT** — status should turn green.
   - Ensure **"Send to ESP32"** checkbox is checked.
3. The serial log at the bottom will show `RX:` lines from the ESP32 firmware.

#### 5. Using Static Mode (Manual Input)

1. Select a **Flight Mode** from the left panel (TAKEOFF / CLIMB / CRUISE / LANDING).
2. Enter sensor values in the top bar:
   - **AIRSPEED** — e.g. `200`
   - **S1, S2, S3** — Angle-of-Attack sensor readings in degrees
3. Click **▶ SEND**.
4. The threshold info bar at the bottom shows the active limits:

| Flight Mode | CAUTION > | PROTECTION > | OVERRIDE > |
|-------------|-----------|--------------|------------|
| TAKEOFF     | 16.0°     | 17.5°        | 18.0°      |
| CLIMB       | 18.0°     | 19.5°        | 20.0°      |
| CRUISE      | 20.0°     | 21.5°        | 22.0°      |
| LANDING     | 18.0°     | 19.5°        | 20.0°      |

**Example static inputs to test each submode:**

| Submode    | Mode   | S1   | S2   | S3   | Airspeed |
|------------|--------|------|------|------|----------|
| NORMAL     | CRUISE | 10   | 10   | 10   | 250      |
| CAUTION    | CRUISE | 21   | 21   | 21   | 250      |
| PROTECTION | CRUISE | 22   | 22   | 22   | 250      |
| OVERRIDE   | CRUISE | 23   | 23   | 23   | 250      |

#### 6. Using Dynamic Mode (CSV Streaming)

1. Switch **INPUT MODE** dropdown to **Dynamic (CSV)**.
2. Click **▶ START** to stream `sim_input.csv`.
3. The dataset automatically cycles through all 4 submodes across 3 flight phases:
   - **TAKEOFF** — ramps to OVERRIDE at ~row 32, then recovers
   - **CRUISE** — ramps to OVERRIDE at ~row 80, then recovers
   - **LANDING** — ramps to OVERRIDE at ~row 113, then recovers
4. Use the **Speed** slider to control playback rate.
5. Click **⏹ STOP** to halt early.

---

### Firmware Commands

Build + flash (firmware):

```bash
idf.py build
idf.py flash
```

Run the demo dataset (single process, read + write, ends in NORMAL):

```bash
python tools/serial_duplex.py --port /dev/cu.usbserial-0001 --baud 115200 --file components/aoa_controller/data/sim_state_demo.csv --send-all-once --interval 1000 --finish-normal
```

Alternate sender (CSV → UART messages):

```bash
python tools/send_sim_data.py --port COM6 --baud 115200 --file components/aoa_controller/data/sim_state_demo.csv --interval 1000
```

### Troubleshooting

- **`ModuleNotFoundError: No module named 'numpy'`** — Run `pip install PyQt5 pyqtgraph numpy` in the same Python environment.
- **LED doesn't blink** — Make sure your S1/S2/S3 values exceed the CAUTION threshold for the selected flight mode (see table above).
- **Submodes stuck on NORMAL in dynamic mode** — The Kalman filter needs several consecutive high-AoA readings to converge. The updated `sim_input.csv` includes gradual ramp-ups for this purpose.
- If `./run_gui.sh` fails, run `python tools/gui.py` directly from the project root.
- If you want longer time per state, increase `--interval`.
- The duplex helper keeps one COM handle open to avoid PermissionError from two processes.
