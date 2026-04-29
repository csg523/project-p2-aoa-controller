#!/usr/bin/env python3

import serial
import time
import argparse
import sys
import csv

def read_messages_from_csv(filename):
    messages = []
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
                messages.append(f"$AOA,S1={s1},S2={s2},S3={s3},TS={ts_int}*")

                if mode:
                    messages.append(f"$FLIGHT_MODE,MODE={mode},TS={ts_int}*")

                if airspeed:
                    messages.append(f"$FLIGHT_PARAMS,AIRSPEED={airspeed},TS={ts_int}*")

        return messages
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found")
        return None

def send_messages(port, baud_rate, messages, interval_ms, dry_run=False):
    if dry_run:
        print("Running in dry-run mode: not opening serial port.")
        for idx, message in enumerate(messages):
            print(f"[{idx+1}/{len(messages)}] (dry) Sending: {message}")
            time.sleep(interval_ms / 1000.0)
        print(f"\n(dry) Sent {len(messages)} messages successfully")
        return

    try:
        ser = serial.Serial(port, baud_rate, timeout=1)
        print(f"Connected to {port} at {baud_rate} baud")
        
        time.sleep(2)
        
        for idx, message in enumerate(messages):
            print(f"[{idx+1}/{len(messages)}] Sending: {message}")
            ser.write(message.encode() + b'\n')
            time.sleep(interval_ms / 1000.0)
        
        print(f"\nSent {len(messages)} messages successfully")
        
        print("Monitoring output (Ctrl+C to exit)...")
        try:
            while True:
                if ser.in_waiting:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        print(f"RX: {line}")
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        
        ser.close()
        
    except serial.SerialException as e:
        print(f"Serial Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description='Send simulation data to Aircraft AoA Safety Controller'
    )
    parser.add_argument('--port', default='/dev/ttyUSB0',
                        help='Serial port (default: /dev/ttyUSB0)')
    parser.add_argument('--baud', type=int, default=115200,
                        help='Baud rate (default: 115200)')
    parser.add_argument('--interval', type=int, default=100,
                        help='Message interval in milliseconds (default: 100)')
    parser.add_argument('--file', default='components/aoa_controller/data/sim_input.csv',
                        help='Input CSV file (default: components/aoa_controller/data/sim_input.csv)')
    parser.add_argument('--dry-run', action='store_true', help='Print messages to stdout instead of sending to serial')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Aircraft AoA Safety Controller - Simulation Data Sender")
    print("=" * 60)
    print(f"Port: {args.port}")
    print(f"Baud Rate: {args.baud}")
    print(f"Message Interval: {args.interval}ms")
    print(f"Input File: {args.file}")
    print("-" * 60)
    
    messages = read_messages_from_csv(args.file)
    if messages is None:
        sys.exit(1)
    
    print(f"Loaded {len(messages)} messages from {args.file}")
    print("-" * 60)
    
    input("Press Enter to start sending data...")
    send_messages(args.port, args.baud, messages, args.interval, dry_run=args.dry_run)

if __name__ == '__main__':
    main()
