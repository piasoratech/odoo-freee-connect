#!/bin/bash
set -e

# VPS初回セットアップスクリプト

# 1. デプロイ先ディレクトリの作成
mkdir -p /opt/invoice-generator
cd /opt/invoice-generator

# 2. .envファイルの初期配置（値は手動で記入）
cp config/.env.example .env
echo "⚠️  .envを編集してAPIキーを入力してください"

# 3. freeeトークンの初期取得（別途OAuth認証フローを実行）
echo "⚠️  freee OAuth認証を実行し .freee_token.json を配置してください"

# 4. cron設定
cat > /etc/cron.d/invoice-generator << 'EOF'
0 3 2 * * root cd /opt/invoice-generator && python3 invoice_generator.py --month prev >> /var/log/invoice-generator.log 2>&1
EOF
chmod 644 /etc/cron.d/invoice-generator

# 5. ログローテーション設定
cat > /etc/logrotate.d/invoice-generator << 'EOF'
/var/log/invoice-generator.log {
    monthly
    rotate 12
    compress
    missingok
    notifempty
}
EOF

echo "✅ VPS初回セットアップ完了"
