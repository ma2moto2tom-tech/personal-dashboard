import os
import json
import csv
import io
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests

app = Flask(__name__, static_folder='public', static_url_path='')
CORS(app)

# ── 設定 ──
GOOGLE_SHEETS_ID = os.environ.get('GOOGLE_SHEETS_ID', '1qy8QoaWRg-1IzGkldplo6dNFEgEadMUfEZT_9ZZTluI')
GOOGLE_SHEETS_GID = os.environ.get('GOOGLE_SHEETS_GID', '1991911400')
CHATWORK_API_TOKEN = os.environ.get('CHATWORK_API_TOKEN', '')
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', '')
YOUTUBE_CHANNEL_ID = os.environ.get('YOUTUBE_CHANNEL_ID', '')


# ── 静的ファイル ──
@app.route('/')
def index():
    return send_from_directory('public', 'index.html')


# ── Google Sheets 健康データ（転置形式パーサー） ──
HEALTH_METRICS = ['最高血圧', '最低血圧', '体重', '睡眠', '酒(wine換算)', 'コーヒー',
                  'xAI', 'YouTube', '1時間以上Walk', '備考',
                  '10分心から話を聞く（遥菜）', '10分真剣に一緒に遊ぶ（俐太朗）',
                  'ケト始めてから']

import re

def parse_transposed_health_data(csv_text):
    """転置形式のスプレッドシートをパースして日別データに変換"""
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)

    all_daily_data = []
    i = 0
    while i < len(rows):
        row = rows[i]
        # 月ヘッダー行を探す (col[1]が "2024年1月" のような形式)
        if len(row) > 1 and re.match(r'20\d{2}年\d{1,2}月', row[1].strip()):
            year_month = row[1].strip()  # e.g. "2026年3月"
            match = re.match(r'(\d{4})年(\d{1,2})月', year_month)
            if not match:
                i += 1
                continue
            year = int(match.group(1))
            month = int(match.group(2))

            # 次の行は日付行のはず
            i += 1
            if i >= len(rows):
                break
            date_row = rows[i]
            # 日付列を特定 (col[2]以降に "3月1日" のような形式)
            dates = {}
            for col_idx in range(2, len(date_row)):
                cell = date_row[col_idx].strip()
                day_match = re.match(r'(\d{1,2})月(\d{1,2})日', cell)
                if day_match:
                    day = int(day_match.group(2))
                    date_str = f'{year}-{month:02d}-{day:02d}'
                    dates[col_idx] = date_str

            if not dates:
                i += 1
                continue

            # 日付ごとのデータ辞書を初期化
            daily = {}
            for col_idx, date_str in dates.items():
                daily[col_idx] = {'日付': date_str}

            # 続くメトリクス行を処理
            i += 1
            while i < len(rows):
                row = rows[i]
                if len(row) <= 1:
                    i += 1
                    continue
                metric_name = row[1].strip() if len(row) > 1 else ''

                # 次の月ヘッダーに到達したら抜ける
                if re.match(r'20\d{2}年\d{1,2}月', metric_name):
                    break
                # 空行やサマリー行をスキップ
                if not metric_name:
                    i += 1
                    continue

                # 各日の値を取得
                for col_idx, date_str in dates.items():
                    if col_idx < len(row):
                        val = row[col_idx].strip()
                        if val:
                            daily[col_idx][metric_name] = val
                i += 1

            # 日別データをリストに追加
            for col_idx in sorted(dates.keys()):
                entry = daily[col_idx]
                if len(entry) > 1:  # 日付以外のデータがある
                    all_daily_data.append(entry)
        else:
            i += 1

    # 日付でソート
    all_daily_data.sort(key=lambda x: x.get('日付', ''))
    return all_daily_data


@app.route('/api/health-data')
def get_health_data():
    try:
        url = f'https://docs.google.com/spreadsheets/d/{GOOGLE_SHEETS_ID}/gviz/tq?tqx=out:csv&gid={GOOGLE_SHEETS_GID}'
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        resp.encoding = 'utf-8'

        data = parse_transposed_health_data(resp.text)

        if not data:
            return jsonify({'error': 'No data found', 'data': [], 'count': 0}), 200

        # 使用されている全キーを収集
        all_keys = set()
        for entry in data:
            all_keys.update(entry.keys())
        headers = ['日付'] + sorted([k for k in all_keys if k != '日付'])

        return jsonify({
            'headers': headers,
            'data': data,
            'count': len(data)
        })
    except Exception as e:
        return jsonify({'error': str(e), 'data': [], 'count': 0}), 500


# ── Chatwork タスク ──
@app.route('/api/chatwork/tasks')
def get_chatwork_tasks():
    if not CHATWORK_API_TOKEN:
        return jsonify({'error': 'CHATWORK_API_TOKEN not configured', 'tasks': []}), 200

    try:
        headers = {'X-ChatWorkToken': CHATWORK_API_TOKEN}
        # 自分の情報を取得
        me_resp = requests.get('https://api.chatwork.com/v2/me', headers=headers, timeout=10)
        me_resp.raise_for_status()
        my_id = me_resp.json()['account_id']

        # 自分のタスクを取得
        tasks_resp = requests.get(
            'https://api.chatwork.com/v2/my/tasks',
            headers=headers,
            params={'status': 'open'},
            timeout=10
        )
        tasks_resp.raise_for_status()
        tasks = tasks_resp.json()

        return jsonify({
            'tasks': [{
                'id': t['task_id'],
                'body': t['body'],
                'room': t.get('room', {}).get('name', ''),
                'limit_time': t.get('limit_time', 0),
                'status': t['status']
            } for t in tasks[:20]]
        })
    except Exception as e:
        return jsonify({'error': str(e), 'tasks': []}), 200


# ── YouTube チャンネル統計 ──
@app.route('/api/youtube/stats')
def get_youtube_stats():
    if not YOUTUBE_API_KEY or not YOUTUBE_CHANNEL_ID:
        return jsonify({'error': 'YouTube API not configured', 'stats': None}), 200

    try:
        # チャンネル統計
        url = 'https://www.googleapis.com/youtube/v3/channels'
        params = {
            'part': 'statistics,snippet',
            'id': YOUTUBE_CHANNEL_ID,
            'key': YOUTUBE_API_KEY
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if not data.get('items'):
            return jsonify({'error': 'Channel not found', 'stats': None}), 200

        channel = data['items'][0]
        stats = channel['statistics']

        # 最新動画
        videos_url = 'https://www.googleapis.com/youtube/v3/search'
        videos_params = {
            'part': 'snippet',
            'channelId': YOUTUBE_CHANNEL_ID,
            'order': 'date',
            'maxResults': 5,
            'type': 'video',
            'key': YOUTUBE_API_KEY
        }
        videos_resp = requests.get(videos_url, params=videos_params, timeout=10)
        videos = []
        if videos_resp.ok:
            for item in videos_resp.json().get('items', []):
                videos.append({
                    'title': item['snippet']['title'],
                    'videoId': item['id']['videoId'],
                    'publishedAt': item['snippet']['publishedAt'],
                    'thumbnail': item['snippet']['thumbnails']['medium']['url']
                })

        return jsonify({
            'stats': {
                'subscriberCount': int(stats.get('subscriberCount', 0)),
                'viewCount': int(stats.get('viewCount', 0)),
                'videoCount': int(stats.get('videoCount', 0)),
                'channelName': channel['snippet']['title']
            },
            'recentVideos': videos
        })
    except Exception as e:
        return jsonify({'error': str(e), 'stats': None}), 200


# ── Google Calendar (公開カレンダー or API key方式) ──
@app.route('/api/calendar/events')
def get_calendar_events():
    # Google Calendar APIはOAuth2が必要なため、
    # フロントエンドのGoogleカレンダー埋め込みを使用
    return jsonify({'message': 'Use Google Calendar embed in frontend', 'events': []})


# ── マネーフォワード (概要情報) ──
@app.route('/api/moneyforward/summary')
def get_moneyforward_summary():
    return jsonify({
        'message': 'MoneyForward requires browser-based OAuth. Configure in settings.',
        'summary': None
    })


# ── Huawei Health データ ──
@app.route('/api/huawei/health')
def get_huawei_health():
    return jsonify({
        'message': 'Huawei Health Kit API integration. Configure credentials in .env',
        'data': None
    })


# ── 設定の保存/読み込み ──
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), 'settings.json')


@app.route('/api/settings', methods=['GET'])
def get_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                return jsonify(json.load(f))
    except Exception:
        pass
    return jsonify({})


@app.route('/api/settings', methods=['POST'])
def save_settings():
    try:
        data = request.get_json()
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # .envファイルを手動で読み込み
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())

    port = int(os.environ.get('PORT', 5000))
    print(f'Dashboard server starting on http://localhost:{port}')
    app.run(host='0.0.0.0', port=port, debug=True)
