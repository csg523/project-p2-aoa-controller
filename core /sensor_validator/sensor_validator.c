#include "sensor_validator.h"
#include <math.h>

// ---------- BUFFER ----------

void SensorBuffer_Init(SensorBuffer_t *buf) {
    buf->head = 0;
    for (int i = 0; i < BUFFER_SIZE; i++) {
        buf->buffer[i].valid = 0;
        buf->buffer[i].value = 0.0f;
    }
}

void SensorBuffer_Add(SensorBuffer_t *buf, float value, uint8_t valid) {
    buf->buffer[buf->head].value = value;
    buf->buffer[buf->head].valid = valid;
    buf->head = (buf->head + 1) % BUFFER_SIZE;
}

uint8_t SensorBuffer_GetLatestValid(SensorBuffer_t *buf, float *out) {

    int idx = buf->head;

    for (int i = 0; i < BUFFER_SIZE; i++) {
        idx = (idx - 1 + BUFFER_SIZE) % BUFFER_SIZE;

        if (buf->buffer[idx].valid) {
            *out = buf->buffer[idx].value;
            return 1;
        }
    }
    return 0;
}

// ---------- MEDIAN ----------

static void swap(float *a, float *b) {
    float t = *a; *a = *b; *b = t;
}

static float median3(float a, float b, float c) {
    if (a > b) swap(&a, &b);
    if (b > c) swap(&b, &c);
    if (a > b) swap(&a, &b);
    return b;
}

// ---------- MAIN PIPELINE ----------

void SensorValidator_Process(SensorBuffer_t buffers[],
                             SensorOutput_t *output)
{
    float values[NUM_SENSORS];
    
    // Step 1: Get latest valid values
    for (int i = 0; i < NUM_SENSORS; i++) {

        if (SensorBuffer_GetLatestValid(&buffers[i], &values[i])) {
            output->valid[i] = 1;
        } else {
            values[i] = 0.0f;
            output->valid[i] = 0;
        }
    }

    // Step 2: Median voting
    float median = median3(values[0], values[1], values[2]);

    // Step 3 + 4: Outlier detection + weighted fusion
    float numerator = 0.0f;
    float denominator = 0.0f;

    for (int i = 0; i < NUM_SENSORS; i++) {

        if (!output->valid[i]) {
            output->weights[i] = 0.0f;
            continue;
        }

        float error = fabsf(values[i] - median);

        // Outlier rejection
        if (error > OUTLIER_THRESHOLD) {
            output->weights[i] = 0.0f;
            continue;
        }

        // Weight based on confidence
        float weight = 1.0f / (1.0f + error);

        output->weights[i] = weight;
        numerator += values[i] * weight;
        denominator += weight;
    }

    // Final fused value
    if (denominator > 0.0f) {
        output->fused_value = numerator / denominator;
    } else {
        output->fused_value = 0.0f; // fallback
    }
}
