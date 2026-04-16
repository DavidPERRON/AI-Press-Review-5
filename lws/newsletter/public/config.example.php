<?php
/**
 * AI Press Review — newsletter config (template).
 *
 * DEPLOYMENT:
 *   1. Copy this file to `config.php` on your LWS server (same dir as
 *      subscribe.php).
 *   2. Fill in the 4 DB values from your LWS panel →
 *      "Gérer mon hébergement" → "Bases de données MySQL".
 *   3. Generate two long random tokens for `ip_hash_salt` and
 *      `admin_token`. On macOS:
 *         openssl rand -hex 32
 *      Store `admin_token` in 1Password — you'll need it to download
 *      the subscriber CSV.
 *   4. NEVER commit `config.php` to git. It's already in .gitignore.
 *
 * Returns an associative array (picked up via `require` in subscribe.php).
 */
return [
    // MySQL connection (from LWS panel → "Bases de données MySQL" or
    // the welcome email you got after creating the DB).
    //   - Newer LWS Perso plans: host = '127.0.0.1' (LWS's own panel
    //     spells out "utilisez 127.0.0.1 et pas localhost"). Older
    //     plans still accept 'localhost'. If in doubt, try both.
    //   - LWS gives you a single DB whose name usually equals the
    //     account handle (e.g. 'aequi2763377' or 'lwsXXXXXX'). No
    //     separate 'newsletter' suffix.
    //   - User is typically the same handle.
    'db_host' => '127.0.0.1',
    'db_name' => 'aequiXXXXXXX',
    'db_user' => 'aequiXXXXXXX',
    'db_pass' => 'REPLACE-ME',

    // A long random string used to hash IPs before storing them (so
    // the DB never contains raw IPs). MUST stay constant — changing
    // it invalidates the 60s rate-limit dedup. Generate once:
    //   openssl rand -hex 32
    'ip_hash_salt' => 'REPLACE-ME-WITH-32-HEX-CHARS-MINIMUM',

    // Bearer token the GH Action (or you with curl) uses to download
    // the subscriber CSV via export.php. Keep secret.
    'admin_token'  => 'REPLACE-ME-WITH-A-DIFFERENT-LONG-RANDOM-STRING',

    // Origins allowed to POST cross-origin to subscribe.php. The
    // request's Origin header is echoed back only if it appears in
    // this list — otherwise CORS blocks the browser from reading
    // the response.
    'allowed_origins' => [
        'https://podcast.aequitus.net',
        // Keep these for local preview; remove if you don't use them:
        'http://localhost:8000',
        'http://127.0.0.1:8000',
    ],

    // If you ever wire a double-opt-in sender (Resend, MailChannels,
    // plain PHP mail()…), flip this to true. subscribe.php will then
    // INSERT with confirmed=0 and a confirm_token instead of
    // confirmed=1.
    'confirm_required' => false,
];
