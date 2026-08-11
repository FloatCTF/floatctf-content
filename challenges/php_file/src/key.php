<?php

if (!isset($_SERVER['HTTP_REFERER']) || strpos($_SERVER['HTTP_REFERER'], 'index.php') === false) {
    header('HTTP/1.1 404 Not Found');
    echo '404 Page Not Found';
    exit;
}

header('Content-Type: text/plain');
echo file_get_contents('/flag');
?>