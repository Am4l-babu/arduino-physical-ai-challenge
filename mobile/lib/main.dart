import 'package:flutter/material.dart';

import 'screens/connect.dart';
import 'theme/tokens.dart';

void main() {
  runApp(const DomoraMobileApp());
}

class DomoraMobileApp extends StatelessWidget {
  const DomoraMobileApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'DOMORA',
      debugShowCheckedModeBanner: false,
      theme: domoraDarkTheme(),
      darkTheme: domoraDarkTheme(),
      themeMode: ThemeMode.dark,
      home: const ConnectScreen(),
    );
  }
}
