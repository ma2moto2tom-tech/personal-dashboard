import os
import sys

# 絶対パスで作業ディレクトリを設定
project_dir = '/Users/tsutomu/Desktop/務ダッシュボード'
os.chdir(project_dir)
sys.path.insert(0, project_dir)

# .envファイルを読み込み
env_path = os.path.join(project_dir, '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

from server import app
app.run(host='0.0.0.0', port=5000, debug=True)
