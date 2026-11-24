MMI HOSTINGER EDITION — PHP 8.2+ / MySQL-compatible MariaDB
=========================================================
Start with START_HERE_HOSTINGER.txt (Roman Urdu). This is a separate web package.
Keep the prior Python desktop package if you still want a local desktop installation.
This edition needs no Python process, VPS, Node or Composer on the hosting server.
PHP extensions required: PDO MySQL, mbstring, zip. Prefer PHP 8.3/8.4 with host patches.

INSTALLATION
Use a dedicated empty database. Copy public_html/mmi to public_html/mmi; place mmi_private
beside public_html, not inside it. Copy config.example.php to private config.php and set
actual credentials, exact HTTPS app_url (including /mmi) and random installation key.
Do NOT upload test config.php; none is included in the release.
Open /mmi/install.php for preflight, then /mmi/ to create the first admin using the key.
Schema is created automatically only after a valid setup key. Manual schema.sql import
is optional; setup still requires the private key and cannot replace an existing admin.
Database user needs CREATE/SELECT/INSERT/UPDATE for installation and normal operations.
SHOW CREATE TABLE access is needed for full SQL backups. No root or SUPER permission needed.
If the platform requires a different DB host, use the exact hPanel-provided host.
Keep private directory readable/writable by your PHP owner only (normally 700), private
config normally 600; use hosting-owner permissions rather than world-writable 777.
Backups directory must be writable. Root .htaccess blocks listing and redirects to HTTPS.
Do not overwrite an existing website's root .htaccess; this package stays under /mmi.
If your deployment uses another folder, adjust app_url; API URLs resolve relatively.

FEATURES
Same MMI navy/emerald/gold interface and required developer credit.
Admin/receptionist accounts, password resets/disabling, 30-minute idle / 12-hour maximum
sessions. Tokens are random and only SHA-256 hashes are in MySQL. Passwords are hashed.
Persistent login, logout, last-seen and end-reason history survives server restarts.
Mobile search begins on first digit, 0 -> 03 -> 030; names/CNIC and paged results.
Visitor profile and last meeting/purpose/remarks autofill. IN/OUT automatic server time
(Pakistan UTC+05:00), saved-by and OUT-by ID. One active visit per person.
Profile corrections preserve old identity snapshots. Visit/call corrections record
actor, time, reason, before/after history and optimistic version conflict checks.
Telephone caller lookup uses previous calls and visitor directory. +92 / 03 normalization.
Timer or manual call start/duration, caller, handled-by and remarks are available.
Full-database visitor/call history with search/date filters, pagination, print/PDF, CSV.
SQL uses bound parameters. HTML reports escape user content. No public database file.
Backups/accounts/audit downloads admin-only. Staff can view/print the records their role permits.

BACKUP / RESTORE
Each successful save/edit/login/logout/account action updates both private Excel files.
MMI_All_Records.xlsx: visitors, visits, callbacks, login activity, record changes.
MMI_Login_Change_History.xlsx: login/logout and record changes in separate sheets.
If Excel writing fails, the primary MySQL commit remains saved, with a visible warning.
An admin can download a fresh full workbook regardless of the currently selected filter.
Restore Backup button downloads MMI_MySQL_Backup.sql, including table definitions and
records. Restore through phpMyAdmin into a NEW dedicated database; then point private
config to it and verify before using it. The dump contains DROP TABLE statements: do not
import into a database holding another website. Back up the current database first.
MySQL backup contains hashed credentials/session hashes; protect it as sensitive data.
Regular encrypted off-site backups are the hosting administrator's responsibility.

OLD DESKTOP DATA — OPTIONAL MIGRATION
Run locally on a copy of a STOPPED desktop SQLite database:
  python tools/export_desktop_records.py /path/to/mmi.sqlite3 /path/to/mmi_import.sql
Initialize the website/admin first but do NOT enter any visitors/calls. Take an SQL
backup. Import the generated file using phpMyAdmin into that fresh installed database.
Never merge into populated visitor/call tables; duplicate IDs will conflict. This tool
preserves visitors, visit identity snapshots, calls, record changes and old login history.
User accounts/passwords are NOT migrated. Create corresponding website staff logins.
Imported login history is inactive (user_id 0); stored staff login labels remain visible.
After import verify counts/search/history, then download fresh Excel/SQL backups. Existing
local and hosted copies are separate; there is no automatic two-way synchronization.

SECURITY / LIMITS
Only public_html/mmi is web-visible; private PHP/config/backups live outside web root.
Installation key protects initial setup. Existing admin cannot be replaced via setup.
Host/origin validation, X-MMI request header, SameSite Strict, HttpOnly, Secure cookies
(HTTPS), CSP, escaping, login throttling and transactional version checks are included.
A SQL user/hosting owner can alter files/database: audit is append-only via application,
not cryptographic tamper protection. Do not give database credentials to reception staff.
Data and Excel files are not encrypted by the application. Use SSL, protected accounts,
server/disk protection and encrypted backups. No promise of impossible data theft.
App has no telephony/PBX integration. First setup requires config/database access, not
just an unzip. Hostinger deployment still needs your real-domain installation check.

TESTS
Local isolated PHP 8.3 + MariaDB 10.11 integration and real Chromium checks were run.
See TEST_REPORT.txt. Developer-only regression/browser scripts are in tests/.
Do not upload tests/ or tools/ to public_html. The production application needs PHP only.

HOSTINGER OFFICIAL REFERENCES
https://www.hostinger.com/support/1583542-how-to-create-a-new-mysql-database-in-hostinger/
https://www.hostinger.com/support/1575755-how-to-change-the-php-version-of-your-hostinger-hosting-plan/
https://www.hostinger.com/support/1583226-which-database-management-system-is-used-at-hostinger/
