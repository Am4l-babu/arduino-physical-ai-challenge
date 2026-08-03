// The hub client: WebSocket for live /ws frames + HTTP for /ai, /nilm,
// /graph, /history, /playback.json. Direct Dart port of studio/core/
// socket.js's reconnect behavior, plus the HTTP helpers studio/core/
// history.js, nilm.js, and screens/{ai,settings}.js implement separately
// in JS. baseUrl is "host:port" (no scheme) — since (unlike Studio) this app
// is a separate process from the hub, it has to be told where it lives.
//
// The app opens without one: baseUrl may start empty (nothing saved yet),
// and Settings is where it is entered or changed, well after launch, via
// reconnectTo(). See docs/APP_PLAN.md §9.
import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import 'store.dart';

class HubClient {
  static const _prefsKey = 'hub_url';

  String baseUrl;
  final DomoraStore store;
  final http.Client _httpClient;
  WebSocketChannel? _channel;
  Timer? _reconnectTimer;
  bool _disposed = false;

  // httpClient is injectable so tests can substitute http.testing.MockClient
  // fed with real captured response bodies, instead of a live network call.
  HubClient({required this.baseUrl, required this.store, http.Client? httpClient})
      : _httpClient = httpClient ?? http.Client();

  /// The last address saved from Settings (or the old Connect screen, on an
  /// upgrade), if any. Null on a first-ever launch.
  static Future<String?> loadSavedAddress() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_prefsKey);
  }

  static Future<void> saveAddress(String url) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefsKey, url);
  }

  Uri _http(String path, [Map<String, String>? query]) => Uri.http(baseUrl, path, query);
  Uri _ws() => Uri.parse('ws://$baseUrl/ws');

  void connect() {
    _disposed = false;
    if (baseUrl.trim().isEmpty) {
      // Nothing to dial. The app is already open regardless — reporting
      // "connecting" here would claim an attempt that isn't happening.
      store.setConnection('unconfigured');
      return;
    }
    _connectOnce();
  }

  /// Point at a different hub — called from Settings, well after the app
  /// has already opened, never as a launch-time gate. Drops any in-flight
  /// connection/retry first; stale points from a *different* house have no
  /// business surviving the switch (DomoraStore.reset()).
  void reconnectTo(String newBaseUrl) {
    _reconnectTimer?.cancel();
    _channel?.sink.close();
    baseUrl = newBaseUrl.trim();
    store.reset();
    connect();
  }

  Future<void> _connectOnce() async {
    if (_disposed) return;
    store.setConnection('connecting');
    final channel = WebSocketChannel.connect(_ws());
    _channel = channel;
    try {
      await channel.ready;
    } catch (_) {
      store.setConnection('down');
      _scheduleReconnect();
      return;
    }
    if (_disposed) return;
    store.setConnection('live');
    channel.stream.listen(
      _onMessage,
      onDone: _onDisconnect,
      onError: (_) => _onDisconnect(),
      cancelOnError: true,
    );
  }

  void _onMessage(dynamic data) {
    try {
      final msg = jsonDecode(data as String) as Map<String, dynamic>;
      switch (msg['type']) {
        case 'snapshot':
          store.applySnapshot(msg);
        case 'point':
          store.applyPoint(msg);
        case 'event':
          store.applyEvent(msg);
      }
    } catch (_) {
      // malformed frame — drop it, the next one will keep the stream healthy
    }
  }

  void _onDisconnect() {
    if (_disposed) return;
    store.setConnection('down');
    _scheduleReconnect();
  }

  void _scheduleReconnect() {
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(milliseconds: 1500), _connectOnce);
  }

  void dispose() {
    _disposed = true;
    _reconnectTimer?.cancel();
    _channel?.sink.close();
    _httpClient.close();
  }

  // --- HTTP: same endpoints Studio's core/{ai,nilm,history}.js call ---

  Future<Map<String, dynamic>> askAi(String message) async {
    final res = await _httpClient.post(
      _http('/ai'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'message': message}),
    );
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>?> fetchNilm() async {
    try {
      final res = await _httpClient.get(_http('/nilm'));
      if (res.statusCode != 200) return null;
      return jsonDecode(res.body) as Map<String, dynamic>;
    } catch (_) {
      return null;
    }
  }

  Future<Map<String, dynamic>?> fetchGraph() async {
    try {
      final res = await _httpClient.get(_http('/graph'));
      if (res.statusCode != 200) return null;
      return jsonDecode(res.body) as Map<String, dynamic>;
    } catch (_) {
      return null;
    }
  }

  Future<List<SeriesPoint>?> fetchHistory(String key, {int limit = 500}) async {
    try {
      final res = await _httpClient.get(_http('/history', {'key': key, 'limit': '$limit'}));
      if (res.statusCode != 200) return null;
      final body = jsonDecode(res.body) as Map<String, dynamic>;
      final pts = (body['points'] as List)
          .map((p) => SeriesPoint((p[0] as num).toInt(), (p[1] as num).toDouble()))
          .toList();
      return pts;
    } catch (_) {
      return null;
    }
  }

  Future<Map<String, dynamic>?> fetchPlayback() async {
    try {
      final res = await _httpClient.get(_http('/playback.json'));
      if (res.statusCode != 200) return null;
      return jsonDecode(res.body) as Map<String, dynamic>;
    } catch (_) {
      return null;
    }
  }

  /// Quick reachability check for the Connect screen.
  Future<bool> healthCheck() async {
    try {
      final res = await _httpClient.get(_http('/health')).timeout(const Duration(seconds: 3));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }
}
