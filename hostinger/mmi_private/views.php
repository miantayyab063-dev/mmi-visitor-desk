<?php
declare(strict_types=1);
function page_number(): int
{
    return intv($_GET["page"] ?? 1, 1, 1000000);
}
function get_query(string $name, int $max = 100): string
{
    return txt($_GET[$name] ?? "", $max, $name);
}
function numeric_term(string $s): string
{
    if ($s !== "" && preg_match('/^[+0-9 ()-]+$/', $s)) {
        return prefix($s);
    }
    return $s;
}
function search_visitors(): array
{
    $term = get_query("q");
    $mode = get_query("mode") ?: "auto";
    $page = page_number();
    if ($term === "") {
        return isset($_GET["paged"]) ? ["rows" => [], "total" => 0] : [];
    }
    $n = prefix($term);
    if ($mode === "phone") {
        $where = "mobile LIKE ?";
        $args = [$n !== "" ? $n . "%" : "no-match"];
    } elseif ($mode === "cnic") {
        $where = "cnic LIKE ?";
        $args = [$n !== "" ? $n . "%" : "no-match"];
    } elseif (preg_match('/^[+0-9 ()-]+$/', $term)) {
        $where = strlen($n) > 11 ? "cnic LIKE ?" : "mobile LIKE ?";
        $args = [$n . "%"];
    } else {
        $where = "LOCATE(LOWER(?),LOWER(name))>0";
        $args = [$term];
    }
    $count = (int) scalar(
        "SELECT COUNT(*) FROM visitors WHERE " . $where,
        $args,
    );
    $offset = ($page - 1) * 30;
    $found = rows(
        "SELECT * FROM visitors WHERE " .
            $where .
            " ORDER BY mobile,id LIMIT 30 OFFSET " .
            $offset,
        $args,
    );
    foreach ($found as &$v) {
        $v["visits"] = (int) scalar(
            "SELECT COUNT(*) FROM visits WHERE visitor_id=?",
            [$v["id"]],
        );
        $last = one(
            "SELECT id,at,out_at,host,purpose,remarks,staff FROM visits WHERE visitor_id=? ORDER BY id DESC LIMIT 1",
            [$v["id"]],
        );
        $v["last_visit"] = $last["at"] ?? null;
        $v["last_details"] = $last;
    }
    unset($v);
    return isset($_GET["paged"])
        ? ["rows" => $found, "total" => $count]
        : $found;
}
function search_callers(): array
{
    $term = get_query("q");
    $mode = get_query("mode") ?: "phone";
    $page = page_number();
    if ($term === "") {
        return ["rows" => [], "total" => 0];
    }
    $source =
        "(SELECT phone,caller FROM calls c1 WHERE c1.id=(SELECT MAX(c2.id) FROM calls c2 WHERE c2.phone=c1.phone) UNION ALL SELECT mobile AS phone,name AS caller FROM visitors v WHERE NOT EXISTS (SELECT 1 FROM calls c WHERE c.phone=v.mobile)) AS directory";
    $n = prefix($term);
    $where =
        $mode === "phone" ? "phone LIKE ?" : "LOCATE(LOWER(?),LOWER(caller))>0";
    $args = [$mode === "phone" ? ($n !== "" ? $n . "%" : "no-match") : $term];
    $total = (int) scalar(
        "SELECT COUNT(*) FROM " . $source . " WHERE " . $where,
        $args,
    );
    $found = rows(
        "SELECT phone,caller FROM " .
            $source .
            " WHERE " .
            $where .
            " ORDER BY phone LIMIT 30 OFFSET " .
            ($page - 1) * 30,
        $args,
    );
    foreach ($found as &$r) {
        $r["last_details"] = one(
            "SELECT at,remarks,kind,spoken_by,staff FROM calls WHERE phone=? ORDER BY id DESC LIMIT 1",
            [$r["phone"]],
        );
    }
    unset($r);
    return ["rows" => $found, "total" => $total];
}
function visit_filter(): array
{
    $term = numeric_term(get_query("q"));
    $day = get_query("date", 10);
    $vid = get_query("visitor", 20);
    if ($vid !== "" && !ctype_digit($vid)) {
        fail("Invalid visitor filter.");
    }
    $where =
        " WHERE (?='' OR t.at LIKE ?) AND (?='' OR LOCATE(LOWER(?),LOWER(v.name))>0 OR LOCATE(?,v.mobile)>0 OR LOCATE(?,v.cnic)>0 OR v.id IN (SELECT h.visitor_id FROM visits h WHERE LOCATE(LOWER(?),LOWER(h.snapshot_name))>0 OR LOCATE(?,h.snapshot_mobile)>0 OR LOCATE(?,h.snapshot_cnic)>0)) AND (?='' OR v.id=?)";
    return [
        $where,
        [
            $day,
            $day . "%",
            $term,
            $term,
            $term,
            $term,
            $term,
            $term,
            $term,
            $vid,
            $vid ?: 0,
        ],
    ];
}
function visit_select(): string
{
    return "SELECT t.id,t.visitor_id,t.snapshot_name AS name,t.snapshot_mobile AS mobile,t.snapshot_cnic AS cnic,t.at,t.purpose,t.out_at,t.host,t.staff,t.remarks,t.out_by,t.updated_at,t.updated_by,t.version FROM visits t JOIN visitors v ON v.id=t.visitor_id";
}
function visit_headers(): array
{
    return [
        "Visit ID",
        "Visitor ID",
        "Name",
        "Mobile",
        "CNIC",
        "IN (PKT)",
        "Purpose",
        "OUT (PKT)",
        "Meeting with",
        "Saved by",
        "Remarks",
        "OUT by",
        "Updated at",
        "Updated by",
        "Version",
    ];
}
function list_visits(): array
{
    [$where, $args] = visit_filter();
    $count = (int) scalar(
        "SELECT COUNT(*) FROM visits t JOIN visitors v ON v.id=t.visitor_id" .
            $where,
        $args,
    );
    $rows = rows(
        visit_select() .
            $where .
            " ORDER BY t.id DESC LIMIT 30 OFFSET " .
            (page_number() - 1) * 30,
        $args,
    );
    return [
        "rows" => $rows,
        "total" => $count,
        "stats" => [
            "today" => (int) scalar(
                "SELECT COUNT(*) FROM visits WHERE at LIKE ?",
                [date("Y-m-d") . "%"],
            ),
            "people" => (int) scalar("SELECT COUNT(*) FROM visitors"),
            "visits" => (int) scalar("SELECT COUNT(*) FROM visits"),
            "inside" => (int) scalar(
                "SELECT COUNT(*) FROM visits WHERE out_at IS NULL AND staff<>''",
            ),
        ],
    ];
}
function call_filter(): array
{
    $term = numeric_term(get_query("q"));
    $day = get_query("date", 10);
    $where =
        " WHERE (?='' OR LOCATE(?,phone)>0 OR LOCATE(LOWER(?),LOWER(caller))>0 OR LOCATE(LOWER(?),LOWER(remarks))>0 OR LOCATE(LOWER(?),LOWER(spoken_by))>0 OR LOCATE(LOWER(?),LOWER(staff))>0) AND (?='' OR at LIKE ?)";
    return [
        $where,
        [$term, $term, $term, $term, $term, $term, $day, $day . "%"],
    ];
}
function call_select(): string
{
    return "SELECT id,phone,caller,at,duration,spoken_by,kind,remarks,created_at,staff,updated_at,updated_by,version FROM calls";
}
function call_headers(): array
{
    return [
        "Call ID",
        "Phone",
        "Caller",
        "Call time (PKT)",
        "Duration (seconds)",
        "Handled by",
        "Type",
        "Remarks",
        "Saved at (PKT)",
        "Saved by",
        "Updated at",
        "Updated by",
        "Version",
    ];
}
function list_calls(): array
{
    [$where, $args] = call_filter();
    $count = (int) scalar("SELECT COUNT(*) FROM calls" . $where, $args);
    $size = isset($_GET["paged"]) ? 30 : 500;
    $rows = rows(
        call_select() .
            $where .
            " ORDER BY at DESC,id DESC LIMIT " .
            $size .
            " OFFSET " .
            (page_number() - 1) * $size,
        $args,
    );
    return isset($_GET["paged"]) ? ["rows" => $rows, "total" => $count] : $rows;
}
function csv_data(array $headers, array $records): string
{
    $f = fopen("php://temp", "r+");
    fwrite($f, "\xEF\xBB\xBF");
    fputcsv($f, $headers, ",", '"', "");
    foreach ($records as $row) {
        $values = [];
        foreach ($row as $v) {
            if (is_string($v) && preg_match('/^[=+@\-\t\r\n]/', $v)) {
                $v = "'" . $v;
            }
            $values[] = $v;
        }
        fputcsv($f, $values, ",", '"', "");
    }
    rewind($f);
    $s = stream_get_contents($f);
    fclose($f);
    return $s;
}
function report_html(
    string $title,
    array $headers,
    array $records,
    array $u,
): string {
    $e = fn($s) => htmlspecialchars(
        (string) ($s ?? ""),
        ENT_QUOTES | ENT_SUBSTITUTE,
        "UTF-8",
    );
    $html =
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>' .
        $e($title) .
        '</title><link rel="stylesheet" href="assets/style.css"><body class="printView"><h1>' .
        $e($title) .
        "</h1><p>Generated " .
        $e(stamp()) .
        " · " .
        $e($u["username"]) .
        " · " .
        count($records) .
        ' records</p><button id="printNow">Print / Save PDF</button><table><thead><tr>';
    foreach ($headers as $h) {
        $html .= "<th>" . $e($h) . "</th>";
    }
    $html .= "</tr></thead><tbody>";
    foreach ($records as $row) {
        $html .= "<tr>";
        foreach ($row as $v) {
            $html .= "<td>" . $e($v) . "</td>";
        }
        $html .= "</tr>";
    }
    $html .=
        '</tbody></table><p class="print-credit">Developed by mianmuhamamdtayyab</p><script src="assets/print.js"></script></body></html>';
    return $html;
}
