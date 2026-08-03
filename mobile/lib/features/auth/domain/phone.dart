/// Phone normalisation, matching the server's rules exactly.
///
/// The backend strips ` `, `-`, `(`, `)`, `.` and then requires
/// `^\+[1-9]\d{6,14}$`. Doing the same client-side means a user who types
/// "+91 98765-43210" sees it accepted rather than bouncing off a 422, and that
/// two spellings of one number cannot become two accounts.
library;

const _separators = {' ', '-', '(', ')', '.'};

/// India. The mockup hardcodes this as a fixed prefix on the field.
const defaultCountryCode = '+91';

/// Strips the separators people actually type. Mirrors `normalise_phone` in
/// backend/app/schemas.py.
String stripSeparators(String raw) =>
    raw.split('').where((c) => !_separators.contains(c)).join().trim();

/// Builds the E.164 number to send, from a national-format field plus the
/// country code shown beside it.
///
/// The UI shows "+91" as a static prefix, so the field holds ten digits. A user
/// who pastes a full international number should not end up with "+91+919...".
String toE164(String input, {String countryCode = defaultCountryCode}) {
  final cleaned = stripSeparators(input);
  if (cleaned.startsWith('+')) return cleaned;
  // A pasted number may carry the country code without the plus.
  final bare = countryCode.replaceAll('+', '');
  if (cleaned.startsWith(bare) && cleaned.length > bare.length) {
    return '+$cleaned';
  }
  return '$countryCode$cleaned';
}

final _e164 = RegExp(r'^\+[1-9]\d{6,14}$');

bool isValidE164(String value) => _e164.hasMatch(value);

/// Indian mobile numbers are exactly ten digits.
const _indianMobileDigits = 10;

/// Validates what the user typed, in the format they typed it.
/// Returns null when valid, or a message for the field's error slot.
String? validatePhoneInput(String? input, {String countryCode = defaultCountryCode}) {
  final raw = (input ?? '').trim();
  if (raw.isEmpty) return 'Enter your phone number';

  final e164 = toE164(raw, countryCode: countryCode);
  if (!isValidE164(e164)) {
    // Deliberately not "invalid E.164" — that phrasing means nothing to a
    // traveller at a bus stop.
    return 'Enter a valid 10-digit mobile number';
  }

  // E.164 alone is too permissive here. The pattern accepts as few as seven
  // digits in total, so "+9198765" passes it — and the server's pattern is the
  // same, because a backend serving E.164 should not hardcode one country. The
  // field sitting beside a fixed "+91" asks for exactly ten digits, so the
  // country-specific rule belongs on the client that makes that promise.
  if (countryCode == defaultCountryCode && e164.startsWith(countryCode)) {
    final national = e164.substring(countryCode.length);
    if (national.length != _indianMobileDigits) {
      return 'Enter a valid 10-digit mobile number';
    }
  }

  return null;
}

/// `+919876543210` -> `+919****3210`. Matches `mask_phone` server-side.
///
/// Used anywhere a number is shown back for confirmation. A full number on a
/// screen someone can shoulder-surf is a small leak that costs nothing to avoid.
String maskPhone(String phone) {
  if (phone.length < 8) return '*' * phone.length;
  return '${phone.substring(0, 4)}****${phone.substring(phone.length - 4)}';
}

/// OTPs are digit strings, not ints — a leading zero is significant.
/// The server accepts 4–8 digits; the stub is 6.
String? validateOtp(String? input) {
  final raw = (input ?? '').trim();
  if (raw.isEmpty) return 'Enter the 6-digit code';
  if (!RegExp(r'^\d{4,8}$').hasMatch(raw)) return 'The code is 6 digits';
  return null;
}
