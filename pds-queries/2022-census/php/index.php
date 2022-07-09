<?php

// Constants

$filename = "/home/itadmin/census-2022-data/cookies.sqlite3";
$timeout = 60 * 24 * 60 * 60;
$unrecognized_key_url = "unknown.php";
$stale_key_url = "stale.php";
$error_url = "error.php";

#----------------------------------------------------------------------

# JMS Debug
#print("<pre>\n");

#----------------------------------------------------------------------

$db_handle  = new SQLite3($filename);

$cookie = $_GET['key'];
// Escape the cookie!

#----------------------------------------------------------------------

// Make sure only 1 cookie matches
$query = "SELECT COUNT(*) FROM COOKIES WHERE cookie=:cookie";
$stmt = $db_handle->prepare($query);
$stmt->bindParam(':cookie', $cookie);
$result = $stmt->execute();
$row = $result->fetchArray();
$count = $row[0];
if ($count == 0) {
    header("Location: $unrecognized_key_url");
    exit(0);
} else if ($count > 1) {
    header("Location: $error_url");
    exit(0);
}

#----------------------------------------------------------------------

# If we get here, there's only one cookie that matches in the DB.
# Get the UID corresponding to this cookie.
$query = "SELECT uid FROM COOKIES WHERE cookie=:cookie";
$stmt = $db_handle->prepare($query);
$stmt->bindParam(':cookie', $cookie);
$result = $stmt->execute();
$row = $result->fetchArray();

$uid  = $row['uid'];

#----------------------------------------------------------------------

// Get the latest URL for this UID.
$query = "SELECT url,creation_timestamp FROM COOKIES WHERE uid=:uid ORDER BY rowid DESC LIMIT 1";
$stmt = $db_handle->prepare($query);
$stmt->bindParam(':uid', intval($uid));
$result = $stmt->execute();
$row = $result->fetchArray();

$url = $row['url'];
$ts  = $row['creation_timestamp'];

// See if we're past the stale time for this URL
$g = gmmktime();
if ($g > $ts + $timeout) {
    header("Location: $stale_key_url");
    exit(0);
}

#----------------------------------------------------------------------

# If we got here, all is good.  Redirect away!
# Do it via Javascript, so that we can get google analytics.

print("<html>
<body>
<script async src=\"https://www.googletagmanager.com/gtag/js?id=UA-3138866-8\"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'UA-3138866-8');

  setTimeout(doRedirect, 250);
  function doRedirect() {
    window.location = \"$url\";
  }
</script>
</body>
</html>");
