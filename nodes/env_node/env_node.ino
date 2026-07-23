/*
 * DOMORA ENV node — template (ESP32-C6)
 *
 * Role-driven: which sensors are stuffed and which topics are published
 * comes from node config, not from forking the firmware.
 *
 * Week-3 deliverable (PLAN.md). This skeleton compiles the structure of
 * the loop; sensor drivers land behind read_*() as parts arrive.
 */

#include <WiFi.h>
// #include <PubSubClient.h>   // MQTT — enable in week 2 bridge work

const char* NODE_ID = "env1";
const char* ROOM = "living";

const unsigned long SENSE_PERIOD_MS = 2000;
unsigned long last_sense = 0;

void setup() {
  Serial.begin(115200);
  // Watchdog: outputs to fail-safe on reset (spec §16.3)
  // TODO week 3: Wi-Fi + TLS + MQTT connect, birth message, LWT
  // TODO week 3: BME280 (I2C), LD2410 (UART), PIR + reed (GPIO), leak (ADC)
}

void publish_point(const char* asset, const char* point, float value) {
  // topic: domora/<node>/<asset>/<point>  payload: {"value": <v>}
  Serial.printf("domora/%s/%s/%s {\"value\": %.2f}\n", NODE_ID, asset, point, value);
}

void loop() {
  if (millis() - last_sense < SENSE_PERIOD_MS) return;
  last_sense = millis();

  // Local reflex FIRST, hub or no hub (spec §2.1): e.g. leak ADC over
  // threshold -> drive interlock GPIO + buzzer, then report.

  // publish_point(ROOM, "radar", read_radar());
  // publish_point(ROOM, "pir", read_pir());
  // publish_point(ROOM, "temp_c", read_bme_temp());
}
