<?php
declare(strict_types=1);
ini_set("display_errors", "0");
header("Cache-Control: no-store");
header("X-Content-Type-Options: nosniff");
header("X-Frame-Options: DENY");
header(
    "Content-Security-Policy: default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'",
);
$checks = [];
$checks["PHP 8.2 or newer"] = version_compare(PHP_VERSION, "8.2.0", ">=");
foreach (["pdo_mysql", "mbstring", "zip"] as $ext) {
    $checks["PHP extension: " . $ext] = extension_loaded($ext);
}
$private = dirname(__DIR__, 2) . "/mmi_private";
$checks["Private application folder"] = is_file($private . "/core.php");
$checks["Private config.php"] = is_file($private . "/config.php");
$ready = false;
if ($checks["Private config.php"] && $checks["Private application folder"]) {
    try {
        require_once $private . "/core.php";
        db();
        $checks["MySQL connection"] = true;
        $c = conf();
        $checks["One-time installation key"] =
            strlen($c["install_key"] ?? "") >= 24 &&
            !str_starts_with($c["install_key"] ?? "", "CHANGE_");
        $checks["HTTPS application URL"] =
            str_starts_with($c["app_url"] ?? "", "https://") ||
            ($c["allow_http"] ?? false);
        $checks["Private Excel backup folder"] =
            is_dir($private . "/backups") && is_writable($private . "/backups");
        $ready = !in_array(false, $checks, true);
    } catch (Throwable) {
        $checks["MySQL connection"] = false;
    }
}
?><!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MMI · Installation check</title><link rel="stylesheet" href="assets/style.css"><body><header class="topbar"><div class="topbar-title"><span class="topbar-mark">M</span><div><strong>MMI · Hostinger installation</strong><span>Mastermind Marketing International</span></div></div></header><main><section class="card"><span class="eyebrow">INSTALLATION READINESS</span><h1>Connect your office.</h1><p>Follow START_HERE_HOSTINGER.txt first. No data is changed by this check.</p><table><thead><tr><th>Requirement</th><th>Status</th></tr></thead><tbody><?php foreach (
    $checks
    as $label => $pass
): ?><tr><td><?= htmlspecialchars(
    $label,
    ENT_QUOTES,
    "UTF-8",
) ?></td><td><?= $pass
    ? "Ready"
    : "Needs attention" ?></td></tr><?php endforeach; ?></tbody></table><p class="field-help">Database credentials belong in mmi_private/config.php, outside public_html. Enable missing PHP extensions in hPanel. Keep the one-time installation key private.</p><div class="form-actions"><a class="primary button-link" href="index.html"><?= $ready
    ? "Open MMI & create admin →"
    : "Open MMI →" ?></a><a class="secondary button-link" href="install.php">Recheck</a></div></section><footer class="app-footer"><span>MMI · Reception Workspace</span><span>Developed by <strong>mianmuhamamdtayyab</strong></span></footer></main></body></html>
