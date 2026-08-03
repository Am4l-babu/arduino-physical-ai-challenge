/*
 * DOMORA TANK node — main valve, line flow, tank level, pump current (ESP32-C6)
 *
 * One combined board for the whole water side (docs/BOM_ORDER.md's
 * "FLOW/POWER — tank node" line item: one ESP32-C6 for valve + flow + level
 * + pump CT + leak probes). This is a stated assumption, not a confirmed
 * physical layout — see nodes/README.md.
 *
 * Publishes onto the exact topic contract sim/virtual_house.py and
 * sim/virtual_pump.py already exercise against the hub:
 *   domora/fp2/tank.line/flow_lpm
 *   domora/fp2/water_tank/level_pct
 *   domora/fp2/main_valve/valve_state
 *   domora/fp2/pump/current_a
 *   domora/fp2/pump/pump_state
 * Subscribes: domora/cmd/main_valve/+, domora/cmd/pump/+ (safety enforcement
 * — what the AUTONOMOUS planner may command — lives entirely in
 * hub/agents/safety.py; this firmware obeys whatever arrives on its command
 * topics, matching the existing architecture where actuators are dumb and
 * the safety plane is the one place that reasons about authority).
 *
 * THE HARDWIRED REFLEX (spec: "Leak -> valve ... works with the hub dead,
 * over copper, not radio"): the leak probes are checked FIRST in every loop
 * iteration, before any MQTT/Wi-Fi work, and drive the valve closed directly
 * via GPIO if either probe reads wet for LEAK_TRIP_READS consecutive checks.
 * This is a *different, faster* mechanism than the hub's software water-
 * balance leak detection (which infers a leak from flow+occupancy over many
 * ticks) — it reacts to water physically touching a probe, not to an
 * indirect multi-sensor inference, and it works even if Wi-Fi never comes up.
 * Once tripped, the reflex LATCHES: clearing requires LEAK_CLEAR_READS
 * consecutive dry reads, and even then the valve is never auto-reopened —
 * reopening always requires a deliberate domora/cmd/main_valve/open command.
 * This firmware refuses that command locally while the latch is tripped,
 * independent of whatever the hub's own software invariants decide (defense
 * in depth: hub/agents/safety.py already blocks "open" while its own
 * virtual.water.leak_suspected is set, but that's a different signal on a
 * different timescale; the firmware's latch does not depend on it).
 *
 * Dry-run pump protection is deliberately NOT a hardwired reflex here: it
 * requires correlating pump current against tank-level slope over time
 * (hub/twin/virtual_sensors.py's PumpProtection), which is exactly the kind
 * of multi-sensor reasoning the hub's software is for, not a single-sensor
 * instant reflex. The spec only calls out leak->valve and gas->solenoid as
 * needing hardwired local reflexes.
 *
 * The valve's own state report below is open-loop (commanded state after a
 * timed drive, no limit-switch feedback wired) — this is fine, not a gap:
 * the hub's Verifier never trusts an actuator's self-report anyway; it
 * verifies main_valve closures against the independent flow sensor
 * (tank.line/flow_lpm falling below threshold), which lives on this same
 * board but is a electrically independent measurement from the valve driver.
 *
 * NOT hardware-verified: written and compile-checked against the ESP32-C6
 * target but never flashed or run on a real board, and no valve/CT/level
 * hardware was in hand while writing this. Treat pin numbers, calibration
 * constants, and timing as first-draft until bench-tested — see README.md
 * for exactly what still needs confirming.
 */

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <esp_task_wdt.h>

#include "config.h"   // defines the HAS_* flags used below
#include "certs.h"

static const uint32_t WDT_TIMEOUT_MS = 20000;

WiFiClientSecure secureClient;
PubSubClient mqtt(secureClient);

char status_topic[48];
unsigned long last_sense = 0;
unsigned long last_mqtt_attempt = 0;

// ---------------------------------------------------------------------
// Publish helpers — topic domora/<node>/<asset>/<point>, payload {"value": v}
// ---------------------------------------------------------------------

void publish_value(const char *asset, const char *point, float value) {
  char topic[48], payload[48];
  snprintf(topic, sizeof(topic), "domora/%s/%s/%s", NODE_ID, asset, point);
  snprintf(payload, sizeof(payload), "{\"value\": %.3f}", value);
  mqtt.publish(topic, payload);
}

void publish_enum(const char *asset, const char *point, const char *value) {
  char topic[48], payload[48];
  snprintf(topic, sizeof(topic), "domora/%s/%s/%s", NODE_ID, asset, point);
  snprintf(payload, sizeof(payload), "{\"value\": \"%s\"}", value);
  mqtt.publish(topic, payload);
}

// ---------------------------------------------------------------------
// Relay driver (shared by valve + pump): honors RELAY_ACTIVE_LOW polarity.
// ---------------------------------------------------------------------

void relay_write(int pin, bool energize) {
  bool level_high = RELAY_ACTIVE_LOW ? !energize : energize;
  digitalWrite(pin, level_high ? HIGH : LOW);
}

// ---------------------------------------------------------------------
// The hardwired leak reflex — checked first, every loop, no MQTT dependency.
// ---------------------------------------------------------------------

#if HAS_LEAK_PROBES
int leak_trip_count = 0;
int leak_clear_count = 0;
bool leak_latched = false;

bool leak_probe_wet() {
  return digitalRead(PIN_LEAK_PROBE_1) == HIGH || digitalRead(PIN_LEAK_PROBE_2) == HIGH;
}
#endif

#if HAS_VALVE
enum ValveTarget { VALVE_NONE, VALVE_OPENING, VALVE_CLOSING };
ValveTarget valve_driving = VALVE_NONE;
unsigned long valve_drive_start_ms = 0;
const char *valve_reported_state = "unknown";   // open-loop, commanded state

void valve_stop_drive() {
  relay_write(PIN_VALVE_OPEN, false);
  relay_write(PIN_VALVE_CLOSE, false);
  valve_driving = VALVE_NONE;
}

void valve_start_close() {
  relay_write(PIN_VALVE_OPEN, false);
  relay_write(PIN_VALVE_CLOSE, true);
  valve_driving = VALVE_CLOSING;
  valve_drive_start_ms = millis();
}

void valve_start_open() {
  relay_write(PIN_VALVE_CLOSE, false);
  relay_write(PIN_VALVE_OPEN, true);
  valve_driving = VALVE_OPENING;
  valve_drive_start_ms = millis();
}

// Called every loop, unconditionally: stops a timed drive after
// VALVE_DRIVE_MAX_MS regardless of MQTT/Wi-Fi state, and updates the
// open-loop state report.
void valve_service_drive() {
  if (valve_driving == VALVE_NONE) return;
  if (millis() - valve_drive_start_ms >= VALVE_DRIVE_MAX_MS) {
    bool was_closing = (valve_driving == VALVE_CLOSING);
    valve_stop_drive();
    valve_reported_state = was_closing ? "closed" : "open";
  }
}
#endif

#if HAS_LEAK_PROBES
// The reflex itself. Runs before anything network-related; must not call
// into MQTT. Latches on trip; never auto-clears the valve back open.
void service_leak_reflex() {
  bool wet = leak_probe_wet();
  if (wet) {
    leak_trip_count++;
    leak_clear_count = 0;
  } else {
    leak_clear_count++;
    leak_trip_count = 0;
  }

  if (!leak_latched && leak_trip_count >= LEAK_TRIP_READS) {
    leak_latched = true;
#if HAS_VALVE
    valve_start_close();
#endif
  } else if (leak_latched && leak_clear_count >= LEAK_CLEAR_READS) {
    leak_latched = false;   // clears the latch; valve stays closed regardless
  }
}
#endif

// ---------------------------------------------------------------------
// Flow sensor (YF-S201): pulse counting via interrupt, converted to L/min
// on each sense period using the datasheet's fixed Hz-per-L/min constant.
// ---------------------------------------------------------------------

#if HAS_FLOW
volatile uint32_t flow_pulse_count = 0;

void IRAM_ATTR on_flow_pulse() {
  flow_pulse_count++;
}

float read_flow_lpm_and_reset(uint32_t elapsed_ms) {
  noInterrupts();
  uint32_t pulses = flow_pulse_count;
  flow_pulse_count = 0;
  interrupts();
  if (elapsed_ms == 0) return 0.0f;
  float hz = pulses * 1000.0f / elapsed_ms;
  return hz / FLOW_HZ_PER_LPM;
}
#endif

// ---------------------------------------------------------------------
// Tank level (AJ-SR04M in trigger/echo mode, HC-SR04-compatible timing).
// ---------------------------------------------------------------------

#if HAS_LEVEL
float read_level_pct() {
  digitalWrite(PIN_LEVEL_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_LEVEL_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_LEVEL_TRIG, LOW);

  unsigned long echo_us = pulseIn(PIN_LEVEL_ECHO, HIGH, 30000UL);  // 30ms timeout
  if (echo_us == 0) return NAN;   // no echo — sensor fault or out of range

  float distance_cm = echo_us / 58.0f;   // standard speed-of-sound constant
  float pct = (LEVEL_EMPTY_CM - distance_cm) / (LEVEL_EMPTY_CM - LEVEL_FULL_CM) * 100.0f;
  if (pct < 0.0f) pct = 0.0f;
  if (pct > 100.0f) pct = 100.0f;
  return pct;
}
#endif

// ---------------------------------------------------------------------
// Pump CT clamp: true-RMS current over a whole number of mains cycles.
//
// The DC midpoint is MEASURED, not assumed to be half of full scale. The
// bias network that lifts the clamp's AC output into the ADC's range is two
// real resistors and never lands exactly on VCC/2, and RMS cannot tell an
// offset from signal — so a fixed 2048 turns any bias error into phantom
// current. That matters here more than anywhere: pump_state below trips at
// 0.2 A, so with PUMP_CT_AMPS_PER_COUNT at 0.01 a bias only ~20 counts off
// centre reports a pump that is always running. hub/twin/virtual_sensors.py's
// PumpProtection reads exactly that signal, so the consequence is a dry-run
// cut on a pump that was never on, or a real dry-run masked by a reading that
// never changes.
//
// Single pass: variance = mean(x^2) - mean(x)^2 yields both the midpoint and
// the RMS about it without buffering samples. sum_sq needs 64 bits — a 12-bit
// sample squared reaches ~16.7M and the window holds thousands of them, which
// overflows a 32-bit accumulator well before the window closes.
//
// The window is time-bounded rather than a fixed sample count: how many
// analogRead() calls fit in one mains cycle is a property of the board and
// the ADC configuration, not something to hardcode, and sampling a partial
// cycle makes the RMS wobble with wherever in the waveform the window opened.
//
// Same routine as nodes/panel_node/panel_node.ino's read_ct_amps() — the two
// nodes measure current the same way because it is the same problem.
// ---------------------------------------------------------------------

#if HAS_PUMP_CT
float read_pump_current_a() {
  uint64_t sum = 0, sum_sq = 0;
  uint32_t n = 0;
  unsigned long start = millis();
  while (millis() - start < PUMP_CT_SAMPLE_WINDOW_MS) {
    uint32_t raw = (uint32_t)analogRead(PIN_PUMP_CT_ADC);
    sum += raw;
    sum_sq += (uint64_t)raw * raw;
    n++;
  }
  if (n == 0) return 0.0f;

  double mean = (double)sum / n;
  double variance = (double)sum_sq / n - mean * mean;
  if (variance < 0.0) variance = 0.0;   // float noise near zero signal

  return (float)sqrt(variance) * PUMP_CT_AMPS_PER_COUNT;
}
#endif

// ---------------------------------------------------------------------
// MQTT command handling
// ---------------------------------------------------------------------

void on_mqtt_message(char *topic, byte *payload, unsigned int length) {
  String t(topic);
#if HAS_VALVE
  if (t == "domora/cmd/main_valve/close") {
    valve_start_close();
  } else if (t == "domora/cmd/main_valve/open") {
#if HAS_LEAK_PROBES
    if (leak_latched) {
      // Refuse locally: the reflex latch outranks any command, including
      // ones the hub's own safety.py already should have vetoed — this is
      // the firmware's independent enforcement of the same rule.
      return;
    }
#endif
    valve_start_open();
  }
#endif
#if HAS_PUMP_RELAY
  if (t == "domora/cmd/pump/off") {
    relay_write(PIN_PUMP_RELAY, false);
  } else if (t == "domora/cmd/pump/on") {
    relay_write(PIN_PUMP_RELAY, true);
  }
#endif
}

// ---------------------------------------------------------------------
// Wi-Fi / MQTT
// ---------------------------------------------------------------------

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

bool connect_mqtt() {
  if (mqtt.connected()) return true;
  if (!connect_wifi()) return false;
  bool ok = mqtt.connect(NODE_ID, status_topic, /*willQos=*/1, /*willRetain=*/true, "offline");
  if (ok) {
    mqtt.subscribe("domora/cmd/main_valve/+");
    mqtt.subscribe("domora/cmd/pump/+");
  }
  return ok;
}

void announce_online() {
  mqtt.publish(status_topic, "online", /*retained=*/true);
}

// ---------------------------------------------------------------------
// Sense + publish
// ---------------------------------------------------------------------

void sense_and_publish(uint32_t elapsed_ms) {
#if HAS_FLOW
  publish_value("tank.line", "flow_lpm", read_flow_lpm_and_reset(elapsed_ms));
#endif
#if HAS_LEVEL
  float level = read_level_pct();
  if (!isnan(level)) publish_value("water_tank", "level_pct", level);
#endif
#if HAS_VALVE
  publish_enum("main_valve", "valve_state", valve_reported_state);
#endif
#if HAS_PUMP_CT
  float current = read_pump_current_a();
  publish_value("pump", "current_a", current);
  publish_enum("pump", "pump_state", current > PUMP_ON_THRESHOLD_A ? "on" : "off");
#endif
}

// ---------------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  snprintf(status_topic, sizeof(status_topic), "domora/%s/tank/status", NODE_ID);

  esp_task_wdt_config_t wdt_config = {
    .timeout_ms = WDT_TIMEOUT_MS,
    .idle_core_mask = 0,
    .trigger_panic = true,
  };
  esp_task_wdt_init(&wdt_config);
  esp_task_wdt_add(NULL);

#if HAS_FLOW
  pinMode(PIN_FLOW_PULSE, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_FLOW_PULSE), on_flow_pulse, FALLING);
#endif
#if HAS_LEVEL
  pinMode(PIN_LEVEL_TRIG, OUTPUT);
  pinMode(PIN_LEVEL_ECHO, INPUT);
#endif
#if HAS_VALVE
  pinMode(PIN_VALVE_OPEN, OUTPUT);
  pinMode(PIN_VALVE_CLOSE, OUTPUT);
  valve_stop_drive();   // both relays de-energized at boot — fail-safe: no
                         // uncommanded motion until a real command arrives
#endif
#if HAS_PUMP_CT
  pinMode(PIN_PUMP_CT_ADC, INPUT);
#endif
#if HAS_PUMP_RELAY
  pinMode(PIN_PUMP_RELAY, OUTPUT);
  // De-energized at boot, same "no uncommanded motion" rule as the valve.
  // NOT "leave it running": a watchdog reset that happens to land exactly
  // when a dry-run cutoff was in effect must not silently re-energize the
  // pump on reboot and undo the safety action. Resuming pump operation
  // after any reset is a deliberate domora/cmd/pump/on, never a boot default.
  relay_write(PIN_PUMP_RELAY, false);
#endif
#if HAS_LEAK_PROBES
  pinMode(PIN_LEAK_PROBE_1, INPUT_PULLDOWN);
  pinMode(PIN_LEAK_PROBE_2, INPUT_PULLDOWN);
#endif

  secureClient.setCACert(CA_CERT);
  secureClient.setCertificate(CLIENT_CERT);
  secureClient.setPrivateKey(CLIENT_KEY);
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(on_mqtt_message);

  connect_wifi();
}

void loop() {
#if HAS_LEAK_PROBES
  service_leak_reflex();   // FIRST, always — no MQTT dependency above this line
#endif
  esp_task_wdt_reset();
#if HAS_VALVE
  valve_service_drive();   // also unconditional: the drive timeout must fire
                           // even if MQTT/Wi-Fi is down
#endif

  if (!mqtt.connected()) {
    if (millis() - last_mqtt_attempt >= MQTT_RETRY_MS) {
      last_mqtt_attempt = millis();
      if (connect_mqtt()) announce_online();
    }
  } else {
    mqtt.loop();
  }

  if (mqtt.connected() && millis() - last_sense >= SENSE_PERIOD_MS) {
    uint32_t elapsed = millis() - last_sense;
    last_sense = millis();
    sense_and_publish(elapsed);
  }
}
