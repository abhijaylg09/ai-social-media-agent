// State
let currentTab = 'studio';
let currentActiveThread = null;
let editingPostThread = null;
let editingPlatform = null;
let currentFilter = 'all';

// DOM Elements
document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initStudio();
  initApprovalQueue();
  initSchedule();
  initTools();
  initSettings();
  loadInitialData();

  // Periodic polling for queue count & logs
  setInterval(loadQueueCount, 10000);
});

// 1. Navigation
function initNavigation() {
  const navBtns = document.querySelectorAll('.nav-btn');
  navBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTab = btn.getAttribute('data-tab');
      switchTab(targetTab);
    });
  });

  // Cron trigger button in header
  const cronBtn = document.getElementById('triggerCronBtn');
  if (cronBtn) {
    cronBtn.addEventListener('click', async () => {
      cronBtn.disabled = true;
      cronBtn.innerHTML = `<span>Running Cron...</span>`;
      try {
        const res = await fetch('/api/cron/trigger-campaign', { method: 'POST' });
        const data = await res.json();
        showToast(data.message || 'Cron Campaign Triggered!');
        loadApprovalQueue();
        loadQueueCount();
      } catch (err) {
        showToast('Error triggering cron campaign: ' + err.message, true);
      } finally {
        cronBtn.disabled = false;
        cronBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"></path></svg><span>Trigger Daily Cron</span>`;
      }
    });
  }
}

function switchTab(tabId) {
  currentTab = tabId;
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.toggle('active', b.getAttribute('data-tab') === tabId));
  document.querySelectorAll('.tab-view').forEach(v => v.classList.toggle('active', v.id === `tab-${tabId}`));

  const titles = {
    studio: { title: 'Workflow Studio', subtitle: 'Draft multi-platform social campaigns with autonomous research & human verification' },
    approval: { title: 'Human Approval Queue', subtitle: 'Review, modify, and authorize LangGraph drafts before live API dispatch' },
    schedule: { title: 'Content Schedule', subtitle: 'Monitor queued posts, countdowns, and published broadcast history' },
    tools: { title: 'Tool Calling & Logs', subtitle: 'Inspect LangChain tool execution logs and test individual capabilities' },
    settings: { title: 'API & OAuth Settings', subtitle: 'Configure Gemini API keys, LLM models, and social network credentials' }
  };

  if (titles[tabId]) {
    document.getElementById('pageTitle').textContent = titles[tabId].title;
    document.getElementById('pageSubtitle').textContent = titles[tabId].subtitle;
  }

  if (tabId === 'approval') loadApprovalQueue();
  if (tabId === 'schedule') loadScheduleFeed();
  if (tabId === 'tools') loadToolLogs();
}

// 2. Workflow Studio
function initStudio() {
  const form = document.getElementById('generateForm');
  const quickBtns = document.querySelectorAll('.tag-btn');
  const platformChips = document.querySelectorAll('.platform-chip');

  // Tag quick clicks
  quickBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      document.getElementById('topicInput').value = btn.getAttribute('data-topic');
    });
  });

  // Toggle platform chip styling
  platformChips.forEach(chip => {
    chip.addEventListener('click', (e) => {
      const checkbox = chip.querySelector('input[type="checkbox"]');
      if (e.target !== checkbox) checkbox.checked = !checkbox.checked;
      chip.classList.toggle('active', checkbox.checked);
    });
  });

  // Submit generator form
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const topic = document.getElementById('topicInput').value.trim();
    const tone = document.getElementById('toneSelect').value;
    const scheduled_time = document.getElementById('scheduleTimeInput').value;

    const platforms = [];
    document.querySelectorAll('.platform-chip input:checked').forEach(c => platforms.push(c.value));

    if (!topic) return alert('Please enter a content topic.');
    if (platforms.length === 0) return alert('Please select at least one social platform.');

    const startBtn = document.getElementById('startAgentBtn');
    startBtn.disabled = true;
    startBtn.innerHTML = `<span>Orchestrating LangGraph...</span>`;

    // Visualizer animation
    resetPipelineVisuals();
    setNodeStatus('node-start', 'completed');
    setNodeStatus('node-generate', 'running');
    appendLog('[START] Initiated LangGraph pipeline for topic: "' + topic + '"', 'completed');
    appendLog('[generate_drafts] Calling search_trending_topics tool & invoking Gemini...', 'running');

    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, tone, platforms, scheduled_time: scheduled_time || null })
      });

      const data = await res.json();
      if (!data.success) throw new Error(data.detail || 'Execution failed');

      currentActiveThread = data.thread_id;
      document.getElementById('activeThreadTag').textContent = `Thread: ${currentActiveThread.substring(0, 8)}...`;

      // Update Visualizer to reflect breakpoint
      setNodeStatus('node-generate', 'completed');
      setNodeStatus('node-review', 'completed');
      setNodeStatus('node-human', 'waiting');
      document.getElementById('graphStateBadge').textContent = 'Paused at Human Gatekeeper';
      document.getElementById('graphStateBadge').style.color = '#fbbf24';

      appendLog(`[review_drafts] Completed brand safety & virality audit.`, 'completed');
      appendLog(`[human_approval] ⏸️ LangGraph interrupt() active! Workflow halted awaiting human sign-off.`, 'waiting');

      loadQueueCount();

      // Show toast and option to jump to Approval Queue
      showToast('Drafts generated! Jump to Approval Queue to inspect & authorize.');
      setTimeout(() => switchTab('approval'), 1200);

    } catch (err) {
      appendLog(`[ERROR] ${err.message}`, 'waiting');
      showToast('Error: ' + err.message, true);
    } finally {
      startBtn.disabled = false;
      startBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg><span>Run LangGraph Agent</span>`;
    }
  });
}

// 3. Human Approval Queue (HITL)
async function loadApprovalQueue() {
  const feed = document.getElementById('approvalFeed');
  feed.innerHTML = `<div class="empty-state"><p>Loading pending reviews...</p></div>`;

  try {
    const res = await fetch('/api/posts?status=pending');
    const data = await res.json();
    const posts = data.posts || [];
    updateQueueBadge(posts.length);

    if (posts.length === 0) {
      feed.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🎉</div>
          <h3>Approval Queue is Clear</h3>
          <p>No posts currently paused at the human review checkpoint. Generate a new campaign to see it here!</p>
        </div>`;
      return;
    }

    feed.innerHTML = '';
    posts.forEach(post => {
      feed.appendChild(renderApprovalCard(post));
    });
  } catch (err) {
    feed.innerHTML = `<div class="empty-state"><p style="color:var(--accent-rose)">Failed to load queue: ${err.message}</p></div>`;
  }
}

function renderApprovalCard(post) {
  const card = document.createElement('div');
  card.className = 'approval-card';
  card.id = `card-${post.thread_id}`;

  const platforms = post.platforms || Object.keys(post.drafts || {});
  const firstPlatform = platforms[0] || 'twitter';

  let tabsHtml = platforms.map((p, idx) => `
    <button class="preview-tab-btn ${idx === 0 ? 'active' : ''}" data-thread="${post.thread_id}" data-platform="${p}">
      ${p.toUpperCase()}
    </button>
  `).join('');

  let initialText = post.drafts[firstPlatform] || 'No draft generated.';
  let reviewData = post.review_feedback[firstPlatform] || { score: 85, feedback: ['Verified safe.'] };

  card.innerHTML = `
    <div class="approval-card-top">
      <div class="approval-topic-box">
        <h4>${escapeHtml(post.topic)}</h4>
        <div class="approval-meta">
          <span>Created: ${new Date(post.created_at).toLocaleTimeString()}</span>
          <span>•</span>
          <span>Thread: <code>${post.thread_id.substring(0, 8)}</code></span>
        </div>
      </div>
      <div class="hitl-banner">
        <span>⏸️ LangGraph Breakpoint Active</span>
      </div>
    </div>

    <div class="preview-tabs">
      ${tabsHtml}
    </div>

    <div class="post-mockup" id="mockup-${post.thread_id}">${escapeHtml(initialText)}</div>

    <div class="review-critique-box" id="critique-${post.thread_id}">
      <span class="score-badge">Virality Score: ${reviewData.score || 85}/100</span>
      <p style="margin-top:4px; color:var(--text-muted); font-size:0.8rem;">
        ${(reviewData.feedback || []).join(' ')}
      </p>
    </div>

    <div class="approval-actions">
      <button class="btn btn-outline edit-btn" data-thread="${post.thread_id}" data-platform="${firstPlatform}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
        <span>Edit Draft</span>
      </button>

      <button class="btn btn-danger reject-btn" data-thread="${post.thread_id}">
        <span>Reject</span>
      </button>

      <button class="btn btn-secondary schedule-action-btn" data-thread="${post.thread_id}">
        <span>Approve & Schedule</span>
      </button>

      <button class="btn btn-success publish-action-btn" data-thread="${post.thread_id}">
        <span>Approve & Publish Now</span>
      </button>
    </div>
  `;

  // Attach platform tab switcher listeners
  card.querySelectorAll('.preview-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      card.querySelectorAll('.preview-tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const plat = btn.getAttribute('data-platform');
      const text = post.drafts[plat] || '';
      const critique = post.review_feedback[plat] || { score: 80, feedback: [] };

      card.querySelector(`#mockup-${post.thread_id}`).textContent = text;
      card.querySelector(`#critique-${post.thread_id}`).innerHTML = `
        <span class="score-badge">Virality Score: ${critique.score || 80}/100</span>
        <p style="margin-top:4px; color:var(--text-muted); font-size:0.8rem;">
          ${(critique.feedback || []).join(' ')}
        </p>
      `;

      card.querySelector('.edit-btn').setAttribute('data-platform', plat);
    });
  });

  // Action: Approve & Publish Now
  card.querySelector('.publish-action-btn').addEventListener('click', async () => {
    await resumeWorkflow(post.thread_id, 'approved', '', null, card);
  });

  // Action: Approve & Schedule
  card.querySelector('.schedule-action-btn').addEventListener('click', async () => {
    const defaultTime = new Date(Date.now() + 3600 * 1000).toISOString().slice(0, 16);
    const chosenTime = prompt('Enter scheduled dispatch time (YYYY-MM-DDTHH:MM):', defaultTime);
    if (chosenTime) {
      await resumeWorkflow(post.thread_id, 'approved', 'Scheduled by reviewer', chosenTime, card);
    }
  });

  // Action: Reject
  card.querySelector('.reject-btn').addEventListener('click', async () => {
    const reason = prompt('Reason for rejection (optional):', 'Topic not aligned with current campaign goals.');
    if (reason !== null) {
      await resumeWorkflow(post.thread_id, 'rejected', reason, null, card);
    }
  });

  // Action: Edit
  card.querySelector('.edit-btn').addEventListener('click', (e) => {
    const plat = e.currentTarget.getAttribute('data-platform');
    openEditModal(post, plat);
  });

  return card;
}

async function resumeWorkflow(threadId, action, feedback, scheduledTime, cardElement) {
  if (cardElement) {
    cardElement.style.opacity = '0.5';
    cardElement.style.pointerEvents = 'none';
  }

  try {
    const res = await fetch(`/api/posts/${threadId}/resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action,
        feedback: feedback || '',
        scheduled_time: scheduledTime || null
      })
    });

    const data = await res.json();
    if (!data.success) throw new Error(data.detail || 'Resume failed');

    showToast(`Workflow resumed: ${action.toUpperCase()}`);
    loadApprovalQueue();
    loadScheduleFeed();
  } catch (err) {
    showToast('Failed to resume: ' + err.message, true);
    if (cardElement) {
      cardElement.style.opacity = '1';
      cardElement.style.pointerEvents = 'auto';
    }
  }
}

// 4. Modal Editing
function openEditModal(post, platform) {
  editingPostThread = post.thread_id;
  editingPlatform = platform;

  const modal = document.getElementById('editModal');
  const modalPlatform = document.getElementById('modalPlatform');
  const modalText = document.getElementById('modalPostText');
  const modalCharCount = document.getElementById('modalCharCount');

  modalPlatform.value = platform.toUpperCase();
  modalText.value = post.drafts[platform] || '';
  modalCharCount.textContent = modalText.value.length;

  modalText.oninput = () => {
    modalCharCount.textContent = modalText.value.length;
  };

  modal.classList.add('active');
}

document.getElementById('closeModalBtn').onclick = () => document.getElementById('editModal').classList.remove('active');
document.getElementById('cancelModalBtn').onclick = () => document.getElementById('editModal').classList.remove('active');

document.getElementById('saveDraftModalBtn').onclick = async () => {
  if (!editingPostThread || !editingPlatform) return;
  const newText = document.getElementById('modalPostText').value;
  const note = document.getElementById('modalFeedback').value;

  try {
    const postRes = await fetch(`/api/posts/${editingPostThread}`);
    const postData = await postRes.json();
    const drafts = postData.post.drafts;
    drafts[editingPlatform] = newText;

    const res = await fetch(`/api/posts/${editingPostThread}/resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: 'modified',
        feedback: note || 'Human edited draft',
        drafts: drafts
      })
    });

    const data = await res.json();
    if (!data.success) throw new Error(data.detail);

    document.getElementById('editModal').classList.remove('active');
    showToast('Draft updated & authorized!');
    loadApprovalQueue();
    loadScheduleFeed();
  } catch (err) {
    showToast('Failed to update draft: ' + err.message, true);
  }
};

// 5. Content Schedule
async function loadScheduleFeed() {
  const container = document.getElementById('scheduleList');
  container.innerHTML = '<div class="empty-state"><p>Loading schedule...</p></div>';

  try {
    const res = await fetch('/api/posts');
    const data = await res.json();
    let posts = data.posts || [];

    if (currentFilter === 'scheduled') {
      posts = posts.filter(p => p.published_status === 'scheduled');
    } else if (currentFilter === 'published') {
      posts = posts.filter(p => p.published_status === 'published');
    }

    if (posts.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <h3>No Posts in Current View</h3>
          <p>Approved posts will appear here once scheduled or published.</p>
        </div>`;
      return;
    }

    container.innerHTML = '';
    posts.forEach(p => {
      const card = document.createElement('div');
      card.className = 'schedule-card';

      const isPublished = p.published_status === 'published';
      const isScheduled = p.published_status === 'scheduled';
      const isPending = p.approval_status === 'pending';

      let statusBadge = '';
      if (isPublished) statusBadge = '<span style="color:var(--accent-emerald)">✓ Published</span>';
      else if (isScheduled) statusBadge = `<span style="color:var(--accent-cyan)">⏰ Scheduled for ${p.scheduled_time || 'Next slot'}</span>`;
      else if (isPending) statusBadge = '<span style="color:var(--accent-amber)">⏸️ Awaiting Approval</span>';
      else statusBadge = '<span style="color:var(--accent-rose)">Rejected</span>';

      card.innerHTML = `
        <div class="schedule-left">
          <h4>${escapeHtml(p.topic)}</h4>
          <div class="schedule-meta">
            <span>Status: ${statusBadge}</span>
            <span>•</span>
            <span>Platforms: ${p.platforms.join(', ')}</span>
          </div>
        </div>
        <div class="schedule-right">
          ${isScheduled ? `
            <button class="btn btn-sm btn-outline publish-now-btn" data-id="${p.id}">
              Publish Now
            </button>` : ''}
        </div>
      `;

      if (isScheduled) {
        card.querySelector('.publish-now-btn').addEventListener('click', async () => {
          await forcePublish(p.id);
        });
      }

      container.appendChild(card);
    });

  } catch (err) {
    container.innerHTML = `<div class="empty-state"><p style="color:var(--accent-rose)">Error: ${err.message}</p></div>`;
  }
}

async function forcePublish(postId) {
  try {
    const res = await fetch(`/api/posts/${postId}/publish-now`, { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast('Post dispatched to social platforms!');
      loadScheduleFeed();
    }
  } catch (err) {
    showToast('Publish failed: ' + err.message, true);
  }
}

// Filter buttons in schedule
document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentFilter = btn.getAttribute('data-filter');
    loadScheduleFeed();
  });
});

// 6. Tools & Logs
async function loadToolLogs() {
  const feed = document.getElementById('toolLogsFeed');
  feed.innerHTML = '<p style="color:var(--text-dim); padding:10px;">Loading tool audit trail...</p>';

  try {
    const res = await fetch('/api/tools/logs');
    const data = await res.json();
    const logs = data.logs || [];

    if (logs.length === 0) {
      feed.innerHTML = '<p style="color:var(--text-dim); padding:10px;">No tools invoked yet.</p>';
      return;
    }

    feed.innerHTML = '';
    logs.forEach(l => {
      const entry = document.createElement('div');
      entry.className = 'log-entry';
      entry.innerHTML = `
        <div class="log-entry-header">
          <span>⚙️ ${escapeHtml(l.tool_name)}</span>
          <span style="color:var(--text-dim)">${new Date(l.invoked_at).toLocaleTimeString()}</span>
        </div>
        <div class="log-payload"><strong>Input:</strong> ${escapeHtml(l.input_args)}</div>
        <div class="log-payload" style="margin-top:4px;"><strong>Output:</strong> ${escapeHtml(l.output_result)}</div>
      `;
      feed.appendChild(entry);
    });
  } catch (err) {
    feed.innerHTML = `<p style="color:var(--accent-rose); padding:10px;">Error loading logs: ${err.message}</p>`;
  }
}

function initTools() {
  document.getElementById('refreshToolLogsBtn').onclick = loadToolLogs;
  document.getElementById('refreshApprovalBtn').onclick = loadApprovalQueue;

  document.getElementById('testTrendingToolBtn').onclick = async () => {
    showToast('Executing search_trending_topics tool...');
    try {
      const res = await fetch('/api/tools/trending', { method: 'POST' });
      const data = await res.json();
      showToast(`Fetched ${data.trends?.length || 0} trending tech topics!`);
      loadToolLogs();
    } catch (err) {
      showToast('Tool test failed: ' + err.message, true);
    }
  };
}

// 7. Settings
async function initSettings() {
  const form = document.getElementById('settingsForm');
  const keyInput = document.getElementById('geminiKeyInput');
  const toggleBtn = document.getElementById('toggleKeyVisibility');
  const modelSelect = document.getElementById('modelSelect');

  toggleBtn.onclick = () => {
    keyInput.type = keyInput.type === 'password' ? 'text' : 'password';
    toggleBtn.textContent = keyInput.type === 'password' ? 'Show' : 'Hide';
  };

  form.onsubmit = async (e) => {
    e.preventDefault();
    const gemini_api_key = keyInput.value.trim();
    const default_model = modelSelect.value;

    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gemini_api_key, default_model })
      });
      const data = await res.json();
      showToast(data.message || 'Settings updated!');
      loadSettings();
    } catch (err) {
      showToast('Save failed: ' + err.message, true);
    }
  };

  loadSettings();
}

async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    const data = await res.json();

    if (data.default_model) {
      document.getElementById('modelSelect').value = data.default_model;
      document.getElementById('modelNameText').textContent = data.default_model;
    }

    if (data.gemini_key_preview) {
      document.getElementById('geminiKeyInput').placeholder = data.gemini_key_preview;
    }

    // Render OAuth list
    const oauthContainer = document.getElementById('oauthConnectionsList');
    oauthContainer.innerHTML = '';
    const oauths = data.oauth_status || {};

    for (const [platform, config] of Object.entries(oauths)) {
      const item = document.createElement('div');
      item.className = 'oauth-item';
      item.innerHTML = `
        <div class="oauth-info">
          <h4>${platform.toUpperCase()} API Connector</h4>
          <p>${config.username} • Rate limit: ${config.rate_limit_remaining} calls/hr</p>
        </div>
        <span class="oauth-status-tag">Connected & Authorized</span>
      `;
      oauthContainer.appendChild(item);
    }

  } catch (err) {
    console.error('Settings load error:', err);
  }
}

// Helpers
async function loadQueueCount() {
  try {
    const res = await fetch('/api/posts?status=pending');
    const data = await res.json();
    const count = (data.posts || []).length;
    updateQueueBadge(count);
  } catch (e) {
    // silently ignore
  }
}

function updateQueueBadge(count) {
  const pill = document.getElementById('pendingCountPill');
  pill.textContent = count;
  pill.style.display = count > 0 ? 'inline-block' : 'none';
}

function resetPipelineVisuals() {
  ['node-start', 'node-generate', 'node-review', 'node-human', 'node-dispatch'].forEach(id => {
    const el = document.getElementById(id);
    el.className = 'node-box';
    if (id === 'node-human') el.classList.add('highlight-hitl');
  });
  document.getElementById('graphTerminal').innerHTML = '';
}

function setNodeStatus(nodeId, status) {
  const el = document.getElementById(nodeId);
  if (!el) return;
  el.classList.remove('running', 'waiting', 'completed');
  el.classList.add(status);
}

function appendLog(msg, type = 'normal') {
  const terminal = document.getElementById('graphTerminal');
  const line = document.createElement('div');
  line.className = `log-line ${type}`;
  line.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
  terminal.appendChild(line);
  terminal.scrollTop = terminal.scrollHeight;
}

function showToast(message, isError = false) {
  const toast = document.createElement('div');
  toast.style.cssText = `
    position: fixed;
    bottom: 24px;
    right: 24px;
    background: ${isError ? 'rgba(244, 63, 94, 0.95)' : 'rgba(99, 102, 241, 0.95)'};
    color: white;
    padding: 12px 20px;
    border-radius: 8px;
    font-size: 0.88rem;
    font-weight: 600;
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
    z-index: 9999;
    animation: fadeIn 0.2s ease-out;
  `;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function loadInitialData() {
  loadQueueCount();
}
