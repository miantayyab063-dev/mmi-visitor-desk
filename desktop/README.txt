MMI — RECEPTION DESK, VISITORS & CALLBACKS
Updated 02 November 2026
========================================
WINDOWS / LOCAL COMPUTER
1. Extract ZIP to a permanent folder; do not run inside ZIP.
2. Install Python 3.10+ with Add Python to PATH enabled.
3. Double-click START_MMI.bat; keep console open.
4. Browser address: http://127.0.0.1:8765
5. Create administrator Login ID and password (10+ characters).
6. Admin / Login IDs: create receptionist accounts and provide their login details.
Stop using Ctrl+C in console. Mac/Linux: python3 app.py
Local app requires no internet or extra Python packages. It runs in your browser,
with a real SQLite file on the computer; it is not a standalone Windows EXE.

UPDATING FROM AN EARLIER MMI VERSION
Stop MMI. Back up the ENTIRE old data folder. Replace program files and static folder
with this release; retain your existing data folder. Schema updates are automatic.
Do not overwrite your populated data folder with an empty one from a fresh extraction.
First-ever upgrade from password-only MMI asks for the previous office password.
Old visits remain; OUT times never recorded remain unknown, not invented.

LIVE SEARCH / AUTOFILL
Type just 0 in Mobile: matches starting with 0 appear below.
Continue 03 -> 030 -> 0300 etc: matching list narrows automatically.
Name and CNIC fields also search while typing, from the first character/digit.
Find existing visitor supports names, phone prefixes or full CNIC.
Suggestions are in pages of 30; Show more loads further matches, with the total shown.
Click a match: name/mobile/CNIC and last meeting/purpose/remarks autofill.
The notice shows last IN/OUT and saved-by ID. Edit copied meeting/purpose/remarks
for the NEW visit. IN/Enter saves a new visit with automatic server time.
Full +92/0092 mobile formats normalize to 03. Identifiers keep leading zeroes.
Every visitor needs a unique mobile and unique 13-digit CNIC.
Conflicting identities cannot silently merge.

VISITOR IN / OUT / CORRECTIONS
IN — Save entry creates the visit only after submission, not while typing.
OUT on a history row saves departure time and the login ID marking OUT.
A visitor cannot have a second active IN before their previous visit is OUT.
Edit on a saved visit changes meeting, purpose and remarks; a reason is required.
Save profile correction changes name/mobile/CNIC for FUTURE visits; add a reason.
Selecting a visitor and editing their identity before IN also updates their profile,
with change history, while creating the new visit.
Past visits retain the original name/mobile/CNIC recorded on that visit.
Automatic IN/OUT timestamps are not manually overwritten.
Version checks stop another screen's older correction overwriting newer data.
Changes button shows who changed what, when, with before/after details.
Database change history is append-only through the app; no delete feature.

FIND / PRINT HISTORY
Find record: type a phone number, name or CNIC. Matching searches cover current
profiles and historical identity snapshots. Records of the matched visitor(s) appear.
Optional date filter narrows visits. All visits clears person/date/text filters.
Print complete history opens EVERY matching visit, across all pages, with all saved
visit fields: identity, IN/OUT, host, purpose, remarks, saved-by, OUT-by, updates/version.
Click Print / Save PDF on that page. CSV export follows the same filters.
Picking a returning visitor clears old filters and displays their full history.

TELEPHONE / CALLBACKS
Incoming, Outgoing or Callback; number, caller, start time, duration seconds,
spoken/handled by, discussion/remarks. Time/duration may be entered manually.
Start / End call measures elapsed time; End before Save call.
Edit a call from history to correct fields with a reason. Original saved-by stays,
updated-by/time and before/after history are recorded separately.
Call history searches the complete database, with date filters and pages of 30.
Print/PDF and CSV export include ALL matching calls, beyond the current page.
Type a phone prefix (even 0) or a caller name in the call form to retrieve saved
caller/visitor details. Selecting it fills the number, name and latest call remarks.
Telephone-line/PBX integration is not connected; incoming caller ID is not auto-detected.

LOGIN / LOGOUT HISTORY
Each staff member has their own ID. Admin can create/reset/disable accounts.
Current and previous login/logout information appears after sign-in.
Admin sees recent sessions and downloads the separate complete history workbook.
Explicit Sign out records exact logout time. Closing a browser or power failure
cannot prove exact logout time: last activity and end reason are retained instead.
Sessions expire after 30 minutes of API inactivity or 12 hours maximum; background
LIVE checks do not keep a session alive. Server restart requires a new login and
marks unfinished previous sessions as Server restarted / exact logout unknown.
History survives restarts because it is stored in SQLite, not browser memory.
Passwords are hashed; history and Excel never include plain passwords or hashes.

DATA / BACKUPS
Primary database: data/mmi.sqlite3
Automatic workbooks:
  data/backups/MMI_All_Records.xlsx
  data/backups/MMI_Login_Change_History.xlsx
Both refresh after successful save/edit/login/logout/account actions and at startup.
All-record workbook: visitors, every visit, every call, login activity.
History workbook: complete login/logout activity and before/after record change history.
Admin has Excel Backup (All), Restore Backup (SQLite download), and history download.
Receptionist can print/export visit records; complete backups/accounts/audit downloads
are admin-only. Authorized staff can still see/print the data needed for their role.
Close backup workbooks in Excel while using MMI on Windows, so replacement is allowed.
If Excel backup fails, primary data remains saved and the app shows a warning.
LIVE indicates a recent successful database write check, repeated every 5 seconds.
Saved to database confirms a committed save; OFFLINE/error indicates an unconfirmed save.
If a response is lost, retry the SAME unsaved form; duplicate request tokens prevent
extra IN/call records. Do not clear the form first.

RESTORE / MOVE
Use Restore Backup for a full consistent SQLite copy. Stop app before restoring.
Keep current data folder safe; replace data/mmi.sqlite3 with the downloaded SQLite
backup, removing old -wal/-shm companion files only AFTER software is fully stopped
and your old whole data folder is backed up. Restart and sign in.
Excel files are reports, not automatic restoration inputs.
To move manually, stop MMI and copy the ENTIRE data folder. Do not copy just the main
SQLite file while running: recent transactions may be in its WAL companion file.

SECURITY / WEBSITE
Read WEBSITE_DEPLOYMENT.txt for hosting. New start_site.py uses a production WSGI
server behind HTTPS. Local and hosted frontends use the same backend/data directory
when they access the same running server. Separate copies are NOT auto-synced.
The package does not publish or deploy to your website automatically.
Use protected server access, HTTPS, OS disk encryption and protected off-site backups.
SQLite/Excel files are not encrypted by this program. An OS/server administrator with
file access can read them. No software can promise that theft is impossible.
Admin-only bulk backups, secure web cookies, origin/host validation, throttled login,
parameterized SQL, escaped print output, CSP, disabled website bootstrap and append-only
change history improve security; they are not a full external penetration audit.

CHECKS
python3 -m unittest discover -s tests -v
See CHECK_RESULTS.txt. Tests use isolated synthetic data, never your office data.

DESIGN UPDATE
Navy / emerald / gold MMI theme, responsive navigation and branded sign-in screen.
Live connection indicator stays in the top bar for every workspace page.
Visitor and callback pages have consistent entry, history, refresh, search, print,
export and correction controls. Clear empty states and database-save feedback.
Show/hide password control, keyboard focus styling and reduced-motion support.
Footer and printed reports: Developed by mianmuhamamdtayyab
