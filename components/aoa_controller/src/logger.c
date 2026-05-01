#include "logger.h"
#include <stdio.h>
#include <string.h>
#include <driver/gpio.h>
#include <driver/uart.h>
#include <esp_log.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

static const char *TAG = "LOGGER";
static volatile uint32_t led_blink_period = 0;
static volatile bool led_target_on = false;
static TaskHandle_t led_task_handle = NULL;

static void led_task(void *arg) {
    (void)arg;
    uint32_t last_period = UINT32_MAX;
    bool last_on = false;
    bool led_state = false;
    for (;;) {
        uint32_t period = led_blink_period;
        bool target_on = led_target_on;

        if (period == 0) {
            if (period != last_period || target_on != last_on) {
                led_state = target_on;
                gpio_set_level(LED_GPIO_PIN, led_state ? 1 : 0);
            }
            last_period = 0;
            last_on = target_on;
            vTaskDelay(pdMS_TO_TICKS(50));
            continue;
        }

        if (period != last_period) {
            led_state = true;
            gpio_set_level(LED_GPIO_PIN, 1);
            last_period = period;
        } else {
            led_state = !led_state;
            gpio_set_level(LED_GPIO_PIN, led_state ? 1 : 0);
        }
        last_on = target_on;
        uint32_t half = period / 2;
        if (half < 50) {
            half = 50;
        }
        vTaskDelay(pdMS_TO_TICKS(half));
    }
}

void logger_init(void) {
    gpio_config_t io_conf = {
        .intr_type = GPIO_INTR_DISABLE,
        .mode = GPIO_MODE_OUTPUT,
        .pin_bit_mask = (1ULL << LED_GPIO_PIN),
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .pull_up_en = GPIO_PULLUP_DISABLE,
    };
    gpio_config(&io_conf);
    gpio_set_level(LED_GPIO_PIN, 0);
    if (!led_task_handle) {
        xTaskCreate(led_task, "led_task", 2048, NULL, 5, &led_task_handle);
    }
    ESP_LOGI(TAG, "Logger initialized");
}

void logger_control_led(bool led_on, uint32_t blink_period_ms) {
    led_target_on = led_on;
    led_blink_period = blink_period_ms;
}

void logger_write_entry(const log_entry_t *entry) {
    char log_line[256];
    snprintf(log_line, sizeof(log_line),
             "IDX=%lu TS=%lu MODE=%s S1=%.2f S2=%.2f S3=%.2f AIRSPEED=%.1f AOA=%.2f STATUS=%s\r\n",
             entry->cycle_index,
             entry->timestamp,
             entry->flight_mode,
             entry->sensor1,
             entry->sensor2,
             entry->sensor3,
             entry->airspeed,
             entry->calculated_aoa,
             entry->status);
    uart_write_bytes(UART_NUM_0, (const char *)log_line, strlen(log_line));
    ESP_LOGD(TAG, "Logged: %s", log_line);
}
