<?php
// Copy this file to config.php in THIS private folder. Never put credentials in public_html.
return [
    "db_host" => "localhost",
    "db_port" => 3306,
    "db_name" => "CHANGE_TO_HOSTINGER_DATABASE_NAME",
    "db_user" => "CHANGE_TO_HOSTINGER_DATABASE_USER",
    "db_password" => "CHANGE_TO_DATABASE_PASSWORD",
    "app_url" => "https://YOUR-DOMAIN.COM/mmi",
    // Change to a NEW random secret of at least 24 characters. Used only for first-admin setup.
    "install_key" => "CHANGE_TO_A_RANDOM_INSTALL_SECRET_32_CHARS",
    "allow_http" => false,
];
