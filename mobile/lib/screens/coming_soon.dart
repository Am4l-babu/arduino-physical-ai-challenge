import 'package:flutter/material.dart';
import '../theme/tokens.dart';

/// Honest placeholder for a screen not built yet — same principle as
/// Studio's disabled "· soon" nav chips before a phase landed.
class ComingSoonScreen extends StatelessWidget {
  final String title;
  final String note;
  const ComingSoonScreen({super.key, required this.title, required this.note});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(DomoraSpace.s6),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(title, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: DomoraColors.ink)),
            const SizedBox(height: DomoraSpace.s2),
            Text(note, textAlign: TextAlign.center, style: const TextStyle(color: DomoraColors.inkFaint, fontStyle: FontStyle.italic)),
          ],
        ),
      ),
    );
  }
}
