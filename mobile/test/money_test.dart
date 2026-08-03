import 'package:decimal/decimal.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mealsonwheels/core/money.dart';

void main() {
  group('parseMoney', () {
    test('parses the API string form exactly', () {
      expect(parseMoney('80.00'), Decimal.parse('80.00'));
      expect(parseMoney('320.50'), Decimal.parse('320.50'));
      expect(parseMoney('15'), Decimal.fromInt(15));
    });

    test('sums without floating-point drift', () {
      // The reason money is Decimal and not double. As doubles, 0.1 + 0.2 is
      // 0.30000000000000004, and this sum would be a rupee short over a
      // large enough order.
      final items = [
        parseMoney('0.10'),
        parseMoney('0.20'),
      ];
      expect(items.sumMoney(), Decimal.parse('0.30'));

      final order = [
        parseMoney('280.00'),
        parseMoney('280.00'),
        parseMoney('120.00'),
        parseMoney('15.00'),
        parseMoney('15.00'),
        parseMoney('15.00'),
        parseMoney('15.00'),
      ];
      expect(order.sumMoney(), Decimal.parse('740.00'));
    });

    test('throws rather than defaulting to zero', () {
      // A price that silently reads as free is worse than a crash.
      expect(() => parseMoney('free'), throwsFormatException);
      expect(() => parseMoney(''), throwsFormatException);
    });
  });

  group('tryParseMoney', () {
    test('returns null for absent or unparseable values', () {
      expect(tryParseMoney(null), isNull);
      expect(tryParseMoney('abc'), isNull);
      expect(tryParseMoney(const {}), isNull);
    });

    test('accepts strings and ints', () {
      expect(tryParseMoney('40.00'), Decimal.parse('40.00'));
      expect(tryParseMoney(40), Decimal.fromInt(40));
    });
  });

  group('formatting', () {
    test('formatInr always shows paise', () {
      expect(formatInr(parseMoney('80')), '₹80.00');
      expect(formatInr(parseMoney('320.50')), '₹320.50');
    });

    test('formatInrCompact drops trailing zeros only when whole', () {
      expect(formatInrCompact(parseMoney('80.00')), '₹80');
      expect(formatInrCompact(parseMoney('320.50')), '₹320.50');
      expect(formatInrCompact(parseMoney('15')), '₹15');
    });
  });
}
