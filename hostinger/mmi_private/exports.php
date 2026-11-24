<?php
declare(strict_types=1);
function xml_text(mixed $v): string
{
    $v = preg_replace(
        '/[\x00-\x08\x0B\x0C\x0E-\x1F]/u',
        "",
        (string) ($v ?? ""),
    );
    return htmlspecialchars(
        $v,
        ENT_XML1 | ENT_QUOTES | ENT_SUBSTITUTE,
        "UTF-8",
    );
}
function xl_col(int $n): string
{
    $s = "";
    while ($n > 0) {
        $n--;
        $s = chr(65 + ($n % 26)) . $s;
        $n = intdiv($n, 26);
    }
    return $s;
}
function xlsx(array $sheets): string
{
    if (!class_exists("ZipArchive")) {
        fail("Enable the PHP zip extension for Excel backups.", 503);
    }
    $file = tempnam(sys_get_temp_dir(), "mmi-xlsx-");
    $z = new ZipArchive();
    if ($z->open($file, ZipArchive::OVERWRITE) !== true) {
        throw new RuntimeException("Cannot create Excel archive.");
    }
    try {
        $types =
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>';
        $book =
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>';
        $rels =
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">';
        $i = 0;
        foreach ($sheets as $name => $rows) {
            $i++;
            $types .=
                '<Override PartName="/xl/worksheets/sheet' .
                $i .
                '.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>';
            $book .=
                '<sheet name="' .
                xml_text($name) .
                '" sheetId="' .
                $i .
                '" r:id="rId' .
                $i .
                '"/>';
            $rels .=
                '<Relationship Id="rId' .
                $i .
                '" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet' .
                $i .
                '.xml"/>';
            $xml =
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>';
            for ($c = 1; $c <= count($rows[0]); $c++) {
                $xml .=
                    '<col min="' .
                    $c .
                    '" max="' .
                    $c .
                    '" width="25" customWidth="1"/>';
            }
            $xml .= "</cols><sheetData>";
            $n = 0;
            foreach ($rows as $row) {
                $n++;
                $xml .=
                    '<row r="' .
                    $n .
                    '" ht="' .
                    ($n === 1 ? 32 : 42) .
                    '" customHeight="1">';
                $c = 0;
                foreach ($row as $v) {
                    $c++;
                    $ref = xl_col($c) . $n;
                    $style = $n === 1 ? 1 : 2;
                    if (is_int($v) || is_float($v)) {
                        $xml .=
                            '<c r="' .
                            $ref .
                            '" s="' .
                            $style .
                            '" t="n"><v>' .
                            $v .
                            "</v></c>";
                    } else {
                        $xml .=
                            '<c r="' .
                            $ref .
                            '" s="' .
                            $style .
                            '" t="inlineStr"><is><t xml:space="preserve">' .
                            xml_text($v) .
                            "</t></is></c>";
                    }
                }
                $xml .= "</row>";
            }
            $xml .=
                '</sheetData><autoFilter ref="A1:' .
                xl_col(count($rows[0])) .
                count($rows) .
                '"/></worksheet>';
            $z->addFromString("xl/worksheets/sheet" . $i . ".xml", $xml);
        }
        $z->addFromString("[Content_Types].xml", $types . "</Types>");
        $z->addFromString(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        );
        $z->addFromString("xl/workbook.xml", $book . "</sheets></workbook>");
        $z->addFromString(
            "xl/_rels/workbook.xml.rels",
            $rels .
                '<Relationship Id="rId' .
                ($i + 1) .
                '" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        );
        $z->addFromString(
            "xl/styles.xml",
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF132238"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="3"><xf fontId="0" fillId="0" borderId="0" xfId="0"/><xf fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf><xf fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="top"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>',
        );
        $z->close();
        $result = file_get_contents($file);
        if ($result === false) {
            throw new RuntimeException("Excel output failed.");
        }
        return $result;
    } finally {
        @unlink($file);
    }
}
function export_tables(): array
{
    return trans(function () {
        return [
            "Visitors" => array_merge(
                [["Visitor ID", "Name", "Mobile", "CNIC", "Version"]],
                array_map(
                    "array_values",
                    rows(
                        "SELECT id,name,mobile,cnic,version FROM visitors ORDER BY id",
                    ),
                ),
            ),
            "Visits" => array_merge(
                [visit_headers()],
                array_map(
                    "array_values",
                    rows(visit_select() . " ORDER BY t.id"),
                ),
            ),
            "Telephone Callbacks" => array_merge(
                [call_headers()],
                array_map("array_values", rows(call_select() . " ORDER BY id")),
            ),
            "Login Activity" => array_merge(
                [
                    [
                        "Session ID",
                        "Login ID",
                        "Sign-in (PKT)",
                        "Sign-out (PKT)",
                        "Last seen (PKT)",
                        "End reason",
                    ],
                ],
                array_map(
                    "array_values",
                    rows(
                        "SELECT id,username,login_at,logout_at,last_seen,end_reason FROM sessions_log ORDER BY id",
                    ),
                ),
            ),
            "Record Change History" => array_merge(
                [
                    [
                        "Change ID",
                        "Time (PKT)",
                        "Staff",
                        "Action",
                        "Record type",
                        "Record ID",
                        "Before JSON",
                        "After JSON",
                    ],
                ],
                array_map(
                    "array_values",
                    rows(
                        "SELECT id,at,staff,action,entity,record_id,before_json,after_json FROM change_log ORDER BY id",
                    ),
                ),
            ),
        ];
    });
}
function history_tables(array $all): array
{
    return [
        "Login Logout History" => $all["Login Activity"],
        "Record Change History" => $all["Record Change History"],
    ];
}
function refresh_backups(): void
{
    $folder = __DIR__ . "/backups";
    if (!is_dir($folder) && !mkdir($folder, 0700, true)) {
        throw new RuntimeException("Backup directory not writable.");
    }
    $lock = fopen($folder . "/.backup.lock", "c");
    if (!$lock || !flock($lock, LOCK_EX)) {
        throw new RuntimeException("Cannot lock backups.");
    }
    try {
        $all = export_tables();
        foreach (
            [
                "MMI_All_Records.xlsx" => $all,
                "MMI_Login_Change_History.xlsx" => history_tables($all),
            ]
            as $name => $sheets
        ) {
            $blob = xlsx($sheets);
            $tmp = tempnam($folder, ".mmi-");
            try {
                if (file_put_contents($tmp, $blob) !== strlen($blob)) {
                    throw new RuntimeException("Backup write failed.");
                }
                @chmod($tmp, 0600);
                if (!rename($tmp, $folder . "/" . $name)) {
                    throw new RuntimeException("Backup replace failed.");
                }
            } finally {
                if (is_file($tmp)) {
                    @unlink($tmp);
                }
            }
        }
    } finally {
        flock($lock, LOCK_UN);
        fclose($lock);
    }
}
function mysql_backup(): string
{
    $tables = [
        "users",
        "visitors",
        "visits",
        "calls",
        "sessions_log",
        "change_log",
        "settings",
        "login_attempts",
    ];
    return trans(function () use ($tables) {
        $out =
            "-- MMI MySQL backup: " .
            stamp() .
            "\nSET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS=0;\n";
        foreach ($tables as $table) {
            $ddl = one("SHOW CREATE TABLE `" . $table . "`");
            $out .=
                "DROP TABLE IF EXISTS `" .
                $table .
                "`;\n" .
                array_values($ddl)[1] .
                ";\n";
            foreach (rows("SELECT * FROM `" . $table . "`") as $row) {
                $names = implode(
                    ",",
                    array_map(fn($s) => "`" . $s . "`", array_keys($row)),
                );
                $vals = implode(
                    ",",
                    array_map(
                        fn($v) => $v === null
                            ? "NULL"
                            : db()->quote((string) $v),
                        array_values($row),
                    ),
                );
                $out .=
                    "INSERT INTO `" .
                    $table .
                    "` (" .
                    $names .
                    ") VALUES (" .
                    $vals .
                    ");\n";
            }
        }
        return $out . "SET FOREIGN_KEY_CHECKS=1;\n";
    });
}
