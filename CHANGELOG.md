# Changelog

## Unreleased

### Changes
- Gate control loop until the first UART data arrives.
- CSV sender now converts rows into firmware UART messages ($AOA, $FLIGHT_MODE, $FLIGHT_PARAMS) with trailing `*` for parsing.
- Added a single-process serial duplex helper to send and receive on one COM port.
- Added a multi-mode demo dataset that exercises NORMAL/CAUTION/PROTECTION/OVERRIDE and returns to NORMAL.
- LED blinking now runs in a dedicated FreeRTOS task so it can blink independently of log writes.

### Commands

Build + flash:

```bash
idf.py build
idf.py flash
```

Run the demo dataset (single process, read + write, ends in NORMAL):

```bash
python tools/serial_duplex.py --port /dev/cu.usbserial-0001 --baud 115200 --file components/aoa_controller/data/sim_state_demo.csv --send-all-once --interval 1000 --finish-normal
```

Alternate sender (CSV -> UART messages):

```bash
python tools/send_sim_data.py --port COM6 --baud 115200 --file components/aoa_controller/data/sim_state_demo.csv --interval 1000
```

Notes:
- If you want longer time per state, increase `--interval`.
- The duplex helper keeps one COM handle open to avoid PermissionError from two processes.
