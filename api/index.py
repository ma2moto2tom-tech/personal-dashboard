"""Vercel Serverless Function - Flask App"""
import os
import json
import csv
import io
import re
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests as http_requests

app = Flask(__name__)
CORS(app)

# ── 設定 ──
GOOGLE_SHEETS_ID = os.environ.get('GOOGLE_SHEETS_ID', '1qy8QoaWRg-1IzGkldplo6dNFEgEadMUfEZT_9ZZTluI')
GOOGLE_SHEETS_GID = os.environ.get('GOOGLE_SHEETS_GID', '1991911400')
CHATWORK_API_TOKEN = os.environ.get('CHATWORK_API_TOKEN', '')
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', '')
YOUTUBE_CHANNEL_ID = os.environ.get('YOUTUBE_CHANNEL_ID', '')


def parse_transposed_health_data(csv_text):
    """転置形式のスプレッドシートをパースして日別データに変換"""
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)

    all_daily_data = []
    i = 0
    while i < len(rows):
        row = rows[i]
        if len(row) > 1 and re.match(r'20\d{2}年\d{1,2}月', row[1].strip()):
            year_month = row[1].strip()
            match = re.match(r'(\d{4})年(\d{1,2})月', year_month)
            if not match:
                i += 1
                continue
            year = int(match.group(1))
            month = int(match.group(2))

            i += 1
            if i >= len(rows):
                break
            date_row = rows[i]
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

            daily = {}
            for col_idx, date_str in dates.items():
                daily[col_idx] = {'日付': date_str}

            i += 1
            while i < len(rows):
                row = rows[i]
                if len(row) <= 1:
                    i += 1
                    continue
                metric_name = row[1].strip() if len(row) > 1 else ''

                if re.match(r'20\d{2}年\d{1,2}月', metric_name):
                    break
                if not metric_name:
                    i += 1
                    continue

                for col_idx, date_str in dates.items():
                    if col_idx < len(row):
                        val = row[col_idx].strip()
                        if val:
                            daily[col_idx][metric_name] = val
                i += 1

            for col_idx in sorted(dates.keys()):
                entry = daily[col_idx]
                if len(entry) > 1:
                    all_daily_data.append(entry)
        else:
            i += 1

    all_daily_data.sort(key=lambda x: x.get('日付', ''))
    return all_daily_data


@app.route('/api/health-data')
def get_health_data():
    try:
        url = f'https://docs.google.com/spreadsheets/d/{GOOGLE_SHEETS_ID}/gviz/tq?tqx=out:csv&gid={GOOGLE_SHEETS_GID}'
        resp = http_requests.get(url, timeout=15)
        resp.raise_for_status()
        resp.encoding = 'utf-8'

        data = parse_transposed_health_data(resp.text)

        if not data:
            return jsonify({'error': 'No data found', 'data': [], 'count': 0}), 200

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


@app.route('/api/chatwork/tasks')
def get_chatwork_tasks():
    if not CHATWORK_API_TOKEN:
        return jsonify({'error': 'CHATWORK_API_TOKEN not configured', 'tasks': []}), 200

    try:
        headers = {'X-ChatWorkToken': CHATWORK_API_TOKEN}
        me_resp = http_requests.get('https://api.chatwork.com/v2/me', headers=headers, timeout=10)
        me_resp.raise_for_status()

        tasks_resp = http_requests.get(
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


@app.route('/api/youtube/stats')
def get_youtube_stats():
    if not YOUTUBE_API_KEY or not YOUTUBE_CHANNEL_ID:
        return jsonify({'error': 'YouTube API not configured', 'stats': None}), 200

    try:
        url = 'https://www.googleapis.com/youtube/v3/channels'
        params = {
            'part': 'statistics,snippet',
            'id': YOUTUBE_CHANNEL_ID,
            'key': YOUTUBE_API_KEY
        }
        resp = http_requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if not data.get('items'):
            return jsonify({'error': 'Channel not found', 'stats': None}), 200

        channel = data['items'][0]
        stats = channel['statistics']

        videos_url = 'https://www.googleapis.com/youtube/v3/search'
        videos_params = {
            'part': 'snippet',
            'channelId': YOUTUBE_CHANNEL_ID,
            'order': 'date',
            'maxResults': 5,
            'type': 'video',
            'key': YOUTUBE_API_KEY
        }
        videos_resp = http_requests.get(videos_url, params=videos_params, timeout=10)
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


@app.route('/api/calendar/events')
def get_calendar_events():
    return jsonify({'message': 'Use Google Calendar embed in frontend', 'events': []})


@app.route('/api/moneyforward/summary')
def get_moneyforward_summary():
    return jsonify({
        'message': 'MoneyForward requires browser-based OAuth. Configure in settings.',
        'summary': None
    })


@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        return jsonify({'status': 'ok'})
    return jsonify({})
