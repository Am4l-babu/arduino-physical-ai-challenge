/*
 * DOMORA ENV node — occupancy + comfort sensing (ESP32-C6)
 *
 * Role-driven (nodes/README.md): one firmware, not a fork per room. Which
 * sensors run comes from config.h's HAS_* flags, so this same binary works
 * whether all five parts have arrived or only some have.
 *
 * Mostly sensing, plus one actuator: the IR blaster (HAS_IR_BLASTER). That
 * makes this the only node that commands an appliance it cannot sense. A
 * valve reports its position and a pump relay has a CT clamp on it; an AC
 * driven by a captured IR code answers nothing at all, ever. So this
 * firmware publishes only what it TRANSMITTED (living_ac/ir_last_cmd) and
 * never claims to know the appliance's state — that is decided at the panel
 * by the hub (hub/twin/virtual_sensors.py ACRunning). Naming the point for
 * the transmission rather than the state is the whole discipline: it is the
 * difference between "we told it to" and "it did".
 *
 * It publishes onto the same topic contract sim/virtual_comfort.py and
 * sim/virtual_house.py already exercise against the hub (domora/env1/living/
 * radar, .../temp_c, domora/env1/living_ac/ir_last_cmd), so the closed loops
 * verified in simulation need nothing else to accept real data from this board.
 *
 * Requires (installed via Library Manager):
 *   PubSubClient, Adafruit BME280 Library (+ Adafruit Unified Sensor,
 *   Adafruit BusIO), Adafruit VEML7700 Library
 *
 * The IR path deliberately adds NO library. The 38 kHz carrier comes from
 * the ESP32's own LEDC peripheral and the frame is a captured mark/space
 * list, so there is no brand-protocol table to be wrong about and no
 * dependency to vendor at the venue.
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

void publish_point_str(const char *asset, const char *point, const char *value) {
  char topic[48];
  char payload[48];
  snprintf(topic, sizeof(topic), "domora/%s/%s/%s", NODE_ID, asset, point);
  snprintf(payload, sizeof(payload), "{\"value\": \"%s\"}", value);
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
#if HAS_IR_BLASTER
  // Re-subscribe on every (re)connect: MQTT subscriptions do not survive a
  // dropped session, and a node that silently stops hearing commands is
  // exactly the failure this project refuses to ship.
  mqtt.subscribe("domora/cmd/living_ac/+");
#endif
}

// --- IR blaster: replay a captured waveform, claim nothing about the result ---
//
// No protocol decoding, on purpose. Decoding needs a table of brands, and the
// point of this actuator is to drive an appliance no table covers: a captured
// mark/space list replays identically whether the original remote spoke NEC,
// Kaseikyo, or something proprietary nobody named. The carrier is the ESP32's
// own LEDC PWM, so no IR library is needed.
//
// One-way by construction: nothing comes back from an IR appliance, and this
// code makes no attempt to pretend otherwise.

#if HAS_IR_BLASTER
static const uint16_t IR_ON_TIMINGS[] = IR_AC_ON_TIMINGS;
static const uint16_t IR_OFF_TIMINGS[] = IR_AC_OFF_TIMINGS;

// delayMicroseconds() is only dependable for short waits; AC frames contain
// inter-frame gaps of tens of milliseconds, so split those into whole
// milliseconds plus a remainder.
void ir_wait_us(uint32_t us) {
  while (us >= 16000) {
    delay(16);
    us -= 16000;
  }
  if (us) delayMicroseconds(us);
}

void ir_send(const uint16_t *timings, size_t count) {
  // Even indices are marks (carrier on), odd are spaces — the order a
  // capture produces, since a frame always begins with a mark.
  for (size_t i = 0; i < count; i++) {
    ledcWrite(PIN_IR_LED, (i % 2 == 0) ? IR_DUTY_8BIT : 0);
    ir_wait_us(timings[i]);
  }
  ledcWrite(PIN_IR_LED, 0);   // never leave the LED driven
  esp_task_wdt_reset();       // a long frame is a long blocking stretch
}

void ir_send_command(const char *command) {
#if HAS_LD2410
  // Defense in depth, not duplication: hub/agents/safety.py already refuses
  // to plan an AC start in an empty house, but that check runs on the hub
  // and reads a fused point. This one runs on the board that owns the radar,
  // so a hub bug, a replayed command, or a stale twin cannot cool an empty
  // room. Same discipline as the tank node's hardwired leak reflex.
  if (strcmp(command, "on") == 0 && digitalRead(PIN_LD2410_OUT) == LOW) {
    Serial.println("IR: refusing 'on' — radar says the room is empty");
    return;
  }
#endif

  if (strcmp(command, "on") == 0) {
    ir_send(IR_ON_TIMINGS, sizeof(IR_ON_TIMINGS) / sizeof(IR_ON_TIMINGS[0]));
  } else if (strcmp(command, "off") == 0) {
    ir_send(IR_OFF_TIMINGS, sizeof(IR_OFF_TIMINGS) / sizeof(IR_OFF_TIMINGS[0]));
  } else {
    return;                   // unknown command: transmit nothing
  }

  // What we sent — NOT what the appliance did. The hub decides that from
  // the panel CT; if these ever disagree, the CT wins and the unit gets
  // flagged suspect.
  publish_point_str("living_ac", "ir_last_cmd", command);
}
#endif  // HAS_IR_BLASTER

// --- IR capture: the provisioning step ---
//
// Point the appliance's own remote at the TSOP and press the button you want
// DOMORA to learn; the timings print as a ready-to-paste C array. This is
// also where "cool, not heat" is actually enforced — hub/agents/safety.py's
// capability table admits `on`/`off` and has no way to check which mode a
// captured code selects, so the button pressed here is the real control.

#if HAS_IR_RECEIVER
void ir_capture_to_serial() {
  if (digitalRead(PIN_IR_RECV) != LOW) return;   // idle HIGH: nothing arriving

  static uint16_t buf[IR_CAPTURE_MAX];
  size_t n = 0;
  int level = LOW;              // a demodulated mark pulls the TSOP output LOW
  uint32_t last = micros();
  uint32_t quiet_since = last;

  while (n < IR_CAPTURE_MAX) {
    int now_level = digitalRead(PIN_IR_RECV);
    uint32_t now = micros();
    if (now_level != level) {
      uint32_t span = now - last;
      buf[n++] = (span > 65535) ? 65535 : (uint16_t)span;
      last = now;
      level = now_level;
      quiet_since = now;
    } else if (now - quiet_since > IR_CAPTURE_GAP_US) {
      break;                    // gap long enough to call the frame finished
    }
  }
  esp_task_wdt_reset();

  Serial.printf("\n// captured %u edges — paste into config.h\n", (unsigned)n);
  Serial.print("#define IR_AC_..._TIMINGS { ");
  for (size_t i = 0; i < n; i++) {
    Serial.printf("%u%s", buf[i], (i + 1 < n) ? ", " : "");
  }
  Serial.println(" }");
}
#endif  // HAS_IR_RECEIVER

// --- commands (only reached when this board carries an actuator) ---

#if HAS_IR_BLASTER
void on_command(char *topic, byte *payload, unsigned int length) {
  (void)payload;
  (void)length;
  if (strcmp(topic, "domora/cmd/living_ac/on") == 0) {
    ir_send_command("on");
  } else if (strcmp(topic, "domora/cmd/living_ac/off") == 0) {
    ir_send_command("off");
  }
}
#endif

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
#if HAS_IR_BLASTER
  // LEDC generates the carrier; attaching at 0 duty means the LED is dark
  // until a frame is actually sent.
  ledcAttach(PIN_IR_LED, IR_CARRIER_HZ, 8);
  ledcWrite(PIN_IR_LED, 0);
#endif
#if HAS_IR_RECEIVER
  pinMode(PIN_IR_RECV, INPUT);
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
#if HAS_IR_BLASTER
  mqtt.setCallback(on_command);
#endif

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

#if HAS_IR_RECEIVER
  // Provisioning aid, not a runtime feature: prints any frame it sees so a
  // real remote can be learned. Returns immediately when the line is idle.
  ir_capture_to_serial();
#endif
}
