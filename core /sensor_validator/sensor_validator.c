#include "sensor_validator.h"

// Initialize buffer
void SensorBuffer_Init(SensorBuffer_t *buf) {
    buf->head = 0;
    for (int i = 0; i < BUFFER_SIZE; i++) {
        buf->buffer[i].valid = 0;
        buf->buffer[i].value = 0.0f;
    }
}

// Add new sample (circular buffer)
void SensorBuffer_Add(SensorBuffer_t *buf, float value, uint8_t valid) {
    buf->buffer[buf->head].value = value;
    buf->buffer[buf->head].valid = valid;

    buf->head = (buf->head + 1) % BUFFER_SIZE;
}

// Get latest valid value (fallback logic)
uint8_t SensorBuffer_GetLatestValid(SensorBuffer_t *buf, float *out) {

    int idx = buf->head;

    // Traverse last 5 values (reverse order)
    for (int i = 0; i < BUFFER_SIZE; i++) {

        idx = (idx - 1 + BUFFER_SIZE) % BUFFER_SIZE;

        if (buf->buffer[idx].valid) {
            *out = buf->buffer[idx].value;
            return 1;  // found valid
        }
    }

    return 0; // all values invalid
}

// Main validation
void SensorValidator_Process(SensorBuffer_t buffers[],
                             SensorValidated_t *output)
{
    for (int i = 0; i < NUM_SENSORS; i++) {

        float value = 0.0f;

        if (SensorBuffer_GetLatestValid(&buffers[i], &value)) {
            output->value[i] = value;
            output->valid[i] = 1;
        } else {
            output->value[i] = 0.0f;
            output->valid[i] = 0;  // sensor invalid
        }
    }
}
