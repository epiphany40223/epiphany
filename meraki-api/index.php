<?php

# File where the validator and secret are
$file = "/home/jeff/ecc-meraki-data/api-secret.php";

$sqlite_file = "/home/jeff/ecc-meraki-data/data.sqlite3";

##########################################################################

function logme($str)
{
    $fp = fopen("/home/jeff/ecc-meraki-data/log.txt", "a");
    fprintf($fp, date("Y-m-d H:i:s: ", time()) . $str . "\n");
    fclose($fp);
}

function my_die($msg)
{
    # Die with a non-200 error code
    http_response_code(400);

    logme($msg);
    die($msg);
}

##########################################################################

function do_get()
{
    global $validator;

    print($validator);
    logme("Validated");
    exit(0);
}

##########################################################################

function create_sqlite_table()
{
    global $sqlite_file;
    if (is_file($sqlite_file)) {
        return;
    }

    $db = new SQLite3($sqlite_file);
    if (!$db) {
        my_die("Error: unable to write to sqlite table\n");
    }

    $str = "CREATE TABLE IF NOT EXISTS data (id integer primary key, timestamp int, apMac text, clientMac text, ipv4 text, ipv6 text, seenTime text, seenEpoch int, ssid text, rssi text, manufacturer text, os text, location_lat int, location_lng int, location_unc int)";
    if (!$db->query($query)) {
        my_die("Failed to create SQLite table");
        logme("Created SQLite table");
    }
    $db->close();
}

function log_json($apMac, $data)
{
    global $sqlite_file;
    if (!is_file($sqlite_file)) {
        my_die("Error: sqlite database does not exist");
    }

    $db = new SQLite3($sqlite_file);
    if (!$db) {
        my_die("Error: unable to write to sqlite table\n");
    }
    $db->busyTimeout(5000);
    // WAL mode has better control over concurrency.
    // Source: https://www.sqlite.org/wal.html
    $db->exec('PRAGMA journal_mode = wal;');

    # ID will auto-increment if not specified
    $str = "INSERT INTO data (timestamp, apMac, clientMac, ipv4, ipv6, seenTime, seenEpoch, ssid, rssi, manufacturer, os, location_lat, location_lng, location_unc) VALUES (" .
        time() . ',"' .
        $apMac . '","' .
        $data->{"clientMac"} . '","' .
        $data->{"ipv4"} . '","' .
        $data->{"ipv6"} . '","' .
        $data->{"seenTime"} . '",' .
        $data->{"seenEpoch"} . ',"' .
        $data->{"ssid"} . '",' .
        $data->{"rssi"} . ',"' .
        $data->{"manufacturer"} . '","' .
        $data->{"os"} . '",' .
        $data->{"location"}->{"lat"} . ',' .
        $data->{"location"}->{"lng"} . ',' .
        $data->{"location"}->{"unc"} .
        ")";
    logme("SQL string: $str");
    if (!$db->query($str)) {
        my_die("Failed to insert to SQLite table");
    }

    $db->close();
}

function do_post($raw_json)
{
    $json = json_decode($raw_json);
    if (json_last_error() != JSON_ERROR_NONE) {
        my_die("Got invalid JSON");
    }

    logme("decoded json: " . print_r($json, true));

    if (!isset($json->{"version"}) ||
        $json->{"version"} != "2.0") {
        my_die("Got non-2.0 data; discarding");
    }

    global $secret;
    if (!isset($json->{"secret"}) ||
        $json->{"secret"} != $secret) {
        my_die("Got invalid secret; discarding");
    }

    if ($json->{"type"} == "DevicesSeen") {
        create_sqlite_table();

        foreach ($json->{"data"}->{"observations"} as $k => $v) {
            log_json($json->{"data"}->{"apMac"}, $v);
        }
    }

    exit(0);
}

##########################################################################
# Main
##########################################################################

if (!is_file($file)) {
    my_die("Cannot open config file");
}
require($file);

#logme("POST is: " . print_r($_POST, true));
#logme("GET is: " . print_r($_GET, true));
#logme("GLOBALS is: " . print_r($GLOBALS, true));
#logme("SERVER is: " . print_r($_SERVER, true));
#logme("REQUEST is: " . print_r($_REQUEST, true));

# If this is a GET, print the validator
$postdata = file_get_contents("php://input");
if ($postdata != "") {
    do_post($postdata);
} else {
    do_get();
}
