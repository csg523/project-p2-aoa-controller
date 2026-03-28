#include "sensor_validator.h"
#include <math.h>

static void swap(float *a, float *b) {
    float temp = *a;
    *a = *b;
    *b = temp;
}

static float median3(float a, float b, float c) {
    if (a > b) swap(&a, &b);
    if (b > c) swap(&b, &c);
    if (a > b) swap(&a, &b);
    return b;
}

void SensorValidator_Process(SensorInput_t *input, SensorOutput_t *output) {
    float a = input->value[0];
    float b = input->value[1];
    float c = input->value[2];

    float median = median3(a, b, c);

    float values[NUM_SENSORS] = {a, b, c};

    for (int i = 0; i < NUM_SENSORS; i++) {
        float error = fabsf(values[i] - median);

        if (error > OUTLIER_THRESHOLD) {
            // Outlier detected
            output->weights[i] = 0.0f;
        } else {
            // Weight inversely proportional to error
            output->weights[i] = 1.0f / (1.0f + error);
        }

        output->validated_values[i] = values[i];
    }
}
