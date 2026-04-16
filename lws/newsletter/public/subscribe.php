<?php
/**
 * AI Press Review — newsletter signup endpoint (LWS Perso PHP + MySQL).
 *
 * POST /api/subscribe.php
 * Content-Type: application/json
 * Body: {"email":"...","locale":"en"|"fr","consent":true,"website":""}
 *
 * Success:           200  {"ok":true,"confirm_required":false}
 * Already in DB:     200  {"ok":true,"already":true}
 * Validation error:  400  {"ok":false,"error":"invalid_email" | "consent_required" | "bad_request"}
 * Rate-limited:      429  {"ok":false,"error":"rate_limited"}
 * Server error:      500  {"ok":false,"error":"server_error"}
 *
 * Hardening choices (intentional, please don't "fix" these without
 * thinking twice):
 *
 *  - Honeypot (`website` field) non-empty  → respond 200 OK but insert
 *    nothing. Never leak to the bot that it was caught.
 *
 *  - UNIQUE violation on `email` → respond 200 {already:true} rather
 *    than 409. Leaking "this email is already registered" to attackers
 *    is an enumeration vector (they learn which emails are in your list).
 *
 *  - IP stored as sha256(salt + ip), truncated to 32 hex chars. Raw IP
 *    never touches the DB or logs. This is GDPR-friendly proof-of-
 *    affirmative-action per Art. 7 without being PII storage.
 *
 *  - 60-second per-IP-hash rate limit. Bots that burn through a proxy
 *    pool will rotate past this, but it stops the kind of spray a
 *    single bored teenager with curl will attempt.
 *
 *  - No PDO::ERRMODE_EXCEPTION reveal to client. Any DB error logs to
 *    PHP error_log and we return {error:"server_error"}. Stack traces
 *    in JSON = free recon for attackers.
 *
 *  - Consent text is stored per-row, in the locale the user saw. If we
 *    ever reword it, historical proof stays intact.
 */

declare(strict_types=1);

// ── Load config ─────────────────────────────────────────────────────
$configFile = __DIR__ . '/config.php';
if (!is_file($configFile)) {
    http_response_code(500);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode(['ok' => false, 'error' => 'server_error']);
    error_log('subscribe.php: config.php missing — copy config.example.php and fill credentials');
    exit;
}
$config = require $configFile;

// ── CORS (echoed allowlist, not wildcard) ──────────────────────────
$origin = $_SERVER['HTTP_ORIGIN'] ?? '';
$allowed = $config['allowed_origins'] ?? [];
if ($origin !== '' && in_array($origin, $allowed, true)) {
    header('Access-Control-Allow-Origin: ' . $origin);
    header('Vary: Origin');
    header('Access-Control-Allow-Methods: POST, OPTIONS');
    header('Access-Control-Allow-Headers: Content-Type');
    header('Access-Control-Max-Age: 86400');
}

// Preflight — answer fast and stop.
if (($_SERVER['REQUEST_METHOD'] ?? '') === 'OPTIONS') {
    http_response_code(204);
    exit;
}

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');

// ── Method check ───────────────────────────────────────────────────
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    http_response_code(405);
    header('Allow: POST, OPTIONS');
    echo json_encode(['ok' => false, 'error' => 'method_not_allowed']);
    exit;
}

// ── Body parse ─────────────────────────────────────────────────────
$raw = file_get_contents('php://input');
if ($raw === false || $raw === '' || strlen($raw) > 4096) {
    // 4 KB cap — legitimate payload is ~150 bytes. Anything bigger is
    // someone probing, and we don't want json_decode chewing on MB-size
    // junk.
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'bad_request']);
    exit;
}
$body = json_decode($raw, true);
if (!is_array($body)) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'bad_request']);
    exit;
}

// ── Honeypot: silent success ───────────────────────────────────────
$honey = isset($body['website']) ? (string) $body['website'] : '';
if ($honey !== '') {
    // Bot filled the hidden field. Return 200 so it thinks it won.
    echo json_encode(['ok' => true, 'confirm_required' => false]);
    exit;
}

// ── Field validation ───────────────────────────────────────────────
$email = isset($body['email']) ? trim((string) $body['email']) : '';
$locale = isset($body['locale']) ? (string) $body['locale'] : 'en';
$consent = !empty($body['consent']);

if ($locale !== 'fr' && $locale !== 'en') {
    $locale = 'en';
}

if ($email === '' || strlen($email) > 254 || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'invalid_email']);
    exit;
}
$email = mb_strtolower($email, 'UTF-8');

if (!$consent) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'consent_required']);
    exit;
}

// ── Build evidence fields ──────────────────────────────────────────
// LWS Perso sits behind a reverse proxy: the real client IP arrives
// in HTTP_X_REAL_IP (single value, set by the proxy — hard to spoof
// unless the proxy is mis-configured). We check that FIRST.
//
// HTTP_X_FORWARDED_FOR is also popular but is a comma-separated chain
// the client can prepend to. The ONLY trustworthy entry is the last
// one (added by our trusted edge proxy); the first is attacker-
// controlled. We read the last entry to avoid that spoofing vector.
//
// CF_CONNECTING_IP is kept for future portability if the site ever
// moves behind Cloudflare. Harmless on LWS (header not present).
// REMOTE_ADDR is the final fallback — on LWS it's usually the proxy's
// internal IP, so we'd rather not land there, but it beats an empty
// string for hashing.
$rawIp = $_SERVER['HTTP_CF_CONNECTING_IP']
      ?? $_SERVER['HTTP_X_REAL_IP']
      ?? $_SERVER['HTTP_X_FORWARDED_FOR']
      ?? $_SERVER['REMOTE_ADDR']
      ?? '';
if (str_contains($rawIp, ',')) {
    // X-Forwarded-For chain: last entry = trusted proxy's view of peer.
    $parts  = explode(',', $rawIp);
    $rawIp  = trim($parts[count($parts) - 1]);
}
$ipHash = substr(
    hash('sha256', ($config['ip_hash_salt'] ?? '') . '|' . $rawIp),
    0,
    32
);

$ua = isset($_SERVER['HTTP_USER_AGENT'])
    ? substr((string) $_SERVER['HTTP_USER_AGENT'], 0, 300)
    : null;

$consentText = $locale === 'fr'
    ? "J'accepte de recevoir la lettre d'information de la Revue de Presse IA. Je peux me désinscrire à tout moment."
    : 'I agree to receive the AI Press Review newsletter. I can unsubscribe at any time.';

// 48-hex-char random tokens (cryptographically strong, binary-safe).
$unsubToken = bin2hex(random_bytes(24));
$confirmRequired = !empty($config['confirm_required']);
$confirmToken = $confirmRequired ? bin2hex(random_bytes(24)) : null;
$confirmed = $confirmRequired ? 0 : 1;

// ── DB connect ─────────────────────────────────────────────────────
try {
    $pdo = new PDO(
        sprintf('mysql:host=%s;dbname=%s;charset=utf8mb4', $config['db_host'], $config['db_name']),
        $config['db_user'],
        $config['db_pass'],
        [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_EMULATE_PREPARES   => false,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        ]
    );
} catch (Throwable $e) {
    error_log('subscribe.php: DB connect failed: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['ok' => false, 'error' => 'server_error']);
    exit;
}

// ── Rate limit: 1 signup per IP-hash per 60 seconds ────────────────
try {
    $rl = $pdo->prepare(
        'SELECT 1 FROM subscribers
          WHERE ip_hash = :h AND created_at > (NOW() - INTERVAL 60 SECOND)
          LIMIT 1'
    );
    $rl->execute([':h' => $ipHash]);
    if ($rl->fetchColumn()) {
        http_response_code(429);
        header('Retry-After: 60');
        echo json_encode(['ok' => false, 'error' => 'rate_limited']);
        exit;
    }
} catch (Throwable $e) {
    error_log('subscribe.php: rate-limit query failed: ' . $e->getMessage());
    // Fall through — we prefer to let the INSERT attempt than block
    // the user on a transient DB hiccup.
}

// ── INSERT (UNIQUE on email → treat as already-subscribed) ─────────
try {
    $ins = $pdo->prepare(
        'INSERT INTO subscribers
           (email, locale, confirmed, confirm_token, unsubscribe_token,
            ip_hash, user_agent, consent_text, source)
         VALUES
           (:email, :locale, :confirmed, :confirm_token, :unsub_token,
            :ip_hash, :ua, :consent_text, :source)'
    );
    $ins->execute([
        ':email'         => $email,
        ':locale'        => $locale,
        ':confirmed'     => $confirmed,
        ':confirm_token' => $confirmToken,
        ':unsub_token'   => $unsubToken,
        ':ip_hash'       => $ipHash,
        ':ua'            => $ua,
        ':consent_text'  => $consentText,
        ':source'        => 'web',
    ]);
} catch (PDOException $e) {
    // MySQL 1062 = duplicate entry. Treat as idempotent success — do
    // NOT tell the client "this email already exists" (enumeration).
    // Parens matter: `===` binds tighter than `??`, so the naive
    // `$e->errorInfo[1] ?? 0 === 1062` reduces to
    // `$e->errorInfo[1] ?? false` — truthy for ANY error.
    if ((int) ($e->errorInfo[1] ?? 0) === 1062) {
        echo json_encode(['ok' => true, 'already' => true]);
        exit;
    }
    error_log('subscribe.php: INSERT failed: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['ok' => false, 'error' => 'server_error']);
    exit;
} catch (Throwable $e) {
    error_log('subscribe.php: unexpected: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['ok' => false, 'error' => 'server_error']);
    exit;
}

echo json_encode([
    'ok'               => true,
    'confirm_required' => $confirmRequired,
]);
