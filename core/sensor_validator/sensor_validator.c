#include "sensor_validator.h"
#include <stdlib.h>
#include <math.h>

static void buffer_insert(CircularBuffer *cb, float value) {
    cb->buffer[cb->index] = value;
    cb->index = (cb->index + 1) % BUFFER_SIZE;

    if (cb->count < BUFFER_SIZE)
        cb->count++;
}

static int compare(const void *a, const void *b) {
    return (*(float*)a - *(float*)b);
}

static float compute_median(CircularBuffer *cb) {
    float temp[BUFFER_SIZE];
    int n = cb->count;

    for (int i = 0; i < n; i++)
        temp[i] = cb->buffer[i];

    qsort(temp, n, sizeof(float), compare);

    if (n % 2 == 0)
        return (temp[n/2] + temp[n/2 - 1]) / 2.0;
    else
        return temp[n/2];
}

static int is_outlier(float value, float median) {
    return fabs(value - median) > OUTLIER_THRESHOLD;
}

void SensorValidator_init(SensorValidatorContext *ctx, pthread_mutex_t *mutex) {
    ctx->mutex = mutex;

    for (int i = 0; i < NUM_SENSORS; i++) {
        ctx->buffers[i].index = 0;
        ctx->buffers[i].count = 0;
    }
}

void SensorValidator_process(SensorValidatorContext *ctx,
                             RawSensorData *input,
                             ValidatedData *output) {

    pthread_mutex_lock(ctx->mutex);

    float inputs[NUM_SENSORS] = {input->s1, input->s2, input->s3};
    float medians[NUM_SENSORS];
    float valid_values[NUM_SENSORS];

    int valid_count = 0;

    // Update buffers
    for (int i = 0; i < NUM_SENSORS; i++) {
        buffer_insert(&ctx->buffers[i], inputs[i]);
        medians[i] = compute_median(&ctx->buffers[i]);
    }

    // Outlier rejection
    for (int i = 0; i < NUM_SENSORS; i++) {
        if (!is_outlier(inputs[i], medians[i])) {
            valid_values[valid_count++] = inputs[i];
        }
    }

    // Compute validated AoA
    float aoa = 0.0;

    if (valid_count > 0) {
        for (int i = 0; i < valid_count; i++)
            aoa += valid_values[i];

        aoa /= valid_count;
        output->fault_flag = 0;
    } else {
        // All sensors faulty
        aoa = medians[0];  // fallback
        output->fault_flag = 1;
    }

    // Confidence score
    output->confidence = (float)valid_count / NUM_SENSORS;
    output->aoa_validated = aoa;

    pthread_mutex_unlock(ctx->mutex);
}
