// ══════════════════════════════════════════
//  務ダッシュボード - メインアプリケーション
// ══════════════════════════════════════════

const API_BASE = '';
let healthData = [];
let bpChart = null;
let sleepWeightChart = null;

// ── ポモドーロ状態 ──
const pomodoro = {
  workMinutes: 25,
  breakMinutes: 5,
  timeLeft: 25 * 60,
  isRunning: false,
  isBreak: false,
  count: 0,
  totalWorkSeconds: 0,
  interval: null,
  todayKey: new Date().toISOString().slice(0, 10)
};

// ══════════════════════════════════════════
//  初期化
// ══════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  updateHeaderDate();
  loadPomodoroState();
  refreshAll();
  // 1分ごとにヘッダー更新
  setInterval(updateHeaderDate, 60000);
});

function updateHeaderDate() {
  const now = new Date();
  const opts = { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' };
  const timeOpts = { hour: '2-digit', minute: '2-digit' };
  document.getElementById('headerDate').textContent =
    now.toLocaleDateString('ja-JP', opts) + ' ' + now.toLocaleTimeString('ja-JP', timeOpts);
}

async function refreshAll() {
  await loadHealthData();
  loadCalendarEvents();
  loadChatworkTasks();
  loadYoutubeStats();
}

// ══════════════════════════════════════════
//  健康データ
// ══════════════════════════════════════════
async function loadHealthData() {
  try {
    const resp = await fetch(`${API_BASE}/api/health-data`);
    const result = await resp.json();

    if (result.error) {
      console.warn('Health data error:', result.error);
      showHealthPlaceholder();
      return;
    }

    healthData = result.data || [];
    document.getElementById('healthDataCount').textContent = `${result.count}件のレコード`;

    updateSummaryCards();
    renderBPChart();
    renderSleepWeightChart();
    renderHealthTable(result.headers);
  } catch (e) {
    console.error('Failed to load health data:', e);
    showHealthPlaceholder();
  }
}

function showHealthPlaceholder() {
  // サマリーにサンプルデータを表示
  document.getElementById('summaryBP').textContent = '--/--';
  document.getElementById('summarySleep').textContent = '--h';
  document.getElementById('summaryWeight').textContent = '--kg';
}

function updateSummaryCards() {
  if (healthData.length === 0) return;

  // 最新のデータを検索（数値があるもの）
  const recent = [...healthData].reverse();

  // 血圧
  const bpEntry = recent.find(d => parseNum(d['最高血圧']) > 0);
  if (bpEntry) {
    const high = parseNum(bpEntry['最高血圧']);
    const low = parseNum(bpEntry['最低血圧']);
    document.getElementById('summaryBP').textContent = `${high}/${low}`;

    // トレンド
    const prev = recent.slice(1).find(d => parseNum(d['最高血圧']) > 0);
    if (prev) {
      const diff = high - parseNum(prev['最高血圧']);
      const el = document.getElementById('summaryBPTrend');
      if (diff > 0) {
        el.className = 'summary-trend trend-down'; // 血圧上昇は悪い
        el.textContent = `↑ +${diff} 前回比`;
      } else if (diff < 0) {
        el.className = 'summary-trend trend-up';
        el.textContent = `↓ ${diff} 前回比`;
      } else {
        el.className = 'summary-trend trend-neutral';
        el.textContent = '→ 変化なし';
      }
    }
  }

  // 睡眠
  const sleepEntry = recent.find(d => parseNum(d['睡眠']) > 0);
  if (sleepEntry) {
    const sleep = parseSleep(sleepEntry['睡眠']);
    document.getElementById('summarySleep').textContent = `${sleep.toFixed(1)}h`;

    const prev = recent.slice(1).find(d => parseNum(d['睡眠']) > 0);
    if (prev) {
      const diff = (sleep - parseSleep(prev['睡眠'])).toFixed(1);
      const el = document.getElementById('summarySleepTrend');
      if (diff > 0) {
        el.className = 'summary-trend trend-up';
        el.textContent = `↑ +${diff}h 前回比`;
      } else if (diff < 0) {
        el.className = 'summary-trend trend-down';
        el.textContent = `↓ ${diff}h 前回比`;
      } else {
        el.className = 'summary-trend trend-neutral';
        el.textContent = '→ 変化なし';
      }
    }
  }

  // 体重
  const weightEntry = recent.find(d => parseNum(d['体重']) > 0);
  if (weightEntry) {
    const weight = parseNum(weightEntry['体重']);
    document.getElementById('summaryWeight').textContent = `${weight}kg`;

    const prev = recent.slice(1).find(d => parseNum(d['体重']) > 0);
    if (prev) {
      const diff = (weight - parseNum(prev['体重'])).toFixed(1);
      const el = document.getElementById('summaryWeightTrend');
      if (diff > 0) {
        el.className = 'summary-trend trend-down';
        el.textContent = `↑ +${diff}kg 前回比`;
      } else if (diff < 0) {
        el.className = 'summary-trend trend-up';
        el.textContent = `↓ ${diff}kg 前回比`;
      } else {
        el.className = 'summary-trend trend-neutral';
        el.textContent = '→ 変化なし';
      }
    }
  }
}

// ── 血圧チャート ──
function renderBPChart() {
  const period = parseInt(document.getElementById('bpPeriod').value);
  const recent = healthData
    .filter(d => parseNum(d['最高血圧']) > 0)
    .slice(-period);

  if (recent.length === 0) return;

  const labels = recent.map(d => {
    const date = d['日付'] || d[Object.keys(d)[0]] || '';
    return date.replace(/2\d{3}年/, '').trim();
  });
  const highBP = recent.map(d => parseNum(d['最高血圧']));
  const lowBP = recent.map(d => parseNum(d['最低血圧']));

  const ctx = document.getElementById('bpChart').getContext('2d');
  if (bpChart) bpChart.destroy();

  bpChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: '最高血圧',
          data: highBP,
          borderColor: '#f87171',
          backgroundColor: 'rgba(248,113,113,0.1)',
          borderWidth: 2,
          tension: 0.3,
          fill: true,
          pointRadius: period > 30 ? 0 : 3,
          pointHoverRadius: 5
        },
        {
          label: '最低血圧',
          data: lowBP,
          borderColor: '#4f8cff',
          backgroundColor: 'rgba(79,140,255,0.1)',
          borderWidth: 2,
          tension: 0.3,
          fill: true,
          pointRadius: period > 30 ? 0 : 3,
          pointHoverRadius: 5
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { labels: { color: '#5e6278', font: { size: 11 } } },
        tooltip: {
          backgroundColor: '#ffffff',
          borderColor: '#e8e8ef',
          borderWidth: 1,
          titleColor: '#1a1f36',
          bodyColor: '#5e6278'
        }
      },
      scales: {
        x: {
          ticks: { color: '#6b7280', font: { size: 10 }, maxTicksLimit: 10 },
          grid: { color: 'rgba(0,0,0,0.06)' }
        },
        y: {
          ticks: { color: '#6b7280', font: { size: 10 } },
          grid: { color: 'rgba(0,0,0,0.06)' },
          suggestedMin: 50,
          suggestedMax: 160
        }
      }
    }
  });
}

function updateBPChart() { renderBPChart(); }

// ── 睡眠・体重チャート ──
function renderSleepWeightChart() {
  const recent = healthData
    .filter(d => parseNum(d['睡眠']) > 0 || parseNum(d['体重']) > 0)
    .slice(-30);

  if (recent.length === 0) return;

  const labels = recent.map(d => {
    const date = d['日付'] || d[Object.keys(d)[0]] || '';
    return date.replace(/2\d{3}年/, '').trim();
  });
  const sleepData = recent.map(d => parseNum(d['睡眠']) ? parseSleep(d['睡眠']) : null);
  const weightData = recent.map(d => parseNum(d['体重']) || null);

  const ctx = document.getElementById('sleepWeightChart').getContext('2d');
  if (sleepWeightChart) sleepWeightChart.destroy();

  sleepWeightChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: '睡眠(h)',
          data: sleepData,
          borderColor: '#4f8cff',
          backgroundColor: 'rgba(79,140,255,0.1)',
          borderWidth: 2,
          tension: 0.3,
          fill: true,
          yAxisID: 'y',
          pointRadius: 2,
          spanGaps: true
        },
        {
          label: '体重(kg)',
          data: weightData,
          borderColor: '#34d399',
          backgroundColor: 'rgba(52,211,153,0.1)',
          borderWidth: 2,
          tension: 0.3,
          fill: true,
          yAxisID: 'y1',
          pointRadius: 2,
          spanGaps: true
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { labels: { color: '#5e6278', font: { size: 11 } } },
        tooltip: {
          backgroundColor: '#ffffff',
          borderColor: '#e8e8ef',
          borderWidth: 1,
          titleColor: '#1a1f36',
          bodyColor: '#5e6278'
        }
      },
      scales: {
        x: {
          ticks: { color: '#6b7280', font: { size: 10 }, maxTicksLimit: 10 },
          grid: { color: 'rgba(0,0,0,0.06)' }
        },
        y: {
          type: 'linear',
          position: 'left',
          title: { display: true, text: '睡眠(h)', color: '#4f8cff', font: { size: 10 } },
          ticks: { color: '#6b7280', font: { size: 10 } },
          grid: { color: 'rgba(0,0,0,0.06)' },
          suggestedMin: 3,
          suggestedMax: 10
        },
        y1: {
          type: 'linear',
          position: 'right',
          title: { display: true, text: '体重(kg)', color: '#34d399', font: { size: 10 } },
          ticks: { color: '#6b7280', font: { size: 10 } },
          grid: { drawOnChartArea: false }
        }
      }
    }
  });
}

// ── 健康データテーブル ──
function renderHealthTable(headers) {
  const showHeaders = headers.filter(h =>
    ['日付', '最高血圧', '最低血圧', '体重', '睡眠', '酒', '勤務', 'コーヒー'].includes(h)
  );
  if (showHeaders.length === 0) return;

  const recent = [...healthData].reverse().slice(0, 30);

  let html = '<table class="health-table"><thead><tr>';
  showHeaders.forEach(h => html += `<th>${h}</th>`);
  html += '</tr></thead><tbody>';

  recent.forEach(row => {
    html += '<tr>';
    showHeaders.forEach(h => {
      let val = row[h] || '-';
      html += `<td>${escapeHtml(val)}</td>`;
    });
    html += '</tr>';
  });

  html += '</tbody></table>';
  document.getElementById('healthTableContainer').innerHTML = html;
}

// ══════════════════════════════════════════
//  ポモドーロタイマー
// ══════════════════════════════════════════
function loadPomodoroState() {
  const saved = localStorage.getItem('pomodoro_' + pomodoro.todayKey);
  if (saved) {
    const state = JSON.parse(saved);
    pomodoro.count = state.count || 0;
    pomodoro.totalWorkSeconds = state.totalWorkSeconds || 0;
  }
  updatePomodoroDisplay();
}

function savePomodoroState() {
  localStorage.setItem('pomodoro_' + pomodoro.todayKey, JSON.stringify({
    count: pomodoro.count,
    totalWorkSeconds: pomodoro.totalWorkSeconds
  }));
}

function togglePomodoro() {
  if (pomodoro.isRunning) {
    pausePomodoro();
  } else {
    startPomodoro();
  }
}

function startPomodoro() {
  pomodoro.isRunning = true;
  document.getElementById('pomodoroStartBtn').textContent = '一時停止';

  pomodoro.interval = setInterval(() => {
    pomodoro.timeLeft--;
    if (!pomodoro.isBreak) {
      pomodoro.totalWorkSeconds++;
    }

    if (pomodoro.timeLeft <= 0) {
      clearInterval(pomodoro.interval);
      pomodoro.isRunning = false;

      if (!pomodoro.isBreak) {
        pomodoro.count++;
        document.getElementById('summaryPomodoro').textContent = pomodoro.count;
        savePomodoroState();
        notifyPomodoro('作業完了！休憩しましょう 🎉');
        // 休憩に切り替え
        pomodoro.isBreak = true;
        pomodoro.timeLeft = pomodoro.breakMinutes * 60;
      } else {
        notifyPomodoro('休憩終了！次の作業を始めましょう 💪');
        // 作業に切り替え
        pomodoro.isBreak = false;
        pomodoro.timeLeft = pomodoro.workMinutes * 60;
      }
      document.getElementById('pomodoroStartBtn').textContent = '開始';
    }

    updatePomodoroDisplay();
  }, 1000);
}

function pausePomodoro() {
  clearInterval(pomodoro.interval);
  pomodoro.isRunning = false;
  document.getElementById('pomodoroStartBtn').textContent = '再開';
  savePomodoroState();
}

function resetPomodoro() {
  clearInterval(pomodoro.interval);
  pomodoro.isRunning = false;
  pomodoro.isBreak = false;
  pomodoro.timeLeft = pomodoro.workMinutes * 60;
  document.getElementById('pomodoroStartBtn').textContent = '開始';
  updatePomodoroDisplay();
}

function skipPomodoro() {
  clearInterval(pomodoro.interval);
  pomodoro.isRunning = false;

  if (pomodoro.isBreak) {
    pomodoro.isBreak = false;
    pomodoro.timeLeft = pomodoro.workMinutes * 60;
  } else {
    pomodoro.isBreak = true;
    pomodoro.timeLeft = pomodoro.breakMinutes * 60;
  }
  document.getElementById('pomodoroStartBtn').textContent = '開始';
  updatePomodoroDisplay();
}

function updatePomodoroDisplay() {
  const mins = Math.floor(pomodoro.timeLeft / 60);
  const secs = pomodoro.timeLeft % 60;
  const timer = document.getElementById('pomodoroTimer');
  timer.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  timer.className = `pomodoro-timer ${pomodoro.isBreak ? 'break' : 'work'}`;

  document.getElementById('pomodoroLabel').textContent =
    pomodoro.isBreak ? '休憩時間' : '作業時間';

  document.getElementById('pomodoroCount').textContent = pomodoro.count;
  document.getElementById('summaryPomodoro').textContent = pomodoro.count;

  const totalMins = Math.floor(pomodoro.totalWorkSeconds / 60);
  document.getElementById('pomodoroTotal').textContent =
    totalMins >= 60 ? `${Math.floor(totalMins / 60)}h${totalMins % 60}m` : `${totalMins}分`;
}

function notifyPomodoro(message) {
  if ('Notification' in window && Notification.permission === 'granted') {
    new Notification('🍅 ポモドーロ', { body: message });
  } else if ('Notification' in window && Notification.permission !== 'denied') {
    Notification.requestPermission().then(perm => {
      if (perm === 'granted') {
        new Notification('🍅 ポモドーロ', { body: message });
      }
    });
  }
  // サウンド
  try {
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.frequency.value = 800;
    gain.gain.value = 0.3;
    osc.start();
    setTimeout(() => { osc.stop(); audioCtx.close(); }, 300);
  } catch (e) { /* ignore */ }
}

// ══════════════════════════════════════════
//  Googleカレンダー
// ══════════════════════════════════════════
function loadCalendarEvents() {
  // Google Calendar APIをフロントエンドで直接使う場合
  const calendarId = localStorage.getItem('dashboard_calendar_id');
  const container = document.getElementById('calendarEvents');

  if (!calendarId) {
    container.innerHTML = `
      <div class="not-connected">
        <div class="icon">📅</div>
        <p>設定からGoogleカレンダーIDを<br>入力して接続してください</p>
        <p style="font-size:0.75rem;margin-top:8px;color:var(--text-muted)">
          カレンダーID例: your-email@gmail.com
        </p>
      </div>`;
    document.getElementById('calendarStatus').className = 'status-badge disconnected';
    document.getElementById('calendarStatus').textContent = '未接続';
    return;
  }

  // サンプルイベントの表示（API連携時に置き換え）
  const today = new Date();
  const sampleEvents = [
    { time: '09:00', title: '朝ミーティング', desc: 'チーム定例' },
    { time: '10:30', title: 'クライアントMTG', desc: 'プロジェクト進捗確認' },
    { time: '13:00', title: '昼休憩', desc: '' },
    { time: '14:00', title: '開発作業', desc: 'フロントエンド実装' },
    { time: '16:00', title: 'コードレビュー', desc: 'PR #42のレビュー' },
    { time: '17:30', title: '日報作成', desc: '' },
  ];

  container.innerHTML = sampleEvents.map(ev => `
    <li class="calendar-event">
      <span class="event-time">${ev.time}</span>
      <span class="event-dot"></span>
      <div class="event-details">
        <h4>${escapeHtml(ev.title)}</h4>
        ${ev.desc ? `<p>${escapeHtml(ev.desc)}</p>` : ''}
      </div>
    </li>
  `).join('');

  document.getElementById('calendarStatus').className = 'status-badge connected';
  document.getElementById('calendarStatus').textContent = 'サンプル表示中';
}

// ══════════════════════════════════════════
//  Chatwork
// ══════════════════════════════════════════
async function loadChatworkTasks() {
  try {
    const resp = await fetch(`${API_BASE}/api/chatwork/tasks`);
    const result = await resp.json();
    const container = document.getElementById('chatworkTasks');

    if (result.error && result.tasks.length === 0) {
      return; // 未接続のまま
    }

    if (result.tasks.length === 0) {
      container.innerHTML = '<div class="not-connected"><p>現在タスクはありません</p></div>';
      document.getElementById('chatworkStatus').className = 'status-badge connected';
      document.getElementById('chatworkStatus').textContent = '接続中';
      return;
    }

    document.getElementById('chatworkStatus').className = 'status-badge connected';
    document.getElementById('chatworkStatus').textContent = '接続中';

    container.innerHTML = result.tasks.map(task => `
      <li class="task-item">
        <div class="task-checkbox" onclick="this.classList.toggle('done')"></div>
        <span>${escapeHtml(task.body.substring(0, 80))}${task.body.length > 80 ? '...' : ''}</span>
        ${task.room ? `<span class="task-room">${escapeHtml(task.room)}</span>` : ''}
      </li>
    `).join('');
  } catch (e) {
    console.error('Chatwork error:', e);
  }
}

// ══════════════════════════════════════════
//  YouTube
// ══════════════════════════════════════════
async function loadYoutubeStats() {
  try {
    const resp = await fetch(`${API_BASE}/api/youtube/stats`);
    const result = await resp.json();

    if (!result.stats) return;

    document.getElementById('youtubeStatus').className = 'status-badge connected';
    document.getElementById('youtubeStatus').textContent = '接続中';

    const s = result.stats;
    let html = `
      <div class="yt-stats-grid">
        <div class="yt-stat">
          <div class="value">${formatNumber(s.subscriberCount)}</div>
          <div class="label">登録者数</div>
        </div>
        <div class="yt-stat">
          <div class="value">${formatNumber(s.viewCount)}</div>
          <div class="label">総再生回数</div>
        </div>
        <div class="yt-stat">
          <div class="value">${s.videoCount}</div>
          <div class="label">動画数</div>
        </div>
      </div>`;

    if (result.recentVideos && result.recentVideos.length > 0) {
      html += '<ul class="yt-video-list">';
      result.recentVideos.forEach(v => {
        const date = new Date(v.publishedAt).toLocaleDateString('ja-JP');
        html += `
          <li class="yt-video">
            <img src="${v.thumbnail}" alt="" loading="lazy">
            <div class="yt-video-info">
              <h4>${escapeHtml(v.title)}</h4>
              <p>${date}</p>
            </div>
          </li>`;
      });
      html += '</ul>';
    }

    document.getElementById('youtubeContent').innerHTML = html;
  } catch (e) {
    console.error('YouTube error:', e);
  }
}

// ══════════════════════════════════════════
//  設定モーダル
// ══════════════════════════════════════════
function openSettings() {
  document.getElementById('settingsModal').classList.add('active');
  // 保存済みの設定を読み込む
  document.getElementById('settingSheetsId').value =
    localStorage.getItem('dashboard_sheets_id') || '';
  document.getElementById('settingChatworkToken').value =
    localStorage.getItem('dashboard_chatwork_token') || '';
  document.getElementById('settingYoutubeKey').value =
    localStorage.getItem('dashboard_youtube_key') || '';
  document.getElementById('settingYoutubeChannel').value =
    localStorage.getItem('dashboard_youtube_channel') || '';
  document.getElementById('settingCalendarUrl').value =
    localStorage.getItem('dashboard_calendar_id') || '';
  document.getElementById('settingPomodoroWork').value = pomodoro.workMinutes;
  document.getElementById('settingPomodoroBreak').value = pomodoro.breakMinutes;
}

function closeSettings() {
  document.getElementById('settingsModal').classList.remove('active');
}

async function saveSettings() {
  const settings = {
    sheetsId: document.getElementById('settingSheetsId').value.trim(),
    chatworkToken: document.getElementById('settingChatworkToken').value.trim(),
    youtubeKey: document.getElementById('settingYoutubeKey').value.trim(),
    youtubeChannel: document.getElementById('settingYoutubeChannel').value.trim(),
    calendarId: document.getElementById('settingCalendarUrl').value.trim(),
    pomodoroWork: parseInt(document.getElementById('settingPomodoroWork').value) || 25,
    pomodoroBreak: parseInt(document.getElementById('settingPomodoroBreak').value) || 5
  };

  // ローカル保存
  localStorage.setItem('dashboard_sheets_id', settings.sheetsId);
  localStorage.setItem('dashboard_chatwork_token', settings.chatworkToken);
  localStorage.setItem('dashboard_youtube_key', settings.youtubeKey);
  localStorage.setItem('dashboard_youtube_channel', settings.youtubeChannel);
  localStorage.setItem('dashboard_calendar_id', settings.calendarId);

  // ポモドーロ設定更新
  pomodoro.workMinutes = settings.pomodoroWork;
  pomodoro.breakMinutes = settings.pomodoroBreak;
  if (!pomodoro.isRunning) {
    pomodoro.timeLeft = (pomodoro.isBreak ? pomodoro.breakMinutes : pomodoro.workMinutes) * 60;
    updatePomodoroDisplay();
  }

  // サーバーにも保存（APIキーなど）
  try {
    await fetch(`${API_BASE}/api/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    });
  } catch (e) {
    console.warn('Settings save to server failed:', e);
  }

  closeSettings();
  refreshAll();
}

// ── 設定モーダル: オーバーレイクリックで閉じる ──
document.getElementById('settingsModal').addEventListener('click', (e) => {
  if (e.target === e.currentTarget) closeSettings();
});

// ══════════════════════════════════════════
//  ユーティリティ
// ══════════════════════════════════════════
function parseNum(val) {
  if (!val) return 0;
  const n = parseFloat(String(val).replace(/[^\d.-]/g, ''));
  return isNaN(n) ? 0 : n;
}

// 睡眠データは10分の1時間単位 (80 = 8.0時間)
function parseSleep(val) {
  const n = parseNum(val);
  return n > 24 ? n / 10 : n; // 24以上なら10で割る
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function formatNumber(num) {
  if (num >= 10000) return (num / 10000).toFixed(1) + '万';
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
  return String(num);
}
