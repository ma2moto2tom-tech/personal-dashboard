"""Vercel Serverless Function - Flask App"""
import os
import json
import csv
import io
import re
import xml.etree.ElementTree as ET
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
YOUTUBE_CHANNEL_ID = os.environ.get('YOUTUBE_CHANNEL_ID', 'UCCzo6GggJJWF-Fhd_QaCLCQ')


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


# ── 健康データ ──
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


# ── Chatwork タスク ──
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


# ── YouTube RSSフィード取得 ──
def fetch_youtube_rss(channel_id):
    """RSSフィードから動画一覧を取得（APIキー不要）"""
    rss_url = f'https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}'
    resp = http_requests.get(rss_url, timeout=15)
    resp.raise_for_status()

    ns = {
        'atom': 'http://www.w3.org/2005/Atom',
        'yt': 'http://www.youtube.com/xml/schemas/2015',
        'media': 'http://search.yahoo.com/mrss/'
    }
    root = ET.fromstring(resp.text)

    channel_name = root.find('atom:title', ns)
    channel_name = channel_name.text if channel_name is not None else 'Unknown'

    videos = []
    for entry in root.findall('atom:entry', ns):
        video_id = entry.find('yt:videoId', ns)
        title = entry.find('atom:title', ns)
        published = entry.find('atom:published', ns)
        media_group = entry.find('media:group', ns)
        thumbnail = None
        description = ''
        if media_group is not None:
            thumb_el = media_group.find('media:thumbnail', ns)
            if thumb_el is not None:
                thumbnail = thumb_el.get('url')
            desc_el = media_group.find('media:description', ns)
            if desc_el is not None:
                description = desc_el.text or ''

        vid = video_id.text if video_id is not None else ''

        videos.append({
            'videoId': vid,
            'title': title.text if title is not None else '',
            'publishedAt': published.text if published is not None else '',
            'thumbnail': thumbnail or f'https://i.ytimg.com/vi/{vid}/mqdefault.jpg',
            'views': 0,
            'description': description[:100]
        })

    return channel_name, videos


# ── YouTube チャンネル統計 ──
@app.route('/api/youtube/stats')
def get_youtube_stats():
    channel_id = YOUTUBE_CHANNEL_ID
    api_key = YOUTUBE_API_KEY

    if not channel_id:
        return jsonify({'error': 'YouTube channel ID not configured', 'stats': None}), 200

    try:
        if api_key:
            # APIキーあり: YouTube Data API使用
            url = 'https://www.googleapis.com/youtube/v3/channels'
            params = {
                'part': 'statistics,snippet',
                'id': channel_id,
                'key': api_key
            }
            resp = http_requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            api_data = resp.json()

            if not api_data.get('items'):
                return jsonify({'error': 'Channel not found', 'stats': None}), 200

            channel = api_data['items'][0]
            ch_stats = channel['statistics']

            search_url = 'https://www.googleapis.com/youtube/v3/search'
            search_params = {
                'part': 'snippet',
                'channelId': channel_id,
                'order': 'date',
                'maxResults': 10,
                'type': 'video',
                'key': api_key
            }
            search_resp = http_requests.get(search_url, params=search_params, timeout=10)
            video_items = search_resp.json().get('items', []) if search_resp.ok else []
            video_ids = [v['id']['videoId'] for v in video_items]

            videos = []
            if video_ids:
                vid_url = 'https://www.googleapis.com/youtube/v3/videos'
                vid_params = {
                    'part': 'statistics,snippet',
                    'id': ','.join(video_ids),
                    'key': api_key
                }
                vid_resp = http_requests.get(vid_url, params=vid_params, timeout=10)
                if vid_resp.ok:
                    for v in vid_resp.json().get('items', []):
                        videos.append({
                            'videoId': v['id'],
                            'title': v['snippet']['title'],
                            'publishedAt': v['snippet']['publishedAt'],
                            'thumbnail': v['snippet']['thumbnails'].get('medium', {}).get('url', ''),
                            'views': int(v['statistics'].get('viewCount', 0)),
                            'likes': int(v['statistics'].get('likeCount', 0)),
                            'comments': int(v['statistics'].get('commentCount', 0))
                        })

            return jsonify({
                'stats': {
                    'subscriberCount': int(ch_stats.get('subscriberCount', 0)),
                    'viewCount': int(ch_stats.get('viewCount', 0)),
                    'videoCount': int(ch_stats.get('videoCount', 0)),
                    'channelName': channel['snippet']['title']
                },
                'recentVideos': videos,
                'source': 'api'
            })

        else:
            # APIキーなし: RSSフィードで動画一覧を取得
            channel_name, videos = fetch_youtube_rss(channel_id)

            return jsonify({
                'stats': {
                    'subscriberCount': 0,
                    'viewCount': 0,
                    'videoCount': len(videos),
                    'channelName': channel_name
                },
                'recentVideos': videos[:10],
                'source': 'rss',
                'note': 'YouTube Data APIキーを設定すると再生回数等の詳細統計が表示されます'
            })

    except Exception as e:
        return jsonify({'error': str(e), 'stats': None}), 200


# ── Google Calendar ──
@app.route('/api/calendar/events')
def get_calendar_events():
    return jsonify({'message': 'Use Google Calendar embed in frontend', 'events': []})


# ── マネーフォワード ──
@app.route('/api/moneyforward/summary')
def get_moneyforward_summary():
    return jsonify({
        'message': 'MoneyForward requires browser-based OAuth.',
        'summary': None
    })


# ── 設定 ──
@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'POST':
        return jsonify({'status': 'ok'})
    return jsonify({})
