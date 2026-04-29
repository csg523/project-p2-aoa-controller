#!/usr/bin/env python3
"""
Open a single COM port, spawn a reader thread to print incoming lines,
and send messages (from CSV or interactive) on the same port.

Usage examples:
  python tools/serial_duplex.py --port COM6 --baud 115200 --file components/aoa_controller/data/sim_input.csv --send-all-once --interval 200
  python tools/serial_duplex.py --port COM6 --baud 115200 --file components/aoa_controller/data/sim_input.csv --once
  python tools/serial_duplex.py --port COM6 --baud 115200 --interactive

This avoids the PermissionError because only one process opens the COM port.
"""

import argparse
import threading
import time
import serial
import csv
import sys
from typing import List, Tuple, Optional


def read_messages_from_csv(filename: str) -> Tuple[List[List[str]], Optional[int]]:
    """Return a list of message groups. Each group is a list of strings
    (AOA, optional FLIGHT_MODE, optional FLIGHT_PARAMS) for a single CSV row.
    Also return the last timestamp seen.
    """
    groups: List[List[str]] = []
    last_ts: Optional[int] = None
    try:
        with open(filename, 'r', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                s1 = row.get('s1')
                s2 = row.get('s2')
                s3 = row.get('s3')
                ts = row.get('ts')
                mode = (row.get('mode') or '').strip()
                airspeed = row.get('airspeed')
                if not s1 or not s2 or not s3 or not ts:
                    continue
                ts_int = int(float(ts))
                last_ts = ts_int
                group: List[str] = []
                group.append(f"$AOA,S1={s1},S2={s2},S3={s3},TS={ts_int}*")
                if mode:
                    group.append(f"$FLIGHT_MODE,MODE={mode},TS={ts_int}*")
                if airspeed:
                    group.append(f"$FLIGHT_PARAMS,AIRSPEED={airspeed},TS={ts_int}*")
                groups.append(group)
        return groups, last_ts
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found", file=sys.stderr)
        return [], None


def build_finish_group(ts: Optional[int]) -> List[str]:
    ts_val = (ts + 20) if ts is not None else 0
    return [
        f"$AOA,S1=5.00,S2=5.00,S3=5.00,TS={ts_val}*",
        f"$FLIGHT_MODE,MODE=CRUISE,TS={ts_val}*",
        f"$FLIGHT_PARAMS,AIRSPEED=200.0,TS={ts_val}*",
    ]


def reader_thread(ser: serial.Serial, stop_event: threading.Event):
    try:
        while not stop_event.is_set():
            try:
                line = ser.readline()
            except Exception:
                break
            if not line:
                continue
            try:
                text = line.decode('utf-8', errors='ignore').rstrip('\r\n')
            except Exception:
                text = repr(line)
            print(f"RX: {text}")
    finally:
        stop_event.set()


def main():
    parser = argparse.ArgumentParser(description='Serial duplex helper (single process read+write)')
    parser.add_argument('--port', required=True, help='Serial port (e.g. COM6)')
    parser.add_argument('--baud', type=int, default=115200)
    parser.add_argument('--file', default=None, help='CSV input file to send')
    parser.add_argument('--interval', type=int, default=100, help='ms between message groups')
    parser.add_argument('--once', action='store_true', help='send only the first set of messages and exit')
    parser.add_argument('--send-all-once', action='store_true', help='send the entire CSV once and exit')
    parser.add_argument('--finish-normal', action='store_true', help='send a final normal group so LED ends OFF')
    parser.add_argument('--interactive', action='store_true', help='enter interactive send mode (type lines to send)')
    args = parser.parse_args()

    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.5)
    except Exception as e:
        print(f"Failed to open {args.port}: {e}", file=sys.stderr)
        sys.exit(1)

    stop_event = threading.Event()
    t = threading.Thread(target=reader_thread, args=(ser, stop_event), daemon=True)
    t.start()

    try:
        msgs: List[List[str]] = []
        last_ts: Optional[int] = None
        if args.file:
            msgs, last_ts = read_messages_from_csv(args.file)
            if not msgs:
                print("No messages loaded from CSV or file missing.")

        if args.once and msgs:
            print("Sending first message group...")
            for m in msgs[0]:
                ser.write(m.encode() + b'\n')
                print(f"TX: {m}")
                time.sleep(0.02)
            time.sleep(0.2)
            print("Done.")
            return

        if args.send_all_once and msgs:
            total_msgs = sum(len(g) for g in msgs)
            print(f"Sending {total_msgs} messages (in {len(msgs)} groups) once to {args.port}...")
            for group in msgs:
                for m in group:
                    ser.write(m.encode() + b'\n')
                    print(f"TX: {m}")
                    time.sleep(0.02)
                time.sleep(args.interval / 1000.0)
            if args.finish_normal:
                finish_group = build_finish_group(last_ts)
                print("Sending final NORMAL group so LED ends OFF...")
                for m in finish_group:
                    ser.write(m.encode() + b'\n')
                    print(f"TX: {m}")
                    time.sleep(0.02)
            time.sleep(0.5)
            print("Done sending all messages.")
            return

        if args.file and msgs:
            print(f"Sending {len(msgs)} groups to {args.port} every {args.interval}ms. Ctrl-C to stop.")
            idx = 0
            while True:
                group = msgs[idx % len(msgs)]
                for m in group:
                    ser.write(m.encode() + b'\n')
                    print(f"TX: {m}")
                    time.sleep(0.02)
                idx += 1
                time.sleep(args.interval / 1000.0)

        elif args.interactive:
            print("Interactive mode. Type lines to send; Ctrl-D or Ctrl-C to exit.")
            try:
                for line in sys.stdin:
                    line = line.rstrip('\n')
                    if not line:
                        continue
                    ser.write(line.encode() + b'\n')
                    print(f"TX: {line}")
            except KeyboardInterrupt:
                pass

        else:
            print("No send action specified (provide --file or --interactive). Reader still running; Ctrl-C to exit.")
            while not stop_event.is_set():
                time.sleep(0.1)

    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        try:
            ser.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
