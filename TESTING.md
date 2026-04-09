# Testing & Validation Guide

## Pre-Flight Checklist

- [ ] ESP-IDF environment configured (`$IDF_PATH` set)
- [ ] ESP32 board connected via USB
- [ ] Baud rate verified (115200)
- [ ] Python 3.6+ installed
- [ ] `pyserial` installed: `pip install pyserial`

## Building the Project

### 1. Set Environment
```bash
export IDF_PATH=/path/to/esp-idf
source $IDF_PATH/export.sh
```

### 2. Configure
```bash
cd aoa_controller
idf.py set-target esp32
idf.py menuconfig    # Optional: adjust settings
```

### 3. Build
```bash
idf.py build
```

### 4. Flash
```bash
idf.py -p /dev/ttyUSB0 flash monitor
```

## Unit Tests

### Test 1: Circular Buffer FIFO

**Objective:** Verify buffer maintains correct order and overwrites oldest value

**Manual Test:**
```c
// In main.c, add temporary test
circular_buffer_t test_buf;
circular_buffer_init(&test_buf);

circular_buffer_push(&test_buf, 1.0f);
circular_buffer_push(&test_buf, 2.0f);
circular_buffer_push(&test_buf, 3.0f);
circular_buffer_push(&test_buf, 4.0f);
circular_buffer_push(&test_buf, 5.0f);
circular_buffer_push(&test_buf, 6.0f);  // Should overwrite 1.0

assert(test_buf.sensor_values[0] == 6.0f);  // Newest at [0]
assert(test_buf.sensor_values[1] == 2.0f);  // Shifted
assert(test_buf.write_index == 1);           // Points to next write
```

**Expected Result:** PASS ✓

### Test 2: Median Calculation

**Objective:** Test median with various input combinations

**Test Cases:**
```
median(1.0, 2.0, 3.0)   → 2.0 ✓
median(3.0, 1.0, 2.0)   → 2.0 ✓
median(3.0, 2.0, 1.0)   → 2.0 ✓
median(12.0, 12.0, 15.0) → 12.0 ✓
median(-1.0, 0.0, 1.0)  → 0.0 ✓
median(5.0, 5.0, 5.0)   → 5.0 ✓
```

**Validation:**
```bash
# Add to validator.c temporarily
for all permutations of (a, b, c):
    assert(calculate_median(a,b,c) == middle_value)
```

### Test 3: Outlier Detection

**Objective:** Verify outliers marked INVALID correctly

**Scenario:**
```
S1 = 12.0° (sensor 1)
S2 = 12.5° (sensor 2)
S3 = 15.0° (sensor 3)

Median = 12.5°
|12.0 - 12.5| = 0.5° < 5.0° → VALID ✓
|12.5 - 12.5| = 0.0° < 5.0° → VALID ✓
|15.0 - 12.5| = 2.5° < 5.0° → VALID ✓
```

**Scenario with Outlier:**
```
S1 = 12.0°
S2 = 12.5°
S3 = 30.0° (sensor malfunction)

Median = 12.5°
|30.0 - 12.5| = 17.5° > 5.0° → INVALID ✗
```

### Test 4: Kalman Filter Convergence

**Objective:** Verify filter converges to constant input

**Setup:**
```
Input: constant 12.0° for 10 cycles
Initial estimate: 0.0°
Initial variance: 1.0
```

**Expected Convergence:**
```
Cycle 1: estimate ≈ 0.55°
Cycle 2: estimate ≈ 2.15°
Cycle 3: estimate ≈ 4.67°
Cycle 4: estimate ≈ 7.09°
Cycle 5: estimate ≈ 8.97°
...
Cycle 10: estimate ≈ 11.8°
Cycle ∞: estimate → 12.0°
```

**Variance:**
```
Should monotonically decrease toward steady-state
Steady-state P ≈ 0.33 (equilibrium between Q and R)
```

### Test 5: FSM State Transitions

**Objective:** Verify correct state transitions at thresholds

**Aircraft A, CRUISE Mode:**
```
Limits: Low=3.0°, High=22.0°
Thresholds:
  NORMAL:     AoA ≤ 20.0°
  CAUTION:    20.0° < AoA ≤ 21.5°
  PROTECTION: 21.5° < AoA < 22.0°
  OVERRIDE:   AoA ≥ 22.0°
```

**Test Sweep:**
```
AoA=10.0° → NORMAL (LED OFF) ✓
AoA=19.9° → NORMAL (LED OFF) ✓
AoA=20.0° → CAUTION (LED blink 500ms) ✓
AoA=21.5° → PROTECTION (LED blink 200ms) ✓
AoA=22.0° → OVERRIDE (LED solid ON) ✓
AoA=25.0° → OVERRIDE (LED solid ON) ✓
```

## Integration Tests

### Test Setup
```bash
# Terminal 1: Monitor output
cd aoa_controller
python3 tools/monitor.py --port /dev/ttyUSB0 --output flight_log.csv

# Terminal 2: Send simulation data
python3 tools/send_sim_data.py --port /dev/ttyUSB0 --interval 50
```

### Test 6: Complete Data Flow (Happy Path)

**Input Sequence:**
```
$AOA,S1=12.0,S2=12.5,S3=12.2,TS=0*
$FLIGHT_PARAMS,AIRSPEED=210,TS=1*
$FLIGHT_MODE,MODE=CRUISE,TS=2*
```

**Expected Output (after 20ms):**
```
IDX=0001 TS=0 MODE=CRUISE S1=12.00 S2=12.50 S3=12.20 AIRSPEED=210.0 AOA=12.23 STATUS=NORMAL
```

**Verify:**
- Median: 12.2° ✓
- All sensors valid (within 5° of median) ✓
- Kalman filter stabilizes around 12.2° ✓
- FSM: NORMAL (AoA < 20°) ✓
- LED: OFF ✓

### Test 7: Outlier Rejection

**Input Sequence:**
```
$AOA,S1=12.0,S2=12.5,S3=30.0,TS=100*  ← S3 is outlier
$FLIGHT_PARAMS,AIRSPEED=210,TS=101*
```

**Expected Output:**
```
IDX=0005 TS=100 ... S1=12.00 S2=12.50 S3=30.00 AOA=12.25 STATUS=NORMAL
```

**Validation:**
- Median: 12.5° (center of S1, S2) ✓
- S3 invalid: |30.0 - 12.5| = 17.5° > 5.0° ✓
- Fusion uses only S1, S2 (2/3 sensors valid) ✓
- Output AOA ≈ (12.0 + 12.5)/2 = 12.25° ✓

### Test 8: Stall Detection (FSM OVERRIDE)

**Input Sequence:**
```
$AOA,S1=22.0,S2=22.1,S3=22.2,TS=300*  ← Stall angle!
$FLIGHT_PARAMS,AIRSPEED=210,TS=301*
```

**Expected Output:**
```
IDX=0016 TS=300 ... AOA=22.10 STATUS=OVERRIDE
```

**Verification:**
- AoA = 22.10° ≥ limit (22.0°) ✓
- FSM state: OVERRIDE ✓
- LED: Solid ON (no blink) ✓
- Action: Full elevator override active ✓

### Test 9: Sensor Loss Tolerance

**Scenario:** Sensor 1 fails (stuck at 50°)

**Input Sequence:**
```
$AOA,S1=50.0,S2=12.5,S3=12.2,TS=500*  ← S1 failed
$FLIGHT_PARAMS,AIRSPEED=210,TS=501*
```

**Expected Output:**
```
IDX=0026 TS=500 ... S1=50.00 S2=12.50 S3=12.20 AOA=12.35 STATUS=NORMAL
```

**Validation:**
- Median: 12.5° ✓
- S1 invalid: |50.0 - 12.5| = 37.5° > 5.0° ✓
- System operates with S2, S3 only ✓
- Output: 2 valid sensors sufficient ✓

### Test 10: Full Mission Profile

**Scenario:** Simulated flight from takeoff to cruise

**Expected Sequence:**
```
Time 0-100ms:   Initialization, NORMAL
Time 100-200ms: AoA values ~12-13°, NORMAL
Time 200-300ms: AoA ramps to 20°, CAUTION threshold
Time 300-400ms: AoA = 21°, PROTECTION state
Time 400-500ms: AoA = 22.5°, OVERRIDE (stall!)
Time 500-600ms: AoA returns to 15°, back to CAUTION
Time 600+:      Stable cruise, NORMAL
```

## Performance Tests

### Test 11: Response Latency

**Objective:** Measure delay from sensor input to LED output

**Method:**
1. Send AoA message that crosses FSM threshold
2. Measure time until LED changes state
3. Repeat 10 times, calculate average

**Expected Result:**
```
Latency: 20-40ms (1-2 control cycles)
Max: <60ms
```

### Test 12: CPU Utilization

**Objective:** Verify control loop occupies <10% of CPU

**Measurement:**
```c
// Add to main.c
uint32_t cycle_start = esp_timer_get_time();
// ... run cycle ...
uint32_t cycle_time = esp_timer_get_time() - cycle_start;

float utilization = 100.0 * cycle_time / (CONTROL_CYCLE_PERIOD_MS * 1000);
ESP_LOGI(TAG, "Cycle time: %lu µs (%.1f%% utilization)", cycle_time, utilization);
```

**Expected Result:**
```
Cycle time: <1500 µs
Utilization: <7.5%
```

### Test 13: Data Throughput

**Objective:** Verify system handles maximum UART input rate

**Method:**
1. Send messages at 100 Hz (every 10ms)
2. Monitor for dropped messages
3. Check log output frequency

**Expected Result:**
```
Input rate: 100 msg/sec
Output rate: 50 log/sec (control cycle limited)
Dropped: 0 messages
```

## Regression Tests

Run after any code changes:

```bash
# Full suite
./run_tests.sh

# Individual modules
./test_validator.sh
./test_estimator.sh
./test_fsm.sh
```

## Logging Output Analysis

### Parse CSV Log
```bash
python3 -c "
import csv
with open('flight_log.csv') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if 'AOA' in row:
            aoa = float(row['AOA'])
            status = row['STATUS']
            print(f'{aoa:.2f}° → {status}')
"
```

### Generate Statistics
```bash
python3 << 'EOF'
import csv
import statistics

aoa_values = []
with open('flight_log.csv') as f:
    reader = csv.reader(f)
    next(reader)  # Skip header
    for row in reader:
        try:
            aoa = float(row[6])  # AOA column
            aoa_values.append(aoa)
        except:
            pass

print(f"Mean AoA: {statistics.mean(aoa_values):.2f}°")
print(f"StdDev:   {statistics.stdev(aoa_values):.2f}°")
print(f"Min:      {min(aoa_values):.2f}°")
print(f"Max:      {max(aoa_values):.2f}°")
EOF
```

## Failure Mode Testing

### Test F1: Corrupt UART Message
**Input:**
```
$AOA,S1=GARBAGE,S2=12.5,S3=12.2,TS=0*
```
**Expected:** Message rejected, no crash ✓

### Test F2: Missing Checksum
**Input:**
```
$AOA,S1=12.0,S2=12.5,S3=12.2,TS=0
```
**Expected:** Message accepted (no validation required) ✓

### Test F3: Out-of-Range Values
**Input:**
```
$AOA,S1=100.0,S2=12.5,S3=12.2,TS=0*  ← S1 out of range
```
**Expected:** Message rejected ✓

### Test F4: Simultaneous Sensor Loss
**Scenario:** All 3 sensors fail

**Expected Behavior:**
- num_valid_sensors = 0
- Fusion returns 0.0°
- FSM uses last known AoA or defaults to NORMAL
- System remains safe (doesn't crash)

## Certification & Sign-Off

**Test Execution Checklist:**
- [ ] Unit Tests 1-5 (passed)
- [ ] Integration Tests 6-10 (passed)
- [ ] Performance Tests 11-13 (within spec)
- [ ] Regression Tests (all passed)
- [ ] Failure Mode Tests F1-F4 (handled gracefully)

**Sign-Off:**
```
Tested by: ________________________
Date:      ________________________
Status:    ☐ PASS   ☐ FAIL
```

## Next Steps

1. **Review Code Coverage:** Aim for >90% on critical modules
2. **Load Testing:** Run for 24+ hours with realistic data
3. **Environmental Testing:** Temperature, vibration, EMI
4. **Flight Testing:** Real aircraft validation

---
*For issues, see DEVELOPMENT.md Debugging Tips section*
