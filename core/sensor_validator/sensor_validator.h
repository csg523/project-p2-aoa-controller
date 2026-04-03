#ifndef SENSOR_VALIDATOR_H
#define SENSOR_VALIDATOR_H

#include <stdint.h>
#include <pthread.h>

#define BUFFER_SIZE 5
#define NUM_SENSORS 3
#define OUTLIER_THRESHOLD 5.0   // in degrees

typedef struct {
    float buffer[BUFFER_SIZE];
    int index;
    int count;
} CircularBuffer;

typedef struct {
    float s1, s2, s3;
    uint32_t ts;
    uint8_t valid;
} RawSensorData;

typedef struct {
    float aoa_validated;
    float confidence;
    uint8_t fault_flag;
} ValidatedData;

typedef struct {
    CircularBuffer buffers[NUM_SENSORS];
    pthread_mutex_t *mutex;
} SensorValidatorContext;

void SensorValidator_init(SensorValidatorContext *ctx, pthread_mutex_t *mutex);

void SensorValidator_process(SensorValidatorContext *ctx,
                             RawSensorData *input,
                             ValidatedData *output);

#endif
