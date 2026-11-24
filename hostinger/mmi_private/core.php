<?php
declare(strict_types=1);
date_default_timezone_set("Asia/Karachi");
final class ApiError extends RuntimeException
{
    public function __construct(public int $status, string $message)
    {
        parent::__construct($message);
    }
}
function fail(string $message, int $status = 400): never
{
    throw new ApiError($status, $message);
}
function conf(): array
{
    static $config = null;
    if ($config === null) {
        $file = __DIR__ . "/config.php";
        if (!is_file($file)) {
            fail(
                "Installation needed: create private config.php using the included Hostinger guide.",
                503,
            );
        }
        $config = require $file;
        if (!is_array($config)) {
            fail("Invalid private configuration.", 503);
        }
    }
    return $config;
}
function db(): PDO
{
    static $pdo = null;
    if ($pdo === null) {
        $c = conf();
        $pdo = new PDO(
            "mysql:host=" .
                $c["db_host"] .
                ";port=" .
                (int) ($c["db_port"] ?? 3306) .
                ";dbname=" .
                $c["db_name"] .
                ";charset=utf8mb4",
            $c["db_user"],
            $c["db_password"],
            [
                PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                PDO::ATTR_EMULATE_PREPARES => false,
                PDO::ATTR_STRINGIFY_FETCHES => false,
            ],
        );
    }
    return $pdo;
}
function rows(string $sql, array $args = []): array
{
    $q = db()->prepare($sql);
    $q->execute($args);
    return $q->fetchAll();
}
function one(string $sql, array $args = []): ?array
{
    $r = rows($sql, $args);
    return $r[0] ?? null;
}
function execute(string $sql, array $args = []): int
{
    $q = db()->prepare($sql);
    $q->execute($args);
    return $q->rowCount();
}
function scalar(string $sql, array $args = []): mixed
{
    $q = db()->prepare($sql);
    $q->execute($args);
    return $q->fetchColumn();
}
function stamp(): string
{
    return date("Y-m-d\TH:i:sP");
}
function txt(
    mixed $value,
    int $max,
    string $label,
    bool $required = false,
): string {
    if (!is_scalar($value) && $value !== null) {
        fail("Invalid " . $label . ".");
    }
    $v = trim((string) $value);
    if (mb_strlen($v) > $max || ($required && $v === "")) {
        fail("Check " . $label . " (maximum " . $max . " characters).");
    }
    return $v;
}
function digits(mixed $v): string
{
    return preg_replace("/[^0-9]/", "", txt($v, 100, "number"));
}
function phone(mixed $v, bool $mobileOnly = false): string
{
    $s = digits($v);
    if (str_starts_with($s, "0092") && strlen($s) === 14) {
        $s = "0" . substr($s, 4);
    } elseif (str_starts_with($s, "92") && strlen($s) === 12) {
        $s = "0" . substr($s, 2);
    }
    if ($mobileOnly && !preg_match('/^03[0-9]{9}$/', $s)) {
        fail("Enter Pakistani mobile: 03XXXXXXXXX or +923XXXXXXXXX.");
    }
    if (!$mobileOnly && (strlen($s) < 6 || strlen($s) > 18)) {
        fail("Phone number must have 6–18 digits.");
    }
    return $s;
}
function prefix(string $term): string
{
    $s = digits($term);
    if (str_starts_with($s, "0092")) {
        return "0" . substr($s, 4);
    }
    if (str_starts_with($s, "92")) {
        return "0" . substr($s, 2);
    }
    return $s;
}
function intv(mixed $v, int $min = 0, int $max = PHP_INT_MAX): int
{
    if (filter_var($v, FILTER_VALIDATE_INT) === false) {
        fail("Invalid numeric value.");
    }
    $n = (int) $v;
    if ($n < $min || $n > $max) {
        fail("Numeric value outside allowed range.");
    }
    return $n;
}
function token(mixed $v): string
{
    $s = txt($v, 100, "request token");
    if (!preg_match('/^[a-zA-Z0-9-]{16,100}$/', $s)) {
        fail("Please refresh and try again.");
    }
    return $s;
}
function jsons(mixed $x): string
{
    return json_encode(
        $x,
        JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR,
    );
}
function audit(
    string $staff,
    string $action,
    string $entity,
    int $id,
    mixed $before = null,
    mixed $after = null,
): void {
    execute(
        "INSERT INTO change_log(at,staff,action,entity,record_id,before_json,after_json) VALUES(?,?,?,?,?,?,?)",
        [
            stamp(),
            $staff,
            $action,
            $entity,
            $id,
            $before === null ? null : jsons($before),
            $after === null ? null : jsons($after),
        ],
    );
}
function trans(callable $f): mixed
{
    db()->beginTransaction();
    try {
        $r = $f();
        db()->commit();
        return $r;
    } catch (Throwable $e) {
        if (db()->inTransaction()) {
            db()->rollBack();
        }
        throw $e;
    }
}
function locked(string $name, callable $f): mixed
{
    $key =
        "mmi_" . substr(hash("sha256", conf()["db_name"] . "_" . $name), 0, 45);
    if ((int) scalar("SELECT GET_LOCK(?,10)", [$key]) !== 1) {
        fail("Office database busy. Please retry.", 503);
    }
    try {
        return $f();
    } finally {
        scalar("SELECT RELEASE_LOCK(?)", [$key]);
    }
}
function is_installed(): bool
{
    try {
        return (int) scalar("SELECT COUNT(*) FROM users") > 0;
    } catch (PDOException $e) {
        if (in_array($e->getCode(), ["42S02", "42S22"], true)) {
            return false;
        }
        throw $e;
    }
}
function settings_get(string $key, string $default = ""): string
{
    return (string) (scalar("SELECT value FROM settings WHERE setting_key=?", [
        $key,
    ]) ?:
    $default);
}
function settings_put(string $key, string $value): void
{
    execute(
        "INSERT INTO settings(setting_key,value) VALUES(?,?) ON DUPLICATE KEY UPDATE value=VALUES(value)",
        [$key, $value],
    );
}
function request_guard(bool $post = false): void
{
    $c = conf();
    $u = parse_url(rtrim($c["app_url"], "/"));
    $host = strtolower($_SERVER["HTTP_HOST"] ?? "");
    $expected = strtolower(
        ($u["host"] ?? "") . (isset($u["port"]) ? ":" . $u["port"] : ""),
    );
    if (!$expected || $host !== $expected) {
        fail("Untrusted request host.", 403);
    }
    $https = !empty($_SERVER["HTTPS"]) && $_SERVER["HTTPS"] !== "off";
    if (($u["scheme"] ?? "") !== "https" && !($c["allow_http"] ?? false)) {
        fail("Configure an HTTPS application URL.", 503);
    }
    if (!$https && !($c["allow_http"] ?? false)) {
        fail("Please use HTTPS.", 403);
    }
    $origin = $_SERVER["HTTP_ORIGIN"] ?? "";
    $allowed = ($u["scheme"] ?? "https") . "://" . $expected;
    if ($origin !== "" && $origin !== $allowed) {
        fail("Untrusted request origin.", 403);
    }
    if ($post && ($_SERVER["HTTP_X_MMI"] ?? "") !== "1") {
        fail("Invalid request.", 403);
    }
}
function cookie_path(): string
{
    $p = parse_url(conf()["app_url"], PHP_URL_PATH) ?: "";
    return rtrim($p, "/") . "/";
}
function set_auth_cookie(string $value, int $expires): void
{
    setcookie("mmi", $value, [
        "expires" => $expires,
        "path" => cookie_path(),
        "secure" => str_starts_with(conf()["app_url"], "https://"),
        "httponly" => true,
        "samesite" => "Strict",
    ]);
}
function session_user(bool $touch = true): ?array
{
    $raw = $_COOKIE["mmi"] ?? "";
    if (!is_string($raw) || !preg_match('/^[a-f0-9]{64}$/', $raw)) {
        return null;
    }
    $s = one(
        "SELECT s.*,u.name,u.role,u.active,u.auth_version current_version FROM sessions_log s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?",
        [hash("sha256", $raw)],
    );
    if (!$s || $s["logout_at"] || $s["end_reason"]) {
        return null;
    }
    if (!$s["active"] || $s["auth_version"] !== $s["current_version"]) {
        execute(
            "UPDATE sessions_log SET end_reason='Access revoked' WHERE id=?",
            [$s["id"]],
        );
        return null;
    }
    if ((int) $s["expires"] < time() || time() - (int) $s["activity"] > 1800) {
        execute(
            "UPDATE sessions_log SET end_reason='Session expired' WHERE id=?",
            [$s["id"]],
        );
        return null;
    }
    if ($touch) {
        execute("UPDATE sessions_log SET last_seen=?,activity=? WHERE id=?", [
            stamp(),
            time(),
            $s["id"],
        ]);
    }
    $prev = one(
        "SELECT login_at,logout_at,last_seen,end_reason FROM sessions_log WHERE user_id=? AND id<>? ORDER BY id DESC LIMIT 1",
        [$s["user_id"], $s["id"]],
    );
    return [
        "id" => (int) $s["user_id"],
        "username" => $s["username"],
        "name" => $s["name"],
        "role" => $s["role"],
        "login_at" => $s["login_at"],
        "previous_login" => $prev,
        "_session_id" => (int) $s["id"],
    ];
}
function need_user(): array
{
    $u = session_user(($_GET["route"] ?? "") !== "health");
    if (!$u) {
        fail("Please sign in.", 401);
    }
    return $u;
}
function admin(array $u): void
{
    if ($u["role"] !== "admin") {
        fail("Administrator access required.", 403);
    }
}
function password_check(string $p): void
{
    if (strlen($p) < 10 || strlen($p) > 72) {
        fail("Choose a password of 10–72 bytes.");
    }
}
function establish_login(array $user): array
{
    $raw = bin2hex(random_bytes(32));
    $at = stamp();
    execute(
        "INSERT INTO sessions_log(user_id,username,token_hash,auth_version,login_at,last_seen,expires,activity) VALUES(?,?,?,?,?,?,?,?)",
        [
            $user["id"],
            $user["username"],
            hash("sha256", $raw),
            $user["auth_version"],
            $at,
            $at,
            time() + 43200,
            time(),
        ],
    );
    set_auth_cookie($raw, time() + 43200);
    return ["ok" => true];
}
function login(array $d, bool $setup = false): array
{
    $name = strtolower(txt($d["username"] ?? "", 40, "login ID", true));
    $p = (string) ($d["password"] ?? "");
    if (strlen($p) > 72) {
        fail("Incorrect login ID or password.", 403);
    }
    $key = hash("sha256", ($_SERVER["REMOTE_ADDR"] ?? "") . "|" . $name);
    $attempt = one("SELECT * FROM login_attempts WHERE attempt_key=?", [$key]);
    if (
        $attempt &&
        $attempt["failures"] >= 8 &&
        time() - (int) $attempt["window_start"] < 300
    ) {
        fail("Too many attempts. Wait five minutes.", 429);
    }
    $user = one("SELECT * FROM users WHERE username=? AND active=1", [$name]);
    $hash =
        $user["password_hash"] ??
        '$2y$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2uheWG/igi';
    $valid = password_verify($p, $hash);
    if (!$user || !$valid) {
        execute(
            "INSERT INTO login_attempts(attempt_key,failures,window_start) VALUES(?,1,?) ON DUPLICATE KEY UPDATE failures=IF(window_start < ?,1,failures+1),window_start=IF(window_start < ?,VALUES(window_start),window_start)",
            [$key, time(), time() - 300, time() - 300],
        );
        fail("Incorrect login ID or password.", 403);
    }
    execute("DELETE FROM login_attempts WHERE attempt_key=?", [$key]);
    return establish_login($user);
}
function install(array $d): array
{
    $key = conf()["install_key"] ?? "";
    if (
        strlen($key) < 24 ||
        str_starts_with($key, "CHANGE_") ||
        !hash_equals($key, (string) ($d["install_key"] ?? ""))
    ) {
        fail("Enter the installation key from your private config.php.", 403);
    }
    return locked("install", function () use ($d) {
        if (is_installed()) {
            fail("Already installed. Use your existing admin login.");
        }
        $name = strtolower(txt($d["username"] ?? "", 40, "login ID", true));
        $p = (string) ($d["password"] ?? "");
        password_check($p);
        if (!preg_match('/^[a-z0-9_.-]{3,40}$/', $name)) {
            fail("Login ID must use 3–40 letters/digits/dot/dash/underscore.");
        }
        $sql = file_get_contents(__DIR__ . "/schema.sql");
        foreach (explode(";", $sql) as $query) {
            if (trim($query) !== "") {
                db()->exec($query);
            }
        }
        if (is_installed()) {
            fail("Already installed.");
        }
        trans(function () use ($name, $p) {
            execute(
                "INSERT INTO users(username,name,role,password_hash) VALUES(?,?,?,?)",
                [
                    $name,
                    "Administrator",
                    "admin",
                    password_hash($p, PASSWORD_DEFAULT),
                ],
            );
            settings_put("installed_at", stamp());
        });
        $r = establish_login(
            one("SELECT * FROM users WHERE username=?", [$name]),
        );
        return $r;
    });
}
