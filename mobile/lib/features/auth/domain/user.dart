/// Auth domain models.
///
/// Hand-written rather than generated. These are small, stable, and read from
/// a contract that is already pinned down in docs/ui/05_SCREEN_API_WIRING.md —
/// codegen would add a build step to every edit without removing any real risk.
/// freezed earns its place when a union type does (loading/error states); it
/// does not for four fields off a JSON map.
library;

/// The full traveller profile, from `GET /user/profile` or `POST /auth/register`.
class User {
  const User({
    required this.id,
    required this.phone,
    this.name,
    this.email,
    this.createdAt,
  });

  factory User.fromJson(Map<String, dynamic> json) => User(
    id: json['id'] as int,
    phone: json['phone'] as String,
    name: json['name'] as String?,
    email: json['email'] as String?,
    createdAt: json['created_at'] == null
        // Timestamps are ISO 8601 UTC with a Z. Parsed to UTC and converted
        // only for display — countdown maths in local time is right by
        // accident and wrong across a DST or clock change.
        ? null
        : DateTime.parse(json['created_at'] as String).toUtc(),
  );

  final int id;
  final String phone;
  final String? name;
  final String? email;
  final DateTime? createdAt;

  /// What to greet them with. Falls back to the phone rather than "there" —
  /// a name the server never had should not be invented in the UI.
  String get displayName => name?.trim().isNotEmpty == true ? name!.trim() : phone;
}

/// The trimmed user embedded in a login response — no email, no timestamps.
/// Kept distinct from [User] so a screen cannot read a field the login payload
/// never carried and get a silent null.
class UserSummary {
  const UserSummary({required this.id, required this.phone, this.name});

  factory UserSummary.fromJson(Map<String, dynamic> json) => UserSummary(
    id: json['id'] as int,
    phone: json['phone'] as String,
    name: json['name'] as String?,
  );

  final int id;
  final String phone;
  final String? name;

  String get displayName => name?.trim().isNotEmpty == true ? name!.trim() : phone;
}

class LoginResult {
  const LoginResult({
    required this.accessToken,
    required this.expiresIn,
    required this.user,
  });

  factory LoginResult.fromJson(Map<String, dynamic> json) => LoginResult(
    accessToken: json['access_token'] as String,
    expiresIn: Duration(seconds: json['expires_in'] as int),
    user: UserSummary.fromJson(json['user'] as Map<String, dynamic>),
  );

  final String accessToken;

  /// Advertised by the server so the client does not have to decode a token it
  /// is only meant to carry.
  final Duration expiresIn;
  final UserSummary user;
}
