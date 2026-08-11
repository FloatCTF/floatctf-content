<?php
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $headers = getallheaders();
    if (isset($headers['X-Query'])) {
        $xQueryValue = $headers['X-Query'];
        if ($xQueryValue == "flag") {
            header('X-Res: ' . file_get_contents('/flag'));
            echo "flag在哪呢?";
        } else {
            echo "你想要的不是flag吗？";
        }
    } else {
        echo "请设置HTTP Header X-Query";
    }
} else {
    echo "请使用POST哦";
}
