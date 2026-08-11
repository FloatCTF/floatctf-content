<?php
// 设置默认 cookie
if (!isset($_COOKIE['role'])) {
    setcookie('role', 'guest', time() + 3600);
    $_COOKIE['role'] = 'guest';
}

$role = $_COOKIE['role'] ?? 'guest';
$username = $_COOKIE['username'] ?? 'Anonymous';
?>

<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cookie Challenge - FreshCup CTF</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Arial', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        
        .container {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 500px;
            width: 90%;
        }
        
        h1 {
            color: #333;
            margin-bottom: 10px;
            text-align: center;
        }
        
        .status {
            background: #f0f0f0;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
        }
        
        .role {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
            margin-left: 10px;
        }
        
        .role-guest {
            background: #ffd93d;
            color: #333;
        }
        
        .role-admin {
            background: #6bcf7f;
            color: white;
        }
        
        .message {
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
            text-align: center;
        }
        
        .error {
            background: #ffebee;
            color: #c62828;
            border: 1px solid #ef5350;
        }
        
        .success {
            background: #e8f5e9;
            color: #2e7d32;
            border: 1px solid #66bb6a;
        }
        
        .flag {
            background: #333;
            color: #0f0;
            padding: 15px;
            border-radius: 10px;
            font-family: 'Courier New', monospace;
            font-size: 1.1em;
            text-align: center;
            margin: 20px 0;
        }
        
        .hint {
            background: #e3f2fd;
            color: #1565c0;
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
            border-left: 4px solid #1976d2;
        }
        
        .hint h3 {
            margin-bottom: 10px;
        }
        
        .hint ul {
            margin-left: 20px;
        }
        
        .hint li {
            margin: 5px 0;
        }
        
        .cookie-display {
            background: #f5f5f5;
            padding: 10px;
            border-radius: 5px;
            font-family: monospace;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Cookie 管理系统</h1>
        
        <div class="status">
            <p><strong>当前用户：</strong> <?php echo htmlspecialchars($username); ?></p>
            <p><strong>用户角色：</strong> 
                <span class="role <?php echo $role === 'admin' ? 'role-admin' : 'role-guest'; ?>">
                    <?php echo htmlspecialchars($role); ?>
                </span>
            </p>
        </div>
        
        <?php if ($role === 'admin'): ?>
            <div class="message success">
                <h2>恭喜你，管理员！</h2>
                <p>你成功获得了管理员权限！</p>
            </div>
            <div class="flag">
                <?php echo file_get_contents('/flag'); ?>
            </div>
        <?php else: ?>
            <div class="message error">
                <h2>权限不足</h2>
                <p>你当前是游客身份，无法查看 flag</p>
                <p>只有管理员才能看到 flag！</p>
            </div>
            
        <?php endif; ?>
    </div>
</body>
</html>