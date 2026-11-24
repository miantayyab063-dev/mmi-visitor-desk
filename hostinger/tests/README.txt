Development tests only — do not upload this folder to public_html.
Production app requires only PHP + MySQL; Python/Node are not needed on Hostinger.
Linux test runner creates an isolated temporary MariaDB instance and test website.
Requires local PHP 8.2+ (pdo_mysql, mbstring, zip), MariaDB server/client core, Python.
Run: python3 tests/regression.py
Optional: MMI_TEST_PHP=/path/to/php MMI_TEST_MARIADB_BASE=/path/to/mariadb/usr
Browser tests: install Playwright locally, set MMI_TEST_BROWSER=1.
Optional MMI_PLAYWRIGHT_MODULE and MMI_BROWSER_EXECUTABLE choose test browser/runtime.
This runner uses a disposable database/temp folder and is not a live-hosting test.
Never run destructive tests against a production database; this runner creates its own.
