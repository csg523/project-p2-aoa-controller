#ifndef SENSOR_VALIDATOR_H
#define SENSOR_VALIDATOR_H

#include <stdint.h>

#define NUM_SENSORS 3
#define OUTLIER_THRESHOLD 5.0f   // configurable based on system

typedef struct {
    float value[NUM_SENSORS];
} SensorInput_t;

typedef struct {
    float validated_values[NUM_SENSORS];
    float weights[NUM_SENSORS];
} SensorOutput_t;

void SensorValidator_Process(SensorInput_t *input, SensorOutput_t *output);

#endif
