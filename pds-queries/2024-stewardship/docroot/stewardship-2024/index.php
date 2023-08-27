<?php

// Constants

$filename = "/home/jsquyres/stewardship-2024-data/cookies.sqlite3";
$unrecognized_key_url = "unknown.php";
$error_url = "error.php";

#----------------------------------------------------------------------

# JMS Debug
#print("<pre>\n"); flush();

#----------------------------------------------------------------------

# If we didn't get a key (i.e., a cookie), bump over to the page that
# prompts for the cookie.
if (!array_key_exists("key", $_GET)) {
    header("Location: code.php");
    exit(0);
}
$cookie = htmlspecialchars($_GET['key']);
$cookie = strtoupper($cookie);

#----------------------------------------------------------------------

$db_handle  = new SQLite3($filename);

# Get the URL from the most recent row in the database with the
# correct cookie (remember: the cookie will be identical for all rows
# with the same FID).
$query = "SELECT url FROM COOKIES WHERE cookie=:cookie ORDER BY creation_timestamp DESC LIMIT 1";
$stmt = $db_handle->prepare($query);
$stmt->bindParam(':cookie', $cookie);
$result = $stmt->execute();
$row = $result->fetchArray();
if (!$row) {
    header("Location: $unrecognized_key_url");
    exit(0);
}

$url  = $row['url'];

#----------------------------------------------------------------------

# If we got here, all is good.  Redirect away!
# Do it via Javascript, so that we can delay a little bit to give the
# Google Analytics a little time to process.

print("<html>\n<body>\n");
include("google_analytics.inc");
print("<script>
setTimeout(doRedirect, 250);
function doRedirect() {
  window.location = \"$url\";
}
</script>
</body>
</html>
");
