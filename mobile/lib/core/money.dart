/// Money handling.
///
/// The API sends money as a JSON **string** — `"80.00"` — deliberately, so it
/// can be parsed exactly. `double.parse` compiles and is wrong: 0.1 + 0.2 is
/// not 0.3 in binary floating point, and these values are summed into a
/// `NUMERIC(10,2)` column that money is owed against.
library;

import 'package:decimal/decimal.dart';

/// Parses an API money string. Throws [FormatException] on anything unparseable
/// rather than silently yielding zero — a price that reads as free is worse than
/// an error.
Decimal parseMoney(String raw) => Decimal.parse(raw);

/// Tolerant parse for optional fields. Returns null rather than throwing.
Decimal? tryParseMoney(Object? raw) => switch (raw) {
  final String s => Decimal.tryParse(s),
  final int i => Decimal.fromInt(i),
  _ => null,
};

/// Formats as Indian rupees. The product is Indian highways — some mockups show
/// `$`, which is a Stitch artefact, not a currency decision.
String formatInr(Decimal value) => '₹${value.toStringAsFixed(2)}';

/// Rupees without decimals, for prices that are whole numbers. `₹80` reads
/// better than `₹80.00` on a dense menu; falls back when paise are present.
String formatInrCompact(Decimal value) {
  final hasPaise = value != value.truncate();
  return hasPaise ? formatInr(value) : '₹${value.truncate()}';
}

/// Sums line totals. Extension rather than a loose function so the intent reads
/// at the call site: `items.map((i) => i.lineTotal).sumMoney()`.
extension MoneySum on Iterable<Decimal> {
  Decimal sumMoney() => fold(Decimal.zero, (a, b) => a + b);
}
