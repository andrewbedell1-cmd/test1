'use strict';

// ── Constants ──────────────────────────────────────────────────────
var AVATAR_COLORS = [
  '#7B68EE', '#3b82f6', '#22c55e', '#f59e0b',
  '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899'
];

var PROJECT_PALETTES = [
  { bg: '#ede9fe', fg: '#6d28d9' },
  { bg: '#dbeafe', fg: '#1e40af' },
  { bg: '#d1fae5', fg: '#065f46' },
  { bg: '#fef3c7', fg: '#92400e' },
  { bg: '#fce7f3', fg: '#9d174d' },
  { bg: '#e0f2fe', fg: '#0369a1' },
  { bg: '#f0fdf4', fg: '#166534' }
];

var currentTaskId = null;

// ── Helpers ────────────────────────────────────────────────────────
function hashStr(str) {
  var h = 0;
  for (var i = 0; i < str.length; i++) {
    h = (h * 31 + str.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

function getAvatarColor(name) {
  return AVATAR_COLORS[hashStr(name) % AVATAR_COLORS.length];
}

function getProjectPalette(project) {
  return PROJECT_PALETTES[hashStr(project) % PROJECT_PALETTES.length];
}

function formatDueDate(dateStr) {
  if (!dateStr) return null;
  var parts = dateStr.split('-');
  var date = new Date(
    parseInt(parts[0], 10),
    parseInt(parts[1], 10) - 1,
    parseInt(parts[2], 10)
  );
  var today = new Date();
  today.setHours(0, 0, 0, 0);
  var diff = Math.round((date - today) / 86400000);

  if (diff < 0)  return { text: Math.abs(diff) + 'd overdue', cls: 'overdue' };
  if (diff === 0) return { text: 'Due today',  cls: 'due-today' };
  if (diff === 1) return { text: 'Tomorrow',   cls: 'due-soon'  };
  if (diff <= 7)  return { text: 'In ' + diff + ' days', cls: 'due-soon' };

  var months = ['Jan','Feb','Mar','Apr','May','Jun',
                'Jul','Aug','Sep','Oct','Nov','Dec'];
  return { text: months[date.getMonth()] + ' ' + date.getDate(), cls: '' };
}

// ── UI initialisation ──────────────────────────────────────────────
function initUI() {
  // Avatar colours
  document.querySelectorAll('.avatar[data-name]').forEach(function(el) {
    var name = el.getAttribute('data-name') || '';
    if (name) el.style.background = getAvatarColor(name);
  });

  // Project badge colours
  document.querySelectorAll('.project-badge[data-project]').forEach(function(el) {
    var project = el.getAttribute('data-project') || '';
    if (project) {
      var palette = getProjectPalette(project);
      el.style.background = palette.bg;
      el.style.color = palette.fg;
    }
  });

  // Friendly due-date labels
  document.querySelectorAll('.due-date[data-date]').forEach(function(el) {
    var dateStr = el.getAttribute('data-date');
    if (!dateStr) return;
    var result = formatDueDate(dateStr);
    if (result) {
      el.textContent = result.text;
      if (result.cls) el.classList.add(result.cls);
    }
  });
}

// ── Modal helpers ──────────────────────────────────────────────────
function openAddModal() {
  currentTaskId = null;
  document.getElementById('modal-title').textContent = 'New Task';
  document.getElementById('task-form').reset();
  document.getElementById('task-id').value = '';
  document.getElementById('form-status').value = 'Upcoming';
  document.getElementById('delete-btn').style.display = 'none';
  document.getElementById('modal-overlay').classList.add('active');
  document.getElementById('form-title').focus();
}

function openEditModal(taskId) {
  fetch('/tasks/' + taskId)
    .then(function(res) {
      if (!res.ok) throw new Error('Not found');
      return res.json();
    })
    .then(function(task) {
      currentTaskId = taskId;
      document.getElementById('modal-title').textContent = 'Edit Task';
      document.getElementById('task-id').value        = task.id;
      document.getElementById('form-title').value     = task.title    || '';
      document.getElementById('form-notes').value     = task.notes    || '';
      document.getElementById('form-project').value   = task.project  || '';
      document.getElementById('form-status').value    = task.status   || 'Upcoming';
      document.getElementById('form-due-date').value  = task.due_date || '';
      document.getElementById('form-assignee').value  = task.assignee || '';
      document.getElementById('delete-btn').style.display = 'inline-flex';
      document.getElementById('modal-overlay').classList.add('active');
      document.getElementById('form-title').focus();
    })
    .catch(function() {
      alert('Could not load task details.');
    });
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('active');
  currentTaskId = null;
}

// ── Form submit ────────────────────────────────────────────────────
function handleSubmit(event) {
  event.preventDefault();

  var data = {
    title:    document.getElementById('form-title').value.trim(),
    notes:    document.getElementById('form-notes').value.trim(),
    project:  document.getElementById('form-project').value.trim(),
    status:   document.getElementById('form-status').value,
    due_date: document.getElementById('form-due-date').value,
    assignee: document.getElementById('form-assignee').value.trim()
  };

  if (!data.title) {
    document.getElementById('form-title').focus();
    return;
  }

  var url    = currentTaskId ? '/tasks/' + currentTaskId : '/tasks';
  var method = currentTaskId ? 'PUT' : 'POST';

  fetch(url, {
    method: method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })
  .then(function(res) {
    if (!res.ok) throw new Error('Save failed');
    closeModal();
    location.reload();
  })
  .catch(function() {
    alert('Could not save the task. Please try again.');
  });
}

// ── Delete ─────────────────────────────────────────────────────────
function deleteTask() {
  if (!currentTaskId) return;
  if (!confirm('Delete this task? This cannot be undone.')) return;

  fetch('/tasks/' + currentTaskId, { method: 'DELETE' })
    .then(function(res) {
      if (!res.ok) throw new Error('Delete failed');
      closeModal();
      location.reload();
    })
    .catch(function() {
      alert('Could not delete the task.');
    });
}

// ── Keyboard shortcut ──────────────────────────────────────────────
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') closeModal();
});

// ── Boot ───────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', initUI);
