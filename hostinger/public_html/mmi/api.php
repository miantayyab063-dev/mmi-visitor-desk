<?php
declare(strict_types=1);
ini_set("display_errors", "0");
header("Cache-Control: no-store");
header("X-Content-Type-Options: nosniff");
header("X-Frame-Options: DENY");
header("Referrer-Policy: no-referrer");
header("Permissions-Policy: camera=(), microphone=(), geolocation=()");
header(
    "Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'",
);
function output(
    mixed $value,
    int $status = 200,
    string $type = "application/json",
    ?string $name = null,
): never {
    http_response_code($status);
    header(
        "Content-Type: " .
            $type .
            ($type === "application/json" || str_starts_with($type, "text/")
                ? "; charset=utf-8"
                : ""),
    );
    if ($name) {
        header('Content-Disposition: attachment; filename="' . $name . '"');
    }
    echo $type === "application/json"
        ? json_encode(
            $value,
            JSON_UNESCAPED_UNICODE |
                JSON_UNESCAPED_SLASHES |
                JSON_THROW_ON_ERROR,
        )
        : $value;
    exit();
}
try {
    $private = dirname(__DIR__, 2) . "/mmi_private";
    foreach (["core.php", "records.php", "views.php", "exports.php"] as $file) {
        require_once $private . "/" . $file;
    }
    $route = txt($_GET["route"] ?? "status", 40, "route");
    $method = $_SERVER["REQUEST_METHOD"];
    request_guard($method === "POST");
    if (str_starts_with(conf()["app_url"], "https://")) {
        header("Strict-Transport-Security: max-age=31536000");
    }
    if ($method === "GET") {
        if ($route === "status") {
            $installed = is_installed();
            $u = $installed ? session_user() : null;
            if ($u) {
                unset($u["_session_id"]);
            }
            output([
                "configured" => $installed,
                "loggedIn" => $u !== null,
                "user" => $u,
                "started" => $installed
                    ? settings_get("installed_at", stamp())
                    : stamp(),
                "serverTime" => stamp(),
                "upgrade" => false,
                "needs_install_key" => !$installed,
            ]);
        }
        $u = need_user();
        switch ($route) {
            case "health":
                settings_put("health_check", stamp());
                output(["ok" => true, "checked_at" => stamp()]);
            case "search":
                output(search_visitors());
            case "caller-search":
                output(search_callers());
            case "visits":
                output(list_visits());
            case "calls":
                output(list_calls());
            case "users":
                admin($u);
                output(
                    rows(
                        "SELECT id,username,name,role,active FROM users ORDER BY id",
                    ),
                );
            case "audit":
                admin($u);
                output(
                    rows(
                        "SELECT id,username,login_at,logout_at,last_seen,end_reason FROM sessions_log ORDER BY id DESC LIMIT 100",
                    ),
                );
            case "changes":
                $entity = get_query("entity", 30) ?: "visit";
                if (
                    !in_array(
                        $entity,
                        ["visitor", "visit", "call", "user"],
                        true,
                    )
                ) {
                    fail("Invalid record type.");
                }
                if ($entity === "user") {
                    admin($u);
                }
                output(
                    rows(
                        "SELECT * FROM change_log WHERE entity=? AND record_id=? ORDER BY id DESC",
                        [$entity, intv($_GET["id"] ?? 0, 1)],
                    ),
                );
            case "export":
            case "print":
                [$where, $args] = visit_filter();
                $records = rows(
                    visit_select() . $where . " ORDER BY t.id DESC",
                    $args,
                );
                if ($route === "print") {
                    output(
                        report_html(
                            "MMI — Visitor History",
                            visit_headers(),
                            $records,
                            $u,
                        ),
                        200,
                        "text/html",
                    );
                }
                output(
                    csv_data(visit_headers(), $records),
                    200,
                    "text/csv",
                    "MMI-visits.csv",
                );
            case "call-export":
            case "call-print":
                [$where, $args] = call_filter();
                $records = rows(
                    call_select() . $where . " ORDER BY at DESC,id DESC",
                    $args,
                );
                if ($route === "call-print") {
                    output(
                        report_html(
                            "MMI — Telephone & Callback History",
                            call_headers(),
                            $records,
                            $u,
                        ),
                        200,
                        "text/html",
                    );
                }
                output(
                    csv_data(call_headers(), $records),
                    200,
                    "text/csv",
                    "MMI-callback-records.csv",
                );
            case "backup":
                admin($u);
                output(
                    xlsx(export_tables()),
                    200,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "MMI_All_Records.xlsx",
                );
            case "history-backup":
                admin($u);
                output(
                    xlsx(history_tables(export_tables())),
                    200,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "MMI_Login_Change_History.xlsx",
                );
            case "database-backup":
                admin($u);
                output(
                    mysql_backup(),
                    200,
                    "application/sql",
                    "MMI_MySQL_Backup.sql",
                );
            default:
                fail("Not found.", 404);
        }
    } elseif ($method === "POST") {
        $size = (int) ($_SERVER["CONTENT_LENGTH"] ?? 0);
        if ($size < 1 || $size > 32768) {
            fail("Invalid request size.");
        }
        $object = json_decode(
            file_get_contents("php://input"),
            false,
            32,
            JSON_THROW_ON_ERROR,
        );
        if (!($object instanceof stdClass)) {
            fail("Request must be a JSON object.");
        }
        $d = get_object_vars($object);
        if ($route === "setup") {
            $result = install($d);
        } elseif ($route === "login") {
            $result = login($d);
        } else {
            $u = need_user();
            $result = match ($route) {
                "visit" => save_visit($d, $u),
                "out" => visitor_out($d, $u),
                "profile" => edit_profile($d, $u),
                "edit-visit" => edit_visit($d, $u),
                "call" => save_call($d, $u),
                "edit-call" => save_call($d, $u, true),
                "user" => save_user($d, $u),
                "logout" => (function () use ($u) {
                    execute(
                        "UPDATE sessions_log SET logout_at=?,last_seen=?,end_reason='Signed out' WHERE id=?",
                        [stamp(), stamp(), $u["_session_id"]],
                    );
                    set_auth_cookie("", time() - 3600);
                    return ["ok" => true];
                })(),
                default => throw new ApiError(404, "Not found."),
            };
        }
        try {
            refresh_backups();
        } catch (Throwable $e) {
            error_log("MMI Excel backup failed: " . $e->getMessage());
            $result["backup_warning"] =
                "Database saved, but Excel backup could not update. Ask admin to check PHP zip extension, private-folder permissions and available disk space.";
        }
        output($result);
    } else {
        header("Allow: GET, POST");
        fail("Method not allowed.", 405);
    }
} catch (Throwable $e) {
    if (function_exists("db")) {
        try {
            if (db()->inTransaction()) {
                db()->rollBack();
            }
        } catch (Throwable) {
        }
    }
    if ($e instanceof ApiError) {
        output(["error" => $e->getMessage()], $e->status);
    }
    if ($e instanceof JsonException) {
        output(["error" => "Invalid JSON request."], 400);
    }
    if ($e instanceof PDOException) {
        error_log("MMI database error: " . $e->getMessage());
        if ($e->getCode() === "23000") {
            output(
                [
                    "error" =>
                        "This mobile, CNIC or request record already exists. Search and select the saved visitor.",
                ],
                409,
            );
        }
        output(
            [
                "error" =>
                    "Database unavailable. Check private configuration and database access. Your unconfirmed entry has not been cleared.",
            ],
            503,
        );
    }
    error_log("MMI error: " . $e->getMessage());
    output(
        [
            "error" =>
                "Unable to complete this request. Ask admin to check the server error log.",
        ],
        500,
    );
}
