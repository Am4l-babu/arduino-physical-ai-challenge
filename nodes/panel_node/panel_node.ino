/*
 * DOMORA PANEL node — whole-house electrical sensing (ESP32-C6, identity fp1)
 *
 * docs/BOM_ORDER.md's "FLOW/POWER — panel node": one ESP32-C6, 3x SCT-013-030
 * CT clamps, one PZEM-004T v3 as the reference-grade meter. This is the node
 * that feeds NILM (hub/agents/energy.py) for the whole house.
 *
 * SENSING ONLY — no relays, no actuator command subscription. That is a
 * deliberate difference from nodes/tank_node/, not an omission: spec §11.1
 * says panel work is "sensing-first, and any mains actuation goes through
 * certified contactors", and the two closed loops in the §25.6 MVP both act
 * on water, never on mains. This firmware therefore subscribes to nothing
 * and can only ever publish.
 *
 * Publishes onto the exact topic contract sim/virtual_loads.py already
 * exercises against the hub:
 *   domora/fp1/main_panel/power_w        <- the one point NILM consumes
 *   domora/fp1/main_panel/voltage_v      | PZEM only
 *   domora/fp1/main_panel/frequency_hz   |
 *   domora/fp1/main_panel/power_factor   |
 *   domora/fp1/main_panel/energy_kwh     |
 *   domora/fp1/panel.ct1/current_a       | one per wired clamp
 *   domora/fp1/panel.ct2/current_a       |
 *   domora/fp1/panel.ct3/current_a       |
 *   domora/fp1/panel/status              <- birth message / LWT
 *
 * WHERE power_w ACTUALLY COMES FROM — the one thing to understand here.
 * A CT clamp measures *current*, nothing else. Real power needs voltage and
 * power factor too, so a clamp alone cannot report watts without assuming
 * both. This firmware has two provenances for power_w and the choice is a
 * config switch, because they are not equally trustworthy:
 *
 *   POWER_FROM_PZEM = 1 — the PZEM sits on the whole-house feed and its
 *     power() reading IS real power, measured. No assumption. Use this
 *     whenever the PZEM is on the incomer; it is the honest path.
 *
 *   POWER_FROM_PZEM = 0 — power_w is DERIVED: (sum of aggregate CT currents)
 *     x voltage x ASSUMED_POWER_FACTOR. The voltage is the PZEM's live
 *     measurement if a PZEM is wired at all (real), otherwise NOMINAL_VOLTAGE_V
 *     (an assumption). The power factor is always an assumption. This is
 *     apparent power scaled by a guess: good enough for NILM's edge detection,
 *     which cares about step *changes*, but the absolute energy ledger will be
 *     wrong for motor loads (pump, fridge compressor, washing machine) whose
 *     true PF is well below the resistive ~1.0.
 *
 * A CT clamp is also UNSIGNED — it cannot tell import from export. A clamp on
 * a solar feed must therefore never be marked CTn_IN_AGGREGATE: adding
 * generation to consumption is simply wrong, and the clamp gives no sign bit
 * to correct it with. Same trap in reverse for sub-circuits: a clamp on the
 * incomer already contains the sub-circuits downstream of it, so marking both
 * in-aggregate double-counts the house. See config.h.example.
 *
 * NOT hardware-verified: written and compile-checked against the ESP32-C6
 * target but never flashed or run on a real board, and no CT clamp or PZEM
 * was in hand while writing this. Every calibration constant and pin
 * assignment is first-draft — see README.md for exactly what needs bench
 * confirmation, and note that this node's clamps go in a live consumer unit:
 * spec §11.1 requires an electrician and an RCD, not a hobbyist afternoon.
 */

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <esp_task_wdt.h>

#include "config.h"   // defines the HAS_* flags used below
#include "certs.h"

#define HAS_ANY_CT (HAS_CT1 || HAS_CT2 || HAS_CT3)

#if HAS_PZEM
#include <PZEM004Tv30.h>
#endif

static const uint32_t WDT_TIMEOUT_MS = 20000;

WiFiClientSecure secureClient;
PubSubClient mqtt(secureClient);

#if HAS_PZEM
PZEM004Tv30 pzem(Serial1, PIN_PZEM_RX, PIN_PZEM_TX);
#endif

char status_topic[48];
unsigned long last_sense = 0;
unsigned long last_mqtt_attempt = 0;

// ---------------------------------------------------------------------
// Publish helpers — topic domora/<node>/<asset>/<point>, payload {"value": v}
// Identical contract to nodes/tank_node and nodes/env_node.
// ---------------------------------------------------------------------

void publish_value(const char *asset, const char *point, float value) {
  char topic[48], payload[48];
  snprintf(topic, sizeof(topic), "domora/%s/%s/%s", NODE_ID, asset, point);
  snprintf(payload, sizeof(payload), "{\"value\": %.3f}", value);
  mqtt.publish(topic, payload);
}

// ---------------------------------------------------------------------
// CT clamp channels
//
// Table-driven rather than three copies of the same block, so adding or
// removing a clamp is a config edit. in_aggregate decides whether a channel
// counts toward the whole-house current used for the derived power_w — read
// the double-counting and solar-sign warnings in the file header before
// setting it.
// ---------------------------------------------------------------------

#if HAS_ANY_CT
struct CtChannel {
  const char *asset;
  uint8_t pin;
  float amps_per_count;
  bool in_aggregate;
};

static const CtChannel CT_CHANNELS[] = {
#if HAS_CT1
  {"panel.ct1", PIN_CT1_ADC, CT1_AMPS_PER_COUNT, CT1_IN_AGGREGATE},
#endif
#if HAS_CT2
  {"panel.ct2", PIN_CT2_ADC, CT2_AMPS_PER_COUNT, CT2_IN_AGGREGATE},
#endif
#if HAS_CT3
  {"panel.ct3", PIN_CT3_ADC, CT3_AMPS_PER_COUNT, CT3_IN_AGGREGATE},
#endif
};
static const size_t CT_COUNT = sizeof(CT_CHANNELS) / sizeof(CT_CHANNELS[0]);

// True-RMS over a whole number of mains cycles.
//
// The DC midpoint is MEASURED, not assumed to be half of full scale: the
// bias network that lifts the clamp's AC output into the ADC's range is two
// real resistors and never lands exactly on VCC/2, and any residual offset
// adds a constant inflation to every reading (RMS cannot tell an offset from
// signal). Single pass: variance = mean(x^2) - mean(x)^2 gives both the
// midpoint and the RMS about it without buffering samples.
//
// sum_sq needs 64 bits — a 12-bit sample squared is up to ~16.7M and the
// window holds thousands of them, which overflows uint32 well before the
// window closes.
//
// Takes the pin and scale directly rather than a CtChannel reference: the
// .ino preprocessor hoists generated prototypes above everything that is not
// an #include, so a sketch-defined type in a function signature is forward-
// referenced before it exists and fails to compile.
float read_ct_amps(uint8_t pin, float amps_per_count) {
  uint64_t sum = 0, sum_sq = 0;
  uint32_t n = 0;
  unsigned long start = millis();
  while (millis() - start < CT_SAMPLE_WINDOW_MS) {
    uint32_t raw = (uint32_t)analogRead(pin);
    sum += raw;
    sum_sq += (uint64_t)raw * raw;
    n++;
  }
  if (n == 0) return 0.0f;

  double mean = (double)sum / n;
  double mean_sq = (double)sum_sq / n;
  double variance = mean_sq - mean * mean;
  if (variance < 0.0) variance = 0.0;   // float noise near zero signal

  float amps = (float)sqrt(variance) * amps_per_count;

  // Below the noise floor the reading is the ADC's own hash, not a load.
  // Reporting it as current would give the house a phantom always-on
  // baseline and hand the NILM edge detector a stream of fake small steps.
  if (amps < CT_NOISE_FLOOR_A) return 0.0f;
  return amps;
}
#endif  // HAS_ANY_CT

// ---------------------------------------------------------------------
// Wi-Fi / MQTT — same pattern as nodes/tank_node.
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
  // No subscribe() here, unlike the tank node: this board has no actuator,
  // so it has no command topic to listen on.
  return mqtt.connect(NODE_ID, status_topic, /*willQos=*/1, /*willRetain=*/true, "offline");
}

void announce_online() {
  mqtt.publish(status_topic, "online", /*retained=*/true);
}

// ---------------------------------------------------------------------
// Sense + publish
// ---------------------------------------------------------------------

void sense_and_publish() {
  float aggregate_amps = 0.0f;
  bool have_aggregate = false;

#if HAS_ANY_CT
  for (size_t i = 0; i < CT_COUNT; i++) {
    float amps = read_ct_amps(CT_CHANNELS[i].pin, CT_CHANNELS[i].amps_per_count);
    publish_value(CT_CHANNELS[i].asset, "current_a", amps);
    if (CT_CHANNELS[i].in_aggregate) {
      aggregate_amps += amps;
      have_aggregate = true;
    }
    esp_task_wdt_reset();   // each channel holds the CPU for CT_SAMPLE_WINDOW_MS
  }
#endif

  float volts = NOMINAL_VOLTAGE_V;   // assumption unless a PZEM overrides it below

#if HAS_PZEM
  // Every PZEM getter returns NAN when the Modbus read fails. Publishing a
  // NaN would poison the twin and hand the NILM edge detector a value that
  // compares false against everything, so each one is guarded and simply
  // omitted when the meter does not answer. Silence is a signal in this
  // architecture (hub-side staleness detection); a fabricated number is not.
  float pzem_voltage = pzem.voltage();
  if (!isnan(pzem_voltage)) {
    publish_value("main_panel", "voltage_v", pzem_voltage);
    volts = pzem_voltage;   // real measurement beats NOMINAL_VOLTAGE_V
  }

  float pzem_frequency = pzem.frequency();
  if (!isnan(pzem_frequency)) publish_value("main_panel", "frequency_hz", pzem_frequency);

  float pzem_pf = pzem.pf();
  if (!isnan(pzem_pf)) publish_value("main_panel", "power_factor", pzem_pf);

  float pzem_energy = pzem.energy();   // library returns Wh
  if (!isnan(pzem_energy)) publish_value("main_panel", "energy_kwh", pzem_energy / 1000.0f);
#endif

#if HAS_PZEM && POWER_FROM_PZEM
  // The honest path: measured real power, no voltage or power-factor guess.
  float pzem_power = pzem.power();
  if (!isnan(pzem_power)) publish_value("main_panel", "power_w", pzem_power);
#else
  // The derived path: apparent power scaled by an assumed power factor. Good
  // enough for NILM's step detection, wrong in absolute terms for motor
  // loads — see the file header.
  if (have_aggregate) {
    publish_value("main_panel", "power_w", aggregate_amps * volts * ASSUMED_POWER_FACTOR);
  }
#endif
}

// ---------------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  snprintf(status_topic, sizeof(status_topic), "domora/%s/panel/status", NODE_ID);

  esp_task_wdt_config_t wdt_config = {
    .timeout_ms = WDT_TIMEOUT_MS,
    .idle_core_mask = 0,
    .trigger_panic = true,
  };
  esp_task_wdt_init(&wdt_config);
  esp_task_wdt_add(NULL);

#if HAS_ANY_CT
  for (size_t i = 0; i < CT_COUNT; i++) {
    pinMode(CT_CHANNELS[i].pin, INPUT);
  }
#endif

#if HAS_PZEM
  // The library's ESP32 constructor already knows the pins; this just fixes
  // the line settings the PZEM-004T v3 expects (9600 8N1, Modbus-RTU).
  Serial1.begin(PZEM_BAUD_RATE, SERIAL_8N1, PIN_PZEM_RX, PIN_PZEM_TX);
#endif

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
