/*
 * DOMORA ENV node — occupancy + comfort sensing (ESP32-C6)
 *
 * Role-driven (nodes/README.md): one firmware, not a fork per room. Which
 * sensors run comes from config.h's HAS_* flags, so this same binary works
 * whether all five parts have arrived or only some have.
 *
 * This node is sensor-only — no actuators, no commands to obey — so unlike
 * the FLOW/POWER node it needs no hardwired reflex and never subscribes to
 * domora/cmd/#. It publishes onto the same topic contract sim/virtual_house.py
 * already exercises against the hub (domora/env1/living/radar, .../pir), so
 * the closed loops verified in simulation need nothing else to accept real
 * data from this board.
 *
 * Requires (installed via Library Manager):
 *   PubSubClient, Adafruit BME280 Library (+ Adafruit Unified Sensor,
 *   Adafruit BusIO), Adafruit VEML7700 Library
 *
 * Requires local files (gitignored, see the .example templates):
 *   config.h   Wi-Fi + MQTT + node identity + which sensors are stuffed
 *   certs.h    this node's mTLS identity from tools/gen_certs.py
 *
 * NOT hardware-verified: written and compile-checked against the ESP32-C6
 * target (arduino-cli, esp32 core 3.3.9) but never flashed or run on a real
 * board — the parts were ordered same-day this file was written. Treat
 * pin numbers, sensor init, and timing as first-draft until bench-tested.
 */

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <esp_task_wdt.h>

#include "config.h"   // defines the HAS_* flags the next block depends on

#if HAS_BME280
#include <Adafruit_BME280.h>
#endif
#if HAS_VEML7700
#include <Adafruit_VEML7700.h>
#endif

#include "certs.h"

// --- watchdog: if the loop ever hangs (e.g. a wedged Wi-Fi/TLS call), the
// board reboots rather than silently going dark. A stale twin point is a
// visible signal (TwinState.is_stale); a wedged node with no watchdog is not. ---
static const uint32_t WDT_TIMEOUT_MS = 20000;

WiFiClientSecure secureClient;
PubSubClient mqtt(secureClient);

#if HAS_BME280
Adafruit_BME280 bme;
bool bme_ok = false;
#endif
#if HAS_VEML7700
Adafruit_VEML7700 veml;
bool veml_ok = false;
#endif

char status_topic[48];
unsigned long last_sense = 0;
unsigned long last_mqtt_attempt = 0;

// --- publish: topic domora/<node>/<asset>/<point>, payload {"value": v} ---
// Matches the exact contract hub/agents/observer.py parses and
// sim/virtual_house.py already emits — the hub cannot tell this board apart
// from the simulator.

void publish_point(const char *asset, const char *point, float value) {
  char topic[48];
  char payload[48];
  snprintf(topic, sizeof(topic), "domora/%s/%s/%s", NODE_ID, asset, point);
  snprintf(payload, sizeof(payload), "{\"value\": %.2f}", value);
  mqtt.publish(topic, payload);
}

void publish_point_int(const char *asset, const char *point, int value) {
  char topic[48];
  char payload[32];
  snprintf(topic, sizeof(topic), "domora/%s/%s/%s", NODE_ID, asset, point);
  snprintf(payload, sizeof(payload), "{\"value\": %d}", value);
  mqtt.publish(topic, payload);
}

// --- Wi-Fi ---

bool connect_wifi() {
  if (WiFi.status() == WL_CONNECTED) return true;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_TIMEOUT_MS) {
    delay(250);
    esp_task_wdt_reset();
  }
  return WiFi.status() == WL_CONNECTED;
}

// --- MQTT (mTLS: broker ACL keys off the client cert's CN, not the
// client_id — see tools/gen_certs.py) ---

bool connect_mqtt() {
  if (mqtt.connected()) return true;
  if (!connect_wifi()) return false;

  return mqtt.connect(NODE_ID, status_topic, /*willQos=*/1, /*willRetain=*/true,
                       "offline");
}

void announce_online() {
  mqtt.publish(status_topic, "online", /*retained=*/true);
}

// --- sensor init (best-effort: a sensor that fails init is simply never
// published, not faked — silence is the honest signal, per hub/twin/state.py) ---

void init_sensors() {
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);

#if HAS_BME280
  bme_ok = bme.begin(0x76) || bme.begin(0x77);
#endif
#if HAS_VEML7700
  veml_ok = veml.begin();
#endif
#if HAS_LD2410
  pinMode(PIN_LD2410_OUT, INPUT);
  // LD2410C ships in UART report mode; its digital OT1 presence pin needs a
  // one-time configuration pass (vendor config tool / Ai-Thinker app) before
  // this firmware can just digitalRead() it. Not done here — bench setup step.
#endif
#if HAS_PIR
  pinMode(PIN_PIR, INPUT);
#endif
#if HAS_REED
  pinMode(PIN_REED, INPUT_PULLUP);   // closed = LOW when the magnet is present
#endif
}

// --- one sense+publish pass ---

void sense_and_publish() {
#if HAS_LD2410
  publish_point_int(ROOM, "radar", digitalRead(PIN_LD2410_OUT) ? 1 : 0);
#endif
#if HAS_PIR
  publish_point_int(ROOM, "pir", digitalRead(PIN_PIR) ? 1 : 0);
#endif
#if HAS_REED
  // INPUT_PULLUP: LOW = contact closed (door shut). Report door OPEN as 1,
  // matching the sense of every other boolean point ("1 = notable state").
  publish_point_int(ROOM, "door", digitalRead(PIN_REED) == LOW ? 0 : 1);
#endif
#if HAS_BME280
  if (bme_ok) {
    publish_point(ROOM, "temp_c", bme.readTemperature());
    publish_point(ROOM, "humidity_pct", bme.readHumidity());
    publish_point(ROOM, "pressure_hpa", bme.readPressure() / 100.0f);
  }
#endif
#if HAS_VEML7700
  if (veml_ok) {
    publish_point(ROOM, "lux", veml.readLux());
  }
#endif
}

void setup() {
  Serial.begin(115200);
  snprintf(status_topic, sizeof(status_topic), "domora/%s/%s/status", NODE_ID, ROOM);

  esp_task_wdt_config_t wdt_config = {
    .timeout_ms = WDT_TIMEOUT_MS,
    .idle_core_mask = 0,
    .trigger_panic = true,
  };
  esp_task_wdt_init(&wdt_config);
  esp_task_wdt_add(NULL);

  init_sensors();

  secureClient.setCACert(CA_CERT);
  secureClient.setCertificate(CLIENT_CERT);
  secureClient.setPrivateKey(CLIENT_KEY);
  mqtt.setServer(MQTT_HOST, MQTT_PORT);

  connect_wifi();
}

void loop() {
  esp_task_wdt_reset();

  if (!mqtt.connected()) {
    if (millis() - last_mqtt_attempt >= MQTT_RETRY_MS) {
      last_mqtt_attempt = millis();
      if (connect_mqtt()) announce_online();
    }
  } else {
    mqtt.loop();
  }

  if (mqtt.connected() && millis() - last_sense >= SENSE_PERIOD_MS) {
    last_sense = millis();
    sense_and_publish();
  }
}
