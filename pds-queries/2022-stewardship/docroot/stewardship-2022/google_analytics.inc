<?php # -*- php -*-

$google_analytics_id = 'UA-3138866-8';

print("<script async src=\"https://www.googletagmanager.com/gtag/js?id=$google_analytics_id\"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());

  gtag('config', '$google_analytics_id');
</script>
");
?>
