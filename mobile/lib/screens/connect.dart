// The Connect screen — Studio is served BY the hub, so relative URLs just
// work; this app is a separate process (often a separate device) and has
// to be told where the hub is. Persists host:port via shared_preferences.
// See docs/APP_PLAN.md §9.
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../core/hub_client.dart';
import '../core/store.dart';
import '../theme/tokens.dart';
import 'app_shell.dart';

const _prefsKey = 'hub_url';

class ConnectScreen extends StatefulWidget {
  const ConnectScreen({super.key});

  @override
  State<ConnectScreen> createState() => _ConnectScreenState();
}

class _ConnectScreenState extends State<ConnectScreen> {
  final _controller = TextEditingController();
  bool _checking = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadSaved();
  }

  Future<void> _loadSaved() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString(_prefsKey);
    if (saved != null && mounted) {
      _controller.text = saved;
      _connect(saved); // auto-retry the last known hub
    }
  }

  Future<void> _connect([String? value]) async {
    final url = (value ?? _controller.text).trim();
    if (url.isEmpty) {
      setState(() => _error = 'Enter the hub\'s host:port.');
      return;
    }
    setState(() {
      _checking = true;
      _error = null;
    });

    final reachable = await http
        .get(Uri.http(url, '/health'))
        .timeout(const Duration(seconds: 4))
        .then((r) => r.statusCode == 200)
        .catchError((_) => false);

    if (!mounted) return;
    setState(() => _checking = false);

    if (!reachable) {
      setState(() => _error = 'Could not reach $url/health. Is the hub running (python -m hub.services.api)?');
      return;
    }

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefsKey, url);

    final store = DomoraStore();
    final client = HubClient(baseUrl: url, store: store);
    client.connect();

    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => AppShell(store: store, client: client)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Padding(
              padding: const EdgeInsets.all(DomoraSpace.s6),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text('DOMORA', style: TextStyle(fontSize: 32, fontWeight: FontWeight.w700, color: DomoraColors.ink)),
                  const SizedBox(height: 4),
                  const Text('Mobile', style: TextStyle(fontSize: 14, color: DomoraColors.inkFaint)),
                  const SizedBox(height: DomoraSpace.s8),
                  TextField(
                    controller: _controller,
                    style: const TextStyle(color: DomoraColors.ink),
                    decoration: const InputDecoration(
                      labelText: 'Hub address',
                      hintText: 'e.g. 192.168.1.5:8080',
                      border: OutlineInputBorder(),
                    ),
                    onSubmitted: (_) => _connect(),
                  ),
                  const SizedBox(height: DomoraSpace.s2),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton(
                      onPressed: () => setState(() => _controller.text = '10.0.2.2:8080'),
                      child: const Text('Use 10.0.2.2:8080 (Android emulator → host machine)'),
                    ),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: DomoraSpace.s2),
                    Text(_error!, style: const TextStyle(color: DomoraColors.stCrit, fontSize: 13)),
                  ],
                  const SizedBox(height: DomoraSpace.s4),
                  FilledButton(
                    onPressed: _checking ? null : () => _connect(),
                    child: _checking
                        ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Text('Connect'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
