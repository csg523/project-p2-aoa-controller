#ifndef SENSOR_VALIDATOR_H
#define SENSOR_VALIDATOR_H

#include <stdint.h>

#define NUM_SENSORS 3
#define BUFFER_SIZE 5
#define OUTLIER_THRESHOLD 5.0f

typedef struct {
    float value;
    uint8_t valid;
} SensorSample_t;

typedef struct {
    SensorSample_t buffer[BUFFER_SIZE];
    uint8_t head;
} SensorBuffer_t;

typedef struct {
    float fused_value;
    float weights[NUM_SENSORS];
    uint8_t valid[NUM_SENSORS];
} SensorOutput_t;

// APIs
void SensorBuffer_Init(SensorBuffer_t *buf);
void SensorBuffer_Add(SensorBuffer_t *buf, float value, uint8_t valid);
uint8_t SensorBuffer_GetLatestValid(SensorBuffer_t *buf, float *out);

void SensorValidator_Process(SensorBuffer_t buffers[],
                             SensorOutput_t *output);

#endif
