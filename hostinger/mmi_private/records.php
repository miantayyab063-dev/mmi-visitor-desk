<?php
declare(strict_types=1);
function visitor_values(array $d): array
{
    $n = txt($d["name"] ?? "", 100, "name", true);
    if (mb_strlen($n) < 2) {
        fail("Name must contain at least two characters.");
    }
    $m = phone($d["mobile"] ?? "", true);
    $cn = digits($d["cnic"] ?? "");
    if (strlen($cn) !== 13) {
        fail("CNIC must contain 13 digits.");
    }
    return [$n, $m, $cn];
}
function save_visit(array $d, array $u): array
{
    [$n, $m, $cn] = visitor_values($d);
    $host = txt($d["host"] ?? "", 150, "meeting person");
    $purpose = txt($d["purpose"] ?? "", 500, "purpose");
    $remarks = txt($d["remarks"] ?? "", 4000, "remarks");
    $tok = token($d["token"] ?? "");
    return locked(
        "visits",
        fn() => trans(function () use (
            $d,
            $u,
            $n,
            $m,
            $cn,
            $host,
            $purpose,
            $remarks,
            $tok,
        ) {
            $existing = one("SELECT id FROM visits WHERE token=?", [$tok]);
            if ($existing) {
                return [
                    "message" => "Visit already saved.",
                    "id" => $existing["id"],
                ];
            }
            $selected = (int) ($d["visitor_id"] ?? 0);
            if ($selected) {
                $v = one("SELECT * FROM visitors WHERE id=? FOR UPDATE", [
                    $selected,
                ]);
                if (!$v) {
                    fail("Selected visitor not found.");
                }
                if (
                    (int) ($d["profile_version"] ?? 0) !== (int) $v["version"]
                ) {
                    fail(
                        "Visitor changed elsewhere. Search and select again.",
                        409,
                    );
                }
                if (
                    one(
                        "SELECT id FROM visitors WHERE id<>? AND (mobile=? OR cnic=?)",
                        [$selected, $m, $cn],
                    )
                ) {
                    fail("Mobile or CNIC belongs to another visitor.");
                }
                $vid = (int) $v["id"];
                if ([$v["name"], $v["mobile"], $v["cnic"]] !== [$n, $m, $cn]) {
                    execute(
                        "UPDATE visitors SET name=?,mobile=?,cnic=?,version=version+1 WHERE id=?",
                        [$n, $m, $cn, $vid],
                    );
                    audit(
                        $u["username"],
                        "Profile updated with new visit",
                        "visitor",
                        $vid,
                        $v,
                        one("SELECT * FROM visitors WHERE id=?", [$vid]),
                    );
                }
            } else {
                $found = rows(
                    "SELECT * FROM visitors WHERE mobile=? OR cnic=? FOR UPDATE",
                    [$m, $cn],
                );
                if ($found) {
                    if (
                        count($found) > 1 ||
                        $found[0]["mobile"] !== $m ||
                        $found[0]["cnic"] !== $cn
                    ) {
                        fail(
                            "Mobile/CNIC conflict. Select the correct saved visitor.",
                        );
                    }
                    $v = $found[0];
                    $vid = (int) $v["id"];
                    if (mb_strtolower($v["name"]) !== mb_strtolower($n)) {
                        fail(
                            "Select this saved visitor before changing the name.",
                        );
                    }
                } else {
                    execute(
                        "INSERT INTO visitors(name,mobile,cnic) VALUES(?,?,?)",
                        [$n, $m, $cn],
                    );
                    $vid = (int) db()->lastInsertId();
                    audit(
                        $u["username"],
                        "Profile created",
                        "visitor",
                        $vid,
                        null,
                        ["name" => $n, "mobile" => $m, "cnic" => $cn],
                    );
                }
            }
            if (
                one(
                    "SELECT id FROM visits WHERE visitor_id=? AND out_at IS NULL AND staff<>''",
                    [$vid],
                )
            ) {
                fail("Visitor already IN. Mark the open visit OUT first.");
            }
            $at = stamp();
            execute(
                "INSERT INTO visits(visitor_id,at,host,purpose,remarks,staff,snapshot_name,snapshot_mobile,snapshot_cnic,token) VALUES(?,?,?,?,?,?,?,?,?,?)",
                [
                    $vid,
                    $at,
                    $host,
                    $purpose,
                    $remarks,
                    $u["username"],
                    $n,
                    $m,
                    $cn,
                    $tok,
                ],
            );
            $id = (int) db()->lastInsertId();
            audit(
                $u["username"],
                "IN",
                "visit",
                $id,
                null,
                one("SELECT * FROM visits WHERE id=?", [$id]),
            );
            return ["message" => "Visitor IN saved.", "id" => $id, "at" => $at];
        }),
    );
}
function visitor_out(array $d, array $u): array
{
    return trans(function () use ($d, $u) {
        $id = intv($d["id"] ?? 0, 1);
        $old = one("SELECT * FROM visits WHERE id=? FOR UPDATE", [$id]);
        if (!$old) {
            fail("Visit not found.");
        }
        if ($old["staff"] === "") {
            fail("Historical visit: exact OUT time was not recorded.");
        }
        if (!$old["out_at"]) {
            execute(
                "UPDATE visits SET out_at=?,out_by=?,version=version+1 WHERE id=?",
                [stamp(), $u["username"], $id],
            );
            audit(
                $u["username"],
                "OUT",
                "visit",
                $id,
                $old,
                one("SELECT * FROM visits WHERE id=?", [$id]),
            );
        }
        return ["message" => "Visitor marked OUT."];
    });
}
function edit_profile(array $d, array $u): array
{
    [$n, $m, $cn] = visitor_values($d);
    $reason = txt($d["reason"] ?? "", 500, "reason", true);
    if (mb_strlen($reason) < 3) {
        fail("Add a correction reason.");
    }
    return locked(
        "visits",
        fn() => trans(function () use ($d, $u, $n, $m, $cn, $reason) {
            $id = intv($d["id"] ?? 0, 1);
            $old = one("SELECT * FROM visitors WHERE id=? FOR UPDATE", [$id]);
            if (!$old) {
                fail("Visitor not found.");
            }
            if ((int) $old["version"] !== (int) ($d["version"] ?? 0)) {
                fail("Profile changed elsewhere. Search/select again.", 409);
            }
            if (
                one(
                    "SELECT id FROM visitors WHERE id<>? AND (mobile=? OR cnic=?)",
                    [$id, $m, $cn],
                )
            ) {
                fail("Mobile or CNIC belongs to another visitor.");
            }
            execute(
                "UPDATE visitors SET name=?,mobile=?,cnic=?,version=version+1 WHERE id=?",
                [$n, $m, $cn, $id],
            );
            audit(
                $u["username"],
                "Profile corrected: " . $reason,
                "visitor",
                $id,
                $old,
                one("SELECT * FROM visitors WHERE id=?", [$id]),
            );
            return [
                "message" =>
                    "Profile corrected. Old visit identities preserved.",
            ];
        }),
    );
}
function edit_visit(array $d, array $u): array
{
    $host = txt($d["host"] ?? "", 150, "meeting person");
    $purpose = txt($d["purpose"] ?? "", 500, "purpose");
    $remarks = txt($d["remarks"] ?? "", 4000, "remarks");
    $reason = txt($d["reason"] ?? "", 500, "reason", true);
    if (mb_strlen($reason) < 3) {
        fail("Add a correction reason.");
    }
    return trans(function () use ($d, $u, $host, $purpose, $remarks, $reason) {
        $id = intv($d["id"] ?? 0, 1);
        $old = one("SELECT * FROM visits WHERE id=? FOR UPDATE", [$id]);
        if (!$old) {
            fail("Visit not found.");
        }
        if ((int) $old["version"] !== (int) ($d["version"] ?? 0)) {
            fail("Visit changed elsewhere. Reload before editing.", 409);
        }
        execute(
            "UPDATE visits SET host=?,purpose=?,remarks=?,updated_at=?,updated_by=?,version=version+1 WHERE id=?",
            [$host, $purpose, $remarks, stamp(), $u["username"], $id],
        );
        audit(
            $u["username"],
            "Visit corrected: " . $reason,
            "visit",
            $id,
            $old,
            one("SELECT * FROM visits WHERE id=?", [$id]),
        );
        return ["message" => "Visit correction saved."];
    });
}
function call_values(array $d): array
{
    $p = phone($d["phone"] ?? "");
    $caller = txt($d["caller"] ?? "", 100, "caller");
    $remarks = txt($d["remarks"] ?? "", 4000, "remarks");
    $spoken = txt($d["spoken_by"] ?? "", 100, "handled by", true);
    $kind = txt($d["kind"] ?? "Incoming", 20, "call type");
    if (!in_array($kind, ["Incoming", "Outgoing", "Callback"], true)) {
        fail("Invalid call type.");
    }
    $duration = intv($d["duration"] ?? 0, 0, 604800);
    $input = txt($d["at"] ?? "", 35, "call time", true);
    if (
        !preg_match(
            '/^\d{4}-\d\d-\d\dT\d\d:\d\d(:\d\d)?([+-]\d\d:\d\d|Z)?$/',
            $input,
        )
    ) {
        fail("Invalid call start time.");
    }
    try {
        $date = new DateTimeImmutable($input, new DateTimeZone("Asia/Karachi"));
        $err = DateTimeImmutable::getLastErrors();
        if ($err && ($err["warning_count"] || $err["error_count"])) {
            fail("Invalid calendar date.");
        }
        $at = $date
            ->setTimezone(new DateTimeZone("Asia/Karachi"))
            ->format("Y-m-d\TH:i:sP");
    } catch (Exception) {
        fail("Invalid call time.");
    }
    return [$p, $caller, $at, $duration, $remarks, $spoken, $kind];
}
function save_call(array $d, array $u, bool $edit = false): array
{
    $v = call_values($d);
    $tok = token($d["token"] ?? "");
    return locked(
        "calls",
        fn() => trans(function () use ($d, $u, $edit, $v, $tok) {
            [$p, $caller, $at, $duration, $remarks, $spoken, $kind] = $v;
            if ($edit) {
                $id = intv($d["id"] ?? 0, 1);
                $old = one("SELECT * FROM calls WHERE id=? FOR UPDATE", [$id]);
                if (!$old) {
                    fail("Call not found.");
                }
                if ((int) $old["version"] !== (int) ($d["version"] ?? 0)) {
                    fail("Call changed elsewhere. Reload history.", 409);
                }
                $reason = txt(
                    $d["reason"] ?? "",
                    500,
                    "correction reason",
                    true,
                );
                if (mb_strlen($reason) < 3) {
                    fail("Add a correction reason.");
                }
                execute(
                    "UPDATE calls SET phone=?,caller=?,at=?,duration=?,remarks=?,spoken_by=?,kind=?,updated_at=?,updated_by=?,version=version+1 WHERE id=?",
                    [
                        $p,
                        $caller,
                        $at,
                        $duration,
                        $remarks,
                        $spoken,
                        $kind,
                        stamp(),
                        $u["username"],
                        $id,
                    ],
                );
                audit(
                    $u["username"],
                    "Call corrected: " . $reason,
                    "call",
                    $id,
                    $old,
                    one("SELECT * FROM calls WHERE id=?", [$id]),
                );
            } else {
                if (one("SELECT id FROM calls WHERE token=?", [$tok])) {
                    return ["message" => "Call already saved."];
                }
                execute(
                    "INSERT INTO calls(phone,caller,at,duration,remarks,spoken_by,kind,created_at,staff,token) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    [
                        $p,
                        $caller,
                        $at,
                        $duration,
                        $remarks,
                        $spoken,
                        $kind,
                        stamp(),
                        $u["username"],
                        $tok,
                    ],
                );
                $id = (int) db()->lastInsertId();
                audit(
                    $u["username"],
                    "Call recorded",
                    "call",
                    $id,
                    null,
                    one("SELECT * FROM calls WHERE id=?", [$id]),
                );
            }
            return ["message" => "Call record saved."];
        }),
    );
}
function save_user(array $d, array $u): array
{
    admin($u);
    $name = strtolower(txt($d["username"] ?? "", 40, "login ID", true));
    $label = txt($d["name"] ?? "", 100, "staff name", true);
    $role = txt($d["role"] ?? "receptionist", 20, "role");
    $active = !empty($d["active"]) ? 1 : 0;
    $p = (string) ($d["password"] ?? "");
    if (
        !preg_match('/^[a-z0-9_.-]{3,40}$/', $name) ||
        !in_array($role, ["admin", "receptionist"], true)
    ) {
        fail("Invalid login ID or role.");
    }
    return locked(
        "users",
        fn() => trans(function () use (
            $d,
            $u,
            $name,
            $label,
            $role,
            $active,
            $p,
        ) {
            $old = one("SELECT * FROM users WHERE username=? FOR UPDATE", [
                $name,
            ]);
            if (
                $old &&
                (int) $old["id"] === $u["id"] &&
                (!$active || $role !== "admin")
            ) {
                fail("You cannot disable or demote your own account.");
            }
            if (!$old || $p !== "") {
                password_check($p);
            }
            if ($old) {
                $id = (int) $old["id"];
                execute("UPDATE users SET name=?,role=?,active=? WHERE id=?", [
                    $label,
                    $role,
                    $active,
                    $id,
                ]);
                if ($p !== "") {
                    execute(
                        "UPDATE users SET password_hash=?,auth_version=auth_version+1 WHERE id=?",
                        [password_hash($p, PASSWORD_DEFAULT), $id],
                    );
                    execute(
                        "UPDATE sessions_log SET end_reason='Password reset' WHERE user_id=? AND logout_at IS NULL AND end_reason IS NULL",
                        [$id],
                    );
                }
                if (!$active) {
                    execute(
                        "UPDATE sessions_log SET end_reason='Account disabled' WHERE user_id=? AND logout_at IS NULL AND end_reason IS NULL",
                        [$id],
                    );
                }
            } else {
                execute(
                    "INSERT INTO users(username,name,role,password_hash,active) VALUES(?,?,?,?,?)",
                    [
                        $name,
                        $label,
                        $role,
                        password_hash($p, PASSWORD_DEFAULT),
                        $active,
                    ],
                );
                $id = (int) db()->lastInsertId();
            }
            audit($u["username"], "Account updated", "user", $id, null, [
                "username" => $name,
                "name" => $label,
                "role" => $role,
                "active" => $active,
                "password_reset" => $p !== "",
            ]);
            return ["message" => "Login account saved."];
        }),
    );
}
