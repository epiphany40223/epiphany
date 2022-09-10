<?php # -*- php -*-

$google_analytics_tag_id = 'G-EW3K1B3YR6';

print("<!-- Google tag (gtag.js) -->
<script async src=\"https://www.googletagmanager.com/gtag/js?id=$google_analytics_tag_id\"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());

  gtag('config', '$google_analytics_tag_id');
</script>
");
?>
