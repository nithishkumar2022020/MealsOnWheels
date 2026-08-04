import 'package:flutter_test/flutter_test.dart';
import 'package:mealsonwheels/features/auth/domain/phone.dart';

void main() {
  group('toE164', () {
    test('prefixes the country code for a national number', () {
      expect(toE164('9876543210'), '+919876543210');
    });

    test('strips the separators people actually type', () {
      // Mirrors normalise_phone server-side. If these diverged, a user typing a
      // formatted number would bounce off a 422 the server would have accepted.
      expect(toE164('98765 43210'), '+919876543210');
      expect(toE164('98765-43210'), '+919876543210');
      expect(toE164('(98765) 43210'), '+919876543210');
      expect(toE164('  9876543210  '), '+919876543210');
    });

    test('does not double-prefix an already-international number', () {
      expect(toE164('+919876543210'), '+919876543210');
      // Pasted with the country code but no plus.
      expect(toE164('919876543210'), '+919876543210');
    });

    test('respects a non-default country code', () {
      expect(toE164('7911123456', countryCode: '+44'), '+447911123456');
    });
  });

  group('isValidE164', () {
    test('accepts a real Indian mobile', () {
      expect(isValidE164('+919876543210'), isTrue);
    });

    test('rejects a leading zero on the country code', () {
      expect(isValidE164('+09876543210'), isFalse);
    });

    test('rejects a missing plus', () {
      expect(isValidE164('919876543210'), isFalse);
    });

    test('rejects too short and too long', () {
      expect(isValidE164('+91987'), isFalse);
      expect(isValidE164('+9198765432109876'), isFalse);
    });
  });

  group('validatePhoneInput', () {
    test('accepts what a user would type', () {
      expect(validatePhoneInput('9876543210'), isNull);
      expect(validatePhoneInput('98765 43210'), isNull);
    });

    test('rejects empty and too-short input with actionable copy', () {
      expect(validatePhoneInput(''), 'Enter your phone number');
      expect(validatePhoneInput(null), 'Enter your phone number');
      // Not "invalid E.164" — that phrasing means nothing to a traveller.
      expect(validatePhoneInput('98765'), contains('10-digit'));
    });
  });

  group('validateOtp', () {
    test('accepts the stub and other digit strings', () {
      expect(validateOtp('123456'), isNull);
      // Leading zero is significant, which is why OTPs are strings not ints.
      expect(validateOtp('012345'), isNull);
      expect(validateOtp('1234'), isNull);
    });

    test('rejects empty and non-digits', () {
      expect(validateOtp(''), contains('6-digit'));
      expect(validateOtp('abcdef'), contains('6 digits'));
      expect(validateOtp('12 34 56'), contains('6 digits'));
    });
  });

  group('maskPhone', () {
    test('matches the server mask_phone format', () {
      expect(maskPhone('+919876543210'), '+919****3210');
    });

    test('fully masks anything too short to partially reveal', () {
      expect(maskPhone('12345'), '*****');
    });
  });
}
