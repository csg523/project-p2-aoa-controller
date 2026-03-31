#ifndef AOA_ESTIMATOR_H
#define AOA_ESTIMATOR_H

typedef struct {
    float estimate;
    float error_covariance;
    float process_noise;
    float measurement_noise;
} KalmanState_t;

void Kalman_Init(KalmanState_t *state);
float Kalman_Update(KalmanState_t *state, float measurement);

#endif
