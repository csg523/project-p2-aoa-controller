# Aircraft AoA Safety Controller - Development Notes

## Event-Driven Architecture Principles

This firmware strictly adheres to **100% event-driven execution** with NO polling:

### ✅ CORRECT - Event-Driven
```c
/* Task waits for event, wakes only when needed */
xEventGroupWaitBits(event_group, BIT_RUN_CYCLE, pdTRUE, pdFALSE, portMAX_DELAY);
/* Process data */
/* Sleep until next event */
```

### ❌ WRONG - Polling (NOT USED)
```c
/* Never do this - wastes CPU */
while (1) {
    vTaskDelay(pdMS_TO_TICKS(20));
    process_data();
}
```

## Key Design Decisions

### 1. Dual-Core Execution
- **Core 0**: HAL Input Task (UART reception, low priority)
- **Core 1**: Control Task (main logic, high priority)
- Prevents UART latency from blocking control loop

### 2. Mutex-Protected Data
```
sensor_data_t {
    circular_buffer_t sensor1_buffer;
    circular_buffer_t sensor2_buffer;
    circular_buffer_t sensor3_buffer;
    SemaphoreHandle_t buffer_mutex;  /* Protects all buffers */
}
```

**Locking Pattern:**
```c
hal_lock_sensor_data();
/* Read/write buffer data */
hal_unlock_sensor_data();
```

### 3. EventGroup Synchronization
```
BIT_DATA_READY (Bit 0)  → New sensor data available
BIT_RUN_CYCLE (Bit 1)   → Control cycle ready to execute
```

**Important:** Main task only uses `BIT_RUN_CYCLE` (timer-driven).
Data availability doesn't trigger immediate processing.

### 4. Circular Buffer Design
```
Buffer State: [13.2, 12.8, 13.1, 0.0, 0.0]  (write_index = 3)
                  ↑
            Newest value

After push(13.0):
Buffer State: [13.0, 13.2, 12.8, 13.1, 0.0]  (write_index = 1)
              ↑
          New newest
```

**Read newest:** `buffer->sensor_values[(write_index - 1) % BUFFER_SIZE]`

### 5. Median Calculation (No Sorting Required)
```c
float calculate_median(float v1, float v2, float v3) {
    if (v1 > v2) {
        if (v2 > v3) return v2;     /* v1 > v2 > v3 */
        else if (v1 > v3) return v3; /* v1 > v3 >= v2 */
        else return v1;              /* v3 >= v1 > v2 */
    } else {
        if (v1 > v3) return v1;     /* v2 >= v1 > v3 */
        else if (v2 > v3) return v3; /* v2 > v3 >= v1 */
        else return v2;              /* v3 >= v2 >= v1 */
    }
}
```
**Complexity:** O(1), no heap allocation, deterministic time.

## Mathematical Algorithms

### Weighted Fusion
**Concept:** Each sensor contributes proportionally to its reliability.

**Implementation:**
```
Weight(i) = 1 / error(i)      /* Inverse error */
Normalized_Weight(i) = Weight(i) / Sum(Weights)
Fused_AoA = Sum(Normalized_Weight(i) * Sensor(i))
```

**Example:**
```
S1=12.0°, S2=12.5°, S3=12.2° (all valid)
Weight = 1.0 for all (error=1.0)
Normalized = 1/3 each
Fused = (1/3)*12.0 + (1/3)*12.5 + (1/3)*12.2 = 12.23°
```

### 1D Kalman Filter
**State:** `[estimated_aoa, estimated_variance]`

**Equations:**
```
/* Predict */
x_prior = x_prev                              (no dynamics)
P_prior = P_prev + Q                          (Q = process noise)

/* Update */
K = P_prior / (P_prior + R)                   (Kalman gain)
x_new = x_prior + K * (z - x_prior)           (measurement z)
P_new = (1 - K) * P_prior                     (variance update)
```

**Parameters:**
```
Q = 0.01    (Process Noise: AoA is stable)
R = 0.5     (Measurement Noise: Sensor uncertainty)
```

**Behavior:**
- High Q: Filter trusts measurements more
- High R: Filter trusts estimates more

### FSM State Machine
```
Input: calculated_aoa
Thresholds: aoa_low, aoa_high

if (aoa > aoa_high)
    → OVERRIDE (stall protection)
else if (aoa > aoa_high - 0.5°)
    → PROTECTION (corrective action)
else if (aoa > aoa_high - 2.0°)
    → CAUTION (warning)
else
    → NORMAL (safe)
```

## Memory Layout

### Static Memory (~2KB)
```
sensor_data_t {
    circular_buffer_t[3]     = 3 * 5 * 4B = 60B
    float airspeed           = 4B
    uint32_t timestamp       = 4B
    SemaphoreHandle_t        = 4B
}

fsm_context_t                = ~32B
kalman_state_t               = 8B
estimator_state_t            = 12B
validator_result_t           = ~64B

UART buffers                 = 512B
Stack (per task)             = 2 * 4096B (8KB total)
```

### Dynamic Memory (~0KB)
- FreeRTOS handles all allocations at startup
- No malloc() in runtime loops

## Performance Analysis

### Control Loop Timing
```
20ms Period
├─ Validation:        0.5ms (median + outlier check)
├─ Estimation:        0.3ms (fusion + Kalman)
├─ FSM:               0.2ms (state machine)
├─ Logger:            0.5ms (UART write)
└─ Total:            ~1.5ms (7.5% utilization)

Slack: 18.5ms available for other tasks
```

### Latency Chain
```
UART RX        → HAL Input Buffer
    (0-20ms variable)
                ↓
Control Cycle  ← Timer fires every 20ms
                ↓
              Validate/Estimate/FSM
                ↓
LED/UART Out   (within same 20ms cycle)

Total Latency: 0-40ms (2 cycles worst case)
```

## Debugging Tips

### Enable Verbose Logging
In `main.c`:
```c
esp_log_level_set(TAG, ESP_LOG_DEBUG);
esp_log_level_set("VALIDATOR", ESP_LOG_DEBUG);
esp_log_level_set("ESTIMATOR", ESP_LOG_DEBUG);
```

### Monitor Task Stack Usage
```c
UBaseType_t stack_remaining = uxTaskGetStackHighWaterMark(control_task_handle);
ESP_LOGI(TAG, "Control task stack remaining: %u bytes", stack_remaining * 4);
```

### Validate Sensor Data Flow
1. Set breakpoint after circular_buffer_push()
2. Verify write_index increments
3. Check mutex lock/unlock balance

### Test Kalman Filter
Inject constant measurement stream:
```
Input: [12.0, 12.0, 12.0, ...] (constant)
Expected output: [12.0, 12.0, 12.0, ...]
Convergence: ~5-10 cycles
Variance should → Steady state
```

## Common Issues & Solutions

### Issue: LED doesn't blink
**Cause:** FSM state machine not transitioning to CAUTION/PROTECTION
**Debug:**
```
1. Verify AoA threshold configuration in fsm.c
2. Check calculated_aoa value in logs
3. Verify LED GPIO pin in config.h
```

### Issue: Sensor values jump/jitter
**Cause:** Kalman filter gain too high or too low
**Fix:**
```c
#define KALMAN_MEASUREMENT_NOISE 0.5f  /* Increase for smoothing */
#define KALMAN_PROCESS_NOISE 0.01f     /* Adjust process model */
```

### Issue: UART messages dropped
**Cause:** Input task priority too low
**Fix:**
```c
xTaskCreatePinnedToCore(hal_input_task, ..., 10, ...);  /* Higher priority */
```

### Issue: Median calculation gives wrong result
**Cause:** Buffer not initialized or write_index logic incorrect
**Debug:**
```c
ESP_LOGI(TAG, "Buffer values: %.1f, %.1f, %.1f",
    buf->sensor_values[0],
    buf->sensor_values[1],
    buf->sensor_values[2]);
```

## Testing Strategy

### Unit Tests (Manual)
1. **Circular Buffer**
   - Push 5 values, verify FIFO order
   - Verify write_index wraps correctly

2. **Median**
   - Test all 6 permutations of (a,b,c)
   - Test with duplicates: (12, 12, 15) → 12
   - Test with negatives: (-1, 0, 1) → 0

3. **Kalman Filter**
   - Input constant: output should converge
   - Input step: output should follow with lag
   - Verify variance decreases monotonically

4. **FSM**
   - Sweep AoA from -10 to 30 degrees
   - Verify state transitions at thresholds
   - Check LED blink rates

### System Integration Test
```bash
# Terminal 1: Monitor output
python3 tools/monitor.py --port /dev/ttyUSB0 --output log.csv

# Terminal 2: Send simulated data
python3 tools/send_sim_data.py --port /dev/ttyUSB0 --interval 50
```

Expected output:
```
IDX=0001 TS=0 AOA=12.43 STATUS=NORMAL
IDX=0002 TS=20 AOA=12.48 STATUS=NORMAL
IDX=0003 TS=40 AOA=12.45 STATUS=CAUTION   ← Threshold crossed
IDX=0004 TS=60 AOA=20.87 STATUS=PROTECTION
IDX=0005 TS=80 AOA=21.50 STATUS=OVERRIDE  ← Stall detected!
```

## Code Style & Conventions

### Naming
- Functions: `module_action()` (e.g., `validator_run()`)
- Variables: `noun_descriptor` (e.g., `sensor_value`, `median_aoa`)
- Constants: `UPPER_CASE` (e.g., `OUTLIER_THRESHOLD_DEG`)
- Types: `name_t` (e.g., `circular_buffer_t`)

### Formatting
- Indent: 4 spaces
- Line length: 100 characters (soft limit)
- Braces: K&R style

### Documentation
```c
/* ===== Section Header ===== */

/**
 * Function description.
 * 
 * @param param1 Description
 * @return Return value description
 */
void function_name(int param1) {
    ...
}
```

## Future Enhancements

### Phase 2: Sensor Diagnostics
- Detect sensor failures (stuck value, always increasing)
- Track sensor health metrics
- Implement sensor replacement logic

### Phase 3: Advanced Filtering
- Dual Kalman filter (AoA + airspeed)
- Extended Kalman Filter (EKF) for nonlinear dynamics
- Particle filter for multi-modal distributions

### Phase 4: Autopilot Integration
- CAN interface for control commands
- Implement elevator trimming logic
- Integrate with Flight Management System (FMS)

### Phase 5: Logging & Storage
- SD card support for black box recording
- Flash filesystem for event logging
- Data compression and archival

## References

- FreeRTOS Documentation: https://www.freertos.org/
- ESP-IDF Guide: https://docs.espressif.com/projects/esp-idf/
- Kalman Filter Theory: https://en.wikipedia.org/wiki/Kalman_filter
- Real-Time Systems: "Real-Time Systems" by Jane W.S. Liu

## Contact & Support

For questions or issues:
1. Check DEBUG logs: `idf.py monitor`
2. Verify thresholds match your aircraft specs
3. Test with the sample input in `components/aoa_controller/data/sim_input.csv` before real sensors
4. Review fsm.c thresholds_table for your config

---
*Last Updated: 2024*
*Firmware Version: 1.0*
