#!/usr/bin/env python3

import serial
import time
import argparse
import sys
import csv
from datetime import datetime

class SerialMonitor:
    def __init__(self, port, baud_rate, output_file=None):
        self.port = port
        self.baud_rate = baud_rate
        self.output_file = output_file
        self.ser = None
        self.csv_writer = None
        self.csv_file = None
        self.start_time = datetime.now()
        
    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baud_rate, timeout=1)
            print(f"Connected to {self.port} at {self.baud_rate} baud")
            time.sleep(2)
            
            if self.output_file:
                self.csv_file = open(self.output_file, 'w', newline='')
                self.csv_writer = csv.writer(self.csv_file)
                self.csv_writer.writerow([
                    'Timestamp', 'Message', 'Type'
                ])
                print(f"Logging to {self.output_file}")
            
            return True
        except serial.SerialException as e:
            print(f"Connection Error: {e}")
            return False
    
    def parse_log_message(self, line):
        fields = {}
        parts = line.split()
        for part in parts:
            if '=' in part:
                key, value = part.split('=', 1)
                fields[key] = value
        return fields
    
    def is_log_message(self, line):
        return 'IDX=' in line and 'STATUS=' in line
    
    def monitor(self):
        if not self.connect():
            return False
        
        print("\nMonitoring output (Ctrl+C to stop)...\n")
        print("-" * 100)
        
        try:
            while True:
                if self.ser.in_waiting:
                    try:
                        line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                        if line:
                            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                            
                            msg_type = "LOG" if self.is_log_message(line) else "DEBUG"
                            
                            if msg_type == "LOG":
                                fields = self.parse_log_message(line)
                                print(f"[{timestamp}] {msg_type:5s} | IDX={fields.get('IDX', '?'):4s} "
                                      f"AOA={fields.get('AOA', '?'):7s} "
                                      f"STATUS={fields.get('STATUS', '?'):12s} "
                                      f"S1={fields.get('S1', '?'):7s} "
                                      f"S2={fields.get('S2', '?'):7s} "
                                      f"S3={fields.get('S3', '?'):7s}")
                            else:
                                print(f"[{timestamp}] {msg_type:5s} | {line}")
                            
                            if self.csv_writer:
                                self.csv_writer.writerow([timestamp, line, msg_type])
                                self.csv_file.flush()
                    
                    except Exception as e:
                        print(f"Parse Error: {e}")
                
                time.sleep(0.01)
        
        except KeyboardInterrupt:
            print("\n" + "-" * 100)
            print("\nMonitoring stopped by user")
        
        finally:
            self.disconnect()
        
        return True
    
    def disconnect(self):
        if self.csv_file:
            self.csv_file.close()
            print(f"Log file saved: {self.output_file}")
        
        if self.ser:
            self.ser.close()
            print(f"Disconnected from {self.port}")

def main():
    parser = argparse.ArgumentParser(
        description='Monitor Aircraft AoA Safety Controller UART output'
    )
    parser.add_argument('--port', default='/dev/ttyUSB0',
                        help='Serial port (default: /dev/ttyUSB0)')
    parser.add_argument('--baud', type=int, default=115200,
                        help='Baud rate (default: 115200)')
    parser.add_argument('--output', default=None,
                        help='Output CSV file for logging (optional)')
    
    args = parser.parse_args()
    
    print("=" * 100)
    print("Aircraft AoA Safety Controller - Serial Monitor")
    print("=" * 100)
    print(f"Port: {args.port}")
    print(f"Baud Rate: {args.baud}")
    if args.output:
        print(f"Log File: {args.output}")
    print("=" * 100)
    
    monitor = SerialMonitor(args.port, args.baud, args.output)
    success = monitor.monitor()
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
