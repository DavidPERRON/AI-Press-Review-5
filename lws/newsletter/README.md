# AI Press Review — newsletter signup (LWS Perso)

A 4-file PHP backend that accepts email signups from the form on
`podcast.aequitus.net` (GitHub Pages) and stores them in your own
LWS-hosted MySQL database. No third-party processor, no analytics
pixel, no cookies. GDPR-clean.

```
podcast.aequitus.net (GitHub Pages, static)
        │
        │  cross-origin POST {email,locale,consent}
        ▼
aequitus.net/api/subscribe.php   (LWS Perso PHP)
        │
        │  PDO INSERT
        ▼
MySQL 8.x  ── subscribers table  (LWS Perso, daily backups included)
```

## Files

```
lws/newsletter/
├── README.md             ← you are here
├── schema.sql            ← run ONCE in phpMyAdmin to create the tables
└── public/               ← upload the contents to /public_html/api/ on LWS
    ├── .htaccess         ← hardens config.php, fixes Authorization header
    ├── subscribe.php     ← POST endpoint called by the form
    ├── export.php        ← GET endpoint, Bearer-authed, returns CSV
    ├── unsubscribe.php   ← GET endpoint with ?t=<token>, self-service
    ├── health.php        ← GET /api/health.php — liveness probe
    ├── config.example.php ← template; copy to config.php and fill in
    └── config.php        ← you create this from config.example.php (gitignored)
```

## Initial deployment (once, ~20 min)

### Step 1 — Create the MySQL database

1. Log into [panel.lws.fr](https://panel.lws.fr/).
2. Open your hosting → **"Bases de données MySQL"**.
3. Click **"Créer une base"**, name it something like `newsletter`
   (LWS will prefix it with your account, e.g. `lwsXXXXXX_newsletter`).
4. Note the 4 connection values it shows you:
   - host (usually `localhost`)
   - DB name (`lwsXXXXXX_newsletter`)
   - user (`lwsXXXXXX`)
   - password (the one you just set)

### Step 2 — Create the tables

1. From the same page, click **"phpMyAdmin"** for that DB.
2. Click the DB name in the left sidebar.
3. Click the **"SQL"** tab.
4. Paste the entire contents of `schema.sql` (in this folder).
5. Click **"Exécuter"**. You should see two new tables: `subscribers`
   and `unsubscribe_log`.

### Step 3 — Generate the secrets

In a Terminal on your laptop:

```bash
echo "ip_hash_salt: $(openssl rand -hex 32)"
echo "admin_token : $(openssl rand -hex 32)"
```

Save both in 1Password / Bitwarden. The `admin_token` is what you'll
need later to download the subscriber CSV.

### Step 4 — Build config.php

1. Copy `public/config.example.php` to `public/config.php` (locally).
2. Fill in the 4 DB values from Step 1.
3. Paste the two secrets from Step 3 into `ip_hash_salt` and
   `admin_token`.
4. **Do NOT commit `config.php` to git.** It's already in `.gitignore`,
   but double-check.

### Step 5 — Upload to LWS

1. In the LWS panel → **"Gestionnaire de fichiers"** (or open FTP with
   your favourite client).
2. Navigate to the web root of your site. Depending on the plan vintage,
   that's either `/public_html/` OR `/htdocs/` (newer Perso plans use
   `htdocs`). A quick way to check: whatever folder contains your
   current `index.html` — that's the web root.
3. Create a folder `api` inside the web root.
4. Upload all six files from `public/`:
   - `subscribe.php`
   - `export.php`
   - `unsubscribe.php`
   - `health.php`
   - `config.php` ← the one YOU created (not the example)
   - `.htaccess`

### Step 6 — Smoke test

```bash
# 1. Liveness — should print {"ok":true,"ts":"…","db":true}
curl https://aequitus.net/api/health.php

# 2. Real signup — should print {"ok":true,"confirm_required":false}
curl -X POST https://aequitus.net/api/subscribe.php \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","locale":"en","consent":true}'

# 3. Same email again — should print {"ok":true,"already":true}
curl -X POST https://aequitus.net/api/subscribe.php \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","locale":"en","consent":true}'

# 4. Validation — should print {"ok":false,"error":"invalid_email"}
curl -X POST https://aequitus.net/api/subscribe.php \
  -H 'Content-Type: application/json' \
  -d '{"email":"not-an-email","locale":"en","consent":true}'

# 5. Consent missing — should print {"ok":false,"error":"consent_required"}
curl -X POST https://aequitus.net/api/subscribe.php \
  -H 'Content-Type: application/json' \
  -d '{"email":"x@y.com","locale":"en","consent":false}'

# 6. Honeypot — should print {"ok":true,"confirm_required":false}
#    AND the subscribers table should NOT have a new row.
curl -X POST https://aequitus.net/api/subscribe.php \
  -H 'Content-Type: application/json' \
  -d '{"email":"bot@y.com","locale":"en","consent":true,"website":"http://spam"}'

# 7. Admin export (replace TOKEN with your actual admin_token)
curl -H "Authorization: Bearer TOKEN" \
     https://aequitus.net/api/export.php \
     -o subscribers-test.csv
head subscribers-test.csv
```

Then clean up the test row in phpMyAdmin:

```sql
DELETE FROM subscribers WHERE email = 'you@example.com';
DELETE FROM unsubscribe_log;  -- if your unsubscribe test ran
```

## Operate

### Monitor the LWS error log

LWS panel → **"Gestionnaire de fichiers"** → look for `error_log` in
`/public_html/api/` (or `/public_html/`). Every `error_log()` call in
the PHP scripts ends up there. Common entries you might see:

| Log line | Meaning |
| --- | --- |
| `subscribe.php: config.php missing` | You uploaded the .php files but forgot config.php. |
| `subscribe.php: DB connect failed` | DB credentials wrong, or LWS DB temporarily down. |
| `export.php: bad token from <ip>` | Someone tried to brute-force the export endpoint. |

### Inspect rows directly

phpMyAdmin → click the `subscribers` table → "Browse" tab. Or via SQL:

```sql
SELECT count(*) AS n, locale FROM subscribers GROUP BY locale;

SELECT email, locale, created_at
  FROM subscribers
 ORDER BY created_at DESC
 LIMIT 20;

-- Most recent signups by IP-hash, for spam investigation
SELECT ip_hash, count(*), min(created_at), max(created_at)
  FROM subscribers
 GROUP BY ip_hash
 HAVING count(*) > 3
 ORDER BY count(*) DESC;
```

### Manually unsubscribe someone

```sql
DELETE FROM subscribers WHERE email = 'unwanted@example.com';
INSERT INTO unsubscribe_log (email_hash, reason)
  VALUES (
    SUBSTRING(SHA2(CONCAT('YOUR_IP_HASH_SALT|', 'unwanted@example.com'), 256), 1, 32),
    'manual'
  );
```

(Or skip the audit log entry if you don't care.)

### Download a fresh CSV any time

```bash
# Save your token somewhere greppable, or paste it interactively:
TOKEN="$(read -s -p 'Admin token: ' t; echo "$t")"
curl -H "Authorization: Bearer $TOKEN" \
     https://aequitus.net/api/export.php \
     -o subscribers-$(date +%F).csv
```

## Off-site backup (optional but recommended)

LWS already runs daily snapshots of your Perso account — but if LWS
ever has a bad day, your subscriber list goes with it. The optional
GitHub Action at `.github/workflows/backup-subscribers.yml` (in the
main repo) downloads the CSV every night, encrypts it with GPG using a
passphrase only you know, and commits the encrypted blob to a private
backup repo.

To enable:

1. Create a private GitHub repo, e.g. `<you>/aequitus-newsletter-backup`.
2. In the AI-Press-Review-5 repo settings → Secrets and variables →
   Actions → add:
   - `LWS_EXPORT_TOKEN` = your `admin_token`
   - `BACKUP_GPG_PASSPHRASE` = a long random string (NOT the admin token)
   - `BACKUP_REPO_TOKEN` = a fine-grained PAT with write access to
     ONLY the backup repo
3. Edit the workflow's `BACKUP_REPO` env to point at your new repo.
4. The workflow runs at 05:00 UTC daily; trigger it once manually
   from the Actions tab to confirm it works.

To decrypt later:

```bash
gpg --decrypt --batch --passphrase "$BACKUP_GPG_PASSPHRASE" \
    subscribers-2026-04-16.csv.gpg > subscribers-2026-04-16.csv
```

## GDPR posture

What we store per signup:

| Column | Why | PII? |
| --- | --- | --- |
| `email` | The whole point. | Yes. |
| `locale` | Picks the right newsletter (FR vs EN) when sent. | No. |
| `created_at` | Proof of when consent was given. | No. |
| `consent_text` | Exact wording the user agreed to (per locale). | No. |
| `ip_hash` | SHA-256 of `salt + IP`, truncated to 32 hex chars. Non-reversible. Used for the 60s rate-limit and Art. 7 proof. **The raw IP is never stored.** | No. |
| `user_agent` | Same proof purpose; truncated to 300 chars. | Marginal. |
| `unsubscribe_token` | Lets the user leave without authenticating. | No. |

What we don't do:

- No third-party processors (no Mailchimp, no SendGrid, no Brevo).
- No tracking pixels in the form page.
- No cookies set by `subscribe.php` (it never even calls `setcookie`).
- No raw IPs stored or logged (LWS Apache access log is the only place
  the raw IP exists, and that's outside our control — LWS rotates it
  on their schedule).

To honour a deletion request:

```sql
DELETE FROM subscribers WHERE email = 'request@example.com';
INSERT INTO unsubscribe_log (email_hash, reason)
  VALUES (
    SUBSTRING(SHA2(CONCAT('SALT|', 'request@example.com'), 256), 1, 32),
    'rtbf'  -- "right to be forgotten"
  );
```

The encrypted backups still contain the email until they expire (you
choose retention in the GH Action — default is "all snapshots kept
forever"). To purge from backups too, you'd need to rewrite the backup
repo's git history, which is out of scope here. If you expect frequent
RTBF requests, set the GH Action to keep only the last 30 snapshots
and let the older ones drop out naturally.

## Local dev

You can run the PHP locally with the built-in dev server to test
schema migrations or new features before uploading to LWS.

```bash
# In one shell:
cd lws/newsletter/public
cp config.example.php config.php
# Edit config.php to point at a local MySQL (e.g. via Docker:
#   docker run --rm -e MYSQL_ROOT_PASSWORD=root -p 3306:3306 mysql:8)

mysql -h 127.0.0.1 -u root -proot -e "CREATE DATABASE newsletter;"
mysql -h 127.0.0.1 -u root -proot newsletter < ../schema.sql

php -S 127.0.0.1:8001

# In another shell:
curl http://127.0.0.1:8001/health.php
curl -X POST http://127.0.0.1:8001/subscribe.php \
  -H 'Content-Type: application/json' \
  -d '{"email":"local@test","locale":"en","consent":true}'
```
