/* drive.js — 사용자 화면. 외부 라이브러리 없습니다.
 *
 * 퍼블 산출물(`foreversoft-drive/js/drive.js`)의 **샘플 데이터를 서버로 바꾼 것**입니다.
 * 렌더 함수 이름(renderFolders · renderFiles · renderChips · renderPanel)과 클래스는
 * 산출물 그대로 두었습니다 — 다음 산출물이 오면 이 파일과 diff 를 떠서 바뀐 줄만 옮기면
 * 됩니다. 산출물에 없던 것은 아래 '대화' 묶음부터이고, 그쪽은 이전 사용자 화면(chat.js)
 * 에서 옮겨 왔습니다.
 *
 * 서버와 닿는 자리는 여섯 군데뿐입니다:
 *   loadDrive()      GET  /api/drive            폴더(프로젝트) · 자료 목록 · 보관량
 *   loadModels()     GET  /api/models           고를 수 있는 답변 모델(운영은 빈 목록)
 *   openStream()     GET  /api/chat/stream      답변 흘려보내기(SSE)
 *   sendFeedback()   POST /api/feedback         👍/👎
 *   sendSupport()    POST /api/support          담당자 문의 → 접수번호
 *   uploadBatch()    POST /api/admin/docs/upload  자료 올리기(studio + 관리자 로그인)
 */
(function () {
  'use strict';

  var STUDIO = document.body.getAttribute('data-mode') === 'studio';
  /* `추론 과정 보기` 를 내줄지. 서버가 `<body data-reasoning>` 으로 알려 줍니다 —
     켜진 뒤 물어보면 못 쓰는 체크박스가 잠깐 보였다 사라집니다. */
  var REASONING = document.body.getAttribute('data-reasoning') === 'on';
  /* 화면을 열었을 때 `AI 답변` 을 켜 둘지. 서버가 알려 줍니다 — 켜면 **검수된 답변 경로를
     건너뜁니다**(QA 인덱스를 보지 않습니다). 설정이라 되돌릴 수 있습니다. */
  var AI_DEFAULT = document.body.getAttribute('data-ai-default') === 'on';

  /* 문서 종류 — 색은 산출물 값 그대로. `md` 는 우리가 더했습니다(원본 없이 본문만). */
  var KINDS = {
    pdf: { label: 'PDF', color: '#E5484D' }, ppt: { label: 'PPT', color: '#D9622B' },
    doc: { label: 'DOC', color: '#2F6FDB' }, xls: { label: 'XLS', color: '#1F8A55' },
    hwp: { label: 'HWP', color: '#1A8BB5' }, zip: { label: 'ZIP', color: '#6B7685' },
    img: { label: 'IMG', color: '#7A5BC7' }, md: { label: 'MD', color: '#8C98A8' },
    etc: { label: 'FILE', color: '#98A2B3' }
  };
  var KIND_ORDER = ['pdf', 'ppt', 'doc', 'xls', 'hwp', 'zip', 'img', 'md', 'etc'];
  var KIND_NAMES = { pdf: 'PDF', ppt: 'PPT', doc: 'DOC', xls: 'XLS', hwp: 'HWP', zip: 'ZIP', img: '이미지', md: '본문만', etc: '기타' };

  /* 한 요청에 보내는 상한. 서버도 20건까지 받습니다(doc_upload.MAX_FILES_PER_REQUEST).
     용량으로도 묶는 이유: 20건이 다 발표자료면 한 요청이 수백 MB 가 됩니다. */
  var UP_FILES = 20, UP_BYTES = 20 * 1024 * 1024;

  var state = {
    projects: [], docs: [], models: [], llmDown: false,
    projectId: null,           /* 고른 프로젝트. null 이면 전체 */
    selKinds: {}, selProjects: {},
    draftKinds: {}, draftProjects: {},
    sort: 'date', limit: 10,
    /* 'search' = AI 지식 검색(전체 범위, 목록 없음) · 'browse' = 프로젝트 둘러보기 */
    view: 'search',
    aiOn: AI_DEFAULT, model: null, reasoning: false,
    streaming: false, current: null, stick: true
  };

  /* ================= 도우미 ================= */
  function $(id) { return document.getElementById(id); }
  function q(root, sel) { return root.querySelector(sel); }
  function tpl(id) { return $(id).content.firstElementChild.cloneNode(true); }
  function show(el, on) { if (!el) return; if (on) el.removeAttribute('hidden'); else el.setAttribute('hidden', ''); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function keys(o) { return Object.keys(o); }
  function count(o) { return keys(o).length; }
  function sec(ms) { return Math.max(0, Math.round(ms / 1000)); }
  function fill(root, data) {
    var nodes = [].slice.call(root.querySelectorAll('[data-bind]'));
    if (root.hasAttribute && root.hasAttribute('data-bind')) nodes.unshift(root);
    nodes.forEach(function (n) {
      var k = n.getAttribute('data-bind');
      if (Object.prototype.hasOwnProperty.call(data, k)) n.textContent = data[k] == null ? '' : data[k];
    });
    return root;
  }
  function fmtSize(bytes) {
    if (bytes >= 1073741824) return (bytes / 1073741824).toFixed(1) + ' GB';
    if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB';
    if (bytes >= 1024) return Math.round(bytes / 1024) + ' KB';
    return bytes + ' B';
  }
  function fmtDate(iso) { return String(iso || '').replace(/-/g, '.'); }
  function dayNum(iso) { return Math.round(Date.parse(iso + 'T00:00:00Z') / 864e5); }
  function isRecent(iso) { return iso && dayNum(new Date().toISOString().slice(0, 10)) - dayNum(iso) < 7; }
  function projectOf(id) {
    return state.projects.filter(function (p) { return p.project_id === id; })[0] || null;
  }
  function docOf(id) {
    return state.docs.filter(function (d) { return d.doc_id === id; })[0] || null;
  }
  function fileUrl(doc) {
    return '/api/drive/' + encodeURIComponent(doc.doc_id) + '/file' +
      (doc.project ? '?project=' + encodeURIComponent(doc.project) : '');
  }
  function modelName() {
    if (state.model) return state.model;
    var d = state.models.filter(function (m) { return m.default; })[0] || state.models[0];
    return d ? d.name : '';
  }
  function aiActive() { return state.aiOn && !state.llmDown; }

  /* ================= 서버 =================
     여기 여섯 함수 바깥에서는 서버를 부르지 않습니다. */

  function getJson(url) {
    return fetch(url, { headers: { 'Accept': 'application/json' } }).then(function (r) {
      if (!r.ok) throw new Error(url + ' → ' + r.status);
      return r.json();
    });
  }
  function postJson(url, body) {
    return fetch(url, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
    }).then(function (r) {
      if (!r.ok) throw new Error(url + ' → ' + r.status);
      return r.json();
    });
  }

  function loadDrive() { return getJson('/api/drive'); }

  /* **빈 목록도 '없음'입니다** — 운영에는 LLM 이 없고, 화면은 그때 AI 답변 스위치를 잠가야
     합니다. 서버가 404 가 아니라 빈 배열을 주는 이유는 '고장'과 '원래 없음'을 같은 모양으로
     두지 않기 위해서입니다(app/api/chat_stream.py). */
  function loadModels() { return getJson('/api/models'); }

  /* SSE. 서버가 `thinking` · `answer` · `sources` · `done` 을 흘려보냅니다. */
  function openStream(req, handlers) {
    var qs = new URLSearchParams({
      question: req.question, topic: '', ai: req.ai ? 'true' : 'false',
      reasoning: req.reasoning ? 'true' : 'false', model: req.model || ''
    });
    /* 고른 프로젝트는 쿼리로 보냅니다 — EventSource 는 헤더를 못 붙입니다.
       비워 두면 서버가 가장 가까운 자료가 있는 프로젝트를 고릅니다(app/pipeline/scope.py). */
    if (req.project) qs.set('project', req.project);

    var es = new EventSource('/api/chat/stream?' + qs.toString());
    var closed = false;
    ['thinking', 'answer', 'sources', 'done'].forEach(function (name) {
      es.addEventListener(name, function (e) {
        var data = {};
        try { data = JSON.parse(e.data); } catch (err) { data = {}; }
        if (handlers[name]) handlers[name](data);
        if (name === 'done') { closed = true; es.close(); }
      });
    });
    es.addEventListener('error', function (e) {
      var data = null;
      try { data = JSON.parse(e.data); } catch (err) { data = null; }
      if (data && handlers.error) { closed = true; es.close(); handlers.error(new Error(data.message)); }
    });
    /* `done` 을 받고 닫은 뒤의 error 는 무시합니다 — EventSource 는 닫을 때도 한 번 냅니다. */
    es.onerror = function () {
      if (closed) return;
      closed = true; es.close();
      if (handlers.error) handlers.error(new Error('연결이 끊어졌습니다'));
    };
    return { close: function () { closed = true; es.close(); } };
  }

  /* 신고는 **그 질문이 기록된 팩**으로 보내야 합니다. 프로젝트를 빼면 서버가 기본
     프로젝트에 쌓아, 검수 화면의 `사용자 신고` 에 아무것도 안 올라옵니다. */
  function sendFeedback(logId, vote, reason, project) {
    return postJson('/api/feedback' + (project ? '?project=' + encodeURIComponent(project) : ''),
      { log_id: logId, vote: vote, reason: reason || null });
  }
  function sendSupport(question, project) {
    return postJson('/api/support' + (project ? '?project=' + encodeURIComponent(project) : ''),
      { question: question });
  }
  function uploadBatch(items, projectId, overwrite) {
    var form = new FormData();
    items.forEach(function (f) { form.append('files', f, f.name); });
    items.forEach(function (f) { form.append('paths', f.webkitRelativePath || f.name); });
    form.append('overwrite', overwrite ? 'true' : 'false');
    var url = '/api/admin/docs/upload' + (projectId ? '?project=' + encodeURIComponent(projectId) : '');
    return fetch(url, { method: 'POST', body: form }).then(function (r) {
      if (r.status === 401 || r.status === 403) throw new Error('auth');
      if (!r.ok) throw new Error('자료를 올리지 못했습니다 (' + r.status + ')');
      return r.json();
    });
  }

  /* ================= 마크다운 =================
     `admin.js` 의 `renderMarkdown()` 과 **같은 규칙**이어야 합니다. 검수 미리보기와
     사용자가 보는 답변이 달라지면 검수가 의미를 잃습니다(CLAUDE.md). */
  function inline(s) {
    return esc(s).replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/`([^`]+)`/g, '<code>$1</code>');
  }
  /* 제목이 섞인 덩이는 **줄 단위로** 가릅니다 — 문서는 제목 바로 아래에 본문을 붙여 쓰는
     일이 흔해서, 덩이 전체를 한 종류로 보면 `## 제목` 이 본문에 섞여 그대로 보입니다. */
  function heads(lines) {
    var out = '', buf = [];
    function flush() {
      if (buf.length) { out += '<p>' + buf.map(inline).join('<br>') + '</p>'; buf = []; }
    }
    lines.forEach(function (l) {
      var m = /^(#{1,6})\s+(.*)$/.exec(l);
      if (m) { flush(); var lv = m[1].length; out += '<h' + lv + '>' + inline(m[2]) + '</h' + lv + '>'; }
      else buf.push(l);
    });
    flush();
    return out;
  }
  /* **`admin.js` 의 `renderMarkdown()` 과 규칙이 같아야 합니다**(CLAUDE.md). 검수자가
     보는 미리보기와 사용자가 보는 답변이 달라지면 검수가 의미를 잃습니다. 빈 줄 거르기와
     목록 판정(첫 줄로 본다)까지 같은 모양으로 맞춰 두었습니다 — 2026-10-06 에 그 둘이
     달라서 같은 글이 한쪽에서는 목록, 한쪽에서는 `- ` 가 그대로 보였습니다. */
  function md(src) {
    return String(src || '').replace(/\r\n/g, '\n').split(/\n{2,}/).map(function (b) {
      var lines = b.split('\n').filter(function (l) { return l.trim() !== ''; });
      if (!lines.length) return '';
      if (lines.some(function (l) { return /^#{1,6}\s/.test(l); })) return heads(lines);
      if (/^\s*\d+\.\s/.test(lines[0]))
        return '<ol>' + lines.map(function (l) { return '<li>' + inline(l.replace(/^\s*\d+\.\s/, '')) + '</li>'; }).join('') + '</ol>';
      if (/^\s*[-*]\s/.test(lines[0]))
        return '<ul>' + lines.map(function (l) { return '<li>' + inline(l.replace(/^\s*[-*]\s/, '')) + '</li>'; }).join('') + '</ul>';
      if (lines[0].trim().charAt(0) === '|') {
        var rows = lines.filter(function (l) { return !/^\|[\s|:-]+\|?$/.test(l.trim()); })
          .map(function (l) { return l.trim().replace(/^\||\|$/g, '').split('|').map(function (c) { return c.trim(); }); });
        return '<table><thead><tr>' + rows[0].map(function (c) { return '<th>' + inline(c) + '</th>'; }).join('') + '</tr></thead><tbody>' +
          rows.slice(1).map(function (r) { return '<tr>' + r.map(function (c) { return '<td>' + inline(c) + '</td>'; }).join('') + '</tr>'; }).join('') + '</tbody></table>';
      }
      return '<p>' + lines.map(inline).join('<br>') + '</p>';
    }).join('');
  }
  var CURSOR = '<span class="cursor" aria-hidden="true">&nbsp;</span>';
  function withCursor(html) {
    if (!html) return '<p>' + CURSOR + '</p>';
    var re = /<\/(p|li|td|th)>/g, m, last = null;
    while ((m = re.exec(html))) last = m;
    return last ? html.slice(0, last.index) + CURSOR + html.slice(last.index) : html + CURSOR;
  }

  /* ================= 폴더(프로젝트) 카드 ================= */
  var foldersEl = $('folders');

  var folderArt = '<svg class="fold" viewBox="0 0 172 80" aria-hidden="true">' +
    '<path d="M12 2h40c3.4 0 5.6 1.2 7.6 3.6L64 11h96a8 8 0 0 1 8 8v61H4V10a8 8 0 0 1 8-8z" fill="url(#fold-back)"/>' +
    '<rect x="16" y="8" width="142" height="46" rx="3" fill="#F9FAFB" transform="rotate(-2 87 31)"/>' +
    '<rect x="13" y="12" width="148" height="46" rx="3" fill="#fff"/>' +
    '<path d="M4 30a8 8 0 0 1 8-8h99c4.4 0 6.6 1.4 9 4.4l3.6 4.6c2.2 2.8 4.4 3.6 8 3.6H160a8 8 0 0 1 8 8v38H4z" fill="url(#fold-back)" opacity=".55" transform="translate(0 -1.6)"/>' +
    '<path d="M4 30a8 8 0 0 1 8-8h99c4.4 0 6.6 1.4 9 4.4l3.6 4.6c2.2 2.8 4.4 3.6 8 3.6H160a8 8 0 0 1 8 8v38H4z" fill="url(#fold-front)"/></svg>';

  function fileIcon(kind) {
    var k = KINDS[kind] || KINDS.etc;
    return '<svg viewBox="0 0 40 48" aria-label="' + k.label + ' 파일">' +
      '<path d="M7 1.5h19l11 11V44a2.5 2.5 0 0 1-2.5 2.5h-27A2.5 2.5 0 0 1 5 44V4a2.5 2.5 0 0 1 2-2.5z" fill="#fff" stroke="#D3DAE6" stroke-width="1.2"/>' +
      '<path d="M26 1.5V10a2.5 2.5 0 0 0 2.5 2.5H37" fill="#EDF1F7" stroke="#D3DAE6" stroke-width="1.2" stroke-linejoin="round"/>' +
      '<path d="M11 33h20M11 38h14" stroke="#E1E6EE" stroke-width="2" stroke-linecap="round"/>' +
      '<rect x="0" y="16" width="30" height="13" rx="3" fill="' + k.color + '"/>' +
      '<text x="15" y="25.6" text-anchor="middle" font-family="Pretendard,Arial,sans-serif" font-size="8.6" font-weight="800" fill="#fff" letter-spacing=".3">' + k.label + '</text></svg>';
  }

  function renderFolders() {
    foldersEl.innerHTML = state.projects.filter(inView).map(function (p) {
      var on = p.project_id === state.projectId;
      return '<a class="fcard' + (on ? ' selected' : '') + '" href="#" draggable="false" data-folder="' +
        esc(p.project_id) + '" aria-pressed="' + on + '">' +
        '<span class="tick" aria-hidden="true"><svg class="i"><use href="#ic-check"/></svg></span>' + folderArt +
        '<h3>' + esc(p.name) + '</h3>' +
        '<div class="n">자료 ' + p.doc_count + '건</div>' +
        '<div class="sz">' + fmtSize(p.bytes) + '</div></a>';
    }).join('');
    /* 프로젝트 만들기·수정은 **관리자 화면**에 있습니다. 운영 행위라 자료를 보러 온
       화면에 둘 자리가 아닙니다(2026-10-07). 서버는 처음부터 관리자 인증 뒤였습니다. */
    $('folderCount').textContent = state.projects.filter(inView).length + '개';
    updateArrows();
  }

  /* 좌우 스와이프: 터치는 기본 스크롤, 마우스는 끌어서 이동 (산출물 그대로) */
  var down = false, moved = false, startX = 0, startLeft = 0;
  foldersEl.addEventListener('pointerdown', function (e) {
    if (e.pointerType !== 'mouse') return;
    down = true; moved = false; startX = e.clientX; startLeft = foldersEl.scrollLeft;
  });
  window.addEventListener('pointermove', function (e) {
    if (!down) return;
    var dx = e.clientX - startX;
    if (!moved && Math.abs(dx) > 5) { moved = true; foldersEl.classList.add('dragging'); }
    if (moved) foldersEl.scrollLeft = startLeft - dx;
  });
  window.addEventListener('pointerup', function () {
    if (!down) return;
    down = false;
    if (moved) {
      foldersEl.classList.remove('dragging');
      var step = 208, target = Math.round(foldersEl.scrollLeft / step) * step;
      foldersEl.scrollTo({ left: target, behavior: 'smooth' });
    }
  });
  foldersEl.addEventListener('click', function (e) {
    if (moved) { e.preventDefault(); e.stopPropagation(); moved = false; }
  }, true);

  foldersEl.addEventListener('click', function (e) {
    var card = e.target.closest('.fcard[data-folder]');
    if (!card) return;
    e.preventDefault();
    selectProject(card.dataset.folder === state.projectId ? null : card.dataset.folder);
  });
  function selectProject(id) {
    state.projectId = id;
    state.limit = pageSize();
    showScope();
    renderNavProjects();
    renderFolders(); renderChips(); renderFiles();
    renderSuggest();      /* 추천 질문도 그 프로젝트 것으로 바뀝니다 */
  }

  var prev = $('prev'), next = $('next');
  function updateArrows() {
    prev.disabled = foldersEl.scrollLeft <= 2;
    next.disabled = foldersEl.scrollLeft + foldersEl.clientWidth >= foldersEl.scrollWidth - 2;
  }
  prev.addEventListener('click', function () { foldersEl.scrollBy({ left: -foldersEl.clientWidth * 0.8 }); });
  next.addEventListener('click', function () { foldersEl.scrollBy({ left: foldersEl.clientWidth * 0.8 }); });
  foldersEl.addEventListener('scroll', updateArrows, { passive: true });
  window.addEventListener('resize', updateArrows);

  /* ================= 자료 목록 ================= */
  var listEl = $('list');
  var pageSizeEl = $('pageSize');
  function pageSize() { return pageSizeEl.value === 'all' ? Infinity : Number(pageSizeEl.value); }

  function visibleDocs() {
    return state.docs.filter(function (d) {
      if (roleOf(d.project) !== viewRole()) return false;
      if (state.projectId && d.project !== state.projectId) return false;
      if (count(state.selKinds) && !state.selKinds[d.kind]) return false;
      if (count(state.selProjects) && !state.selProjects[d.project]) return false;
      return true;
    });
  }

  function renderFiles() {
    var rows = visibleDocs();
    rows.sort(function (a, b) {
      if (state.sort === 'name') return a.title.localeCompare(b.title, 'ko');
      if (state.sort === 'size') return b.bytes - a.bytes;
      return String(b.updated).localeCompare(String(a.updated)) || a.title.localeCompare(b.title, 'ko');
    });
    var total = rows.length;
    rows = rows.slice(0, state.limit);

    listEl.innerHTML = rows.map(function (d) {
      var tags = '';
      /* 색인 안 된 자료를 **눈에 보이게** 둡니다. 숨기면 "올렸는데 AI가 모른다"의 원인을
         사람이 짚을 수 없습니다. */
      if (!d.indexed) tags += '<span class="tag t-raw">색인 안 됨</span>';
      if (isRecent(d.updated)) tags += '<span class="tag t-new">최근 7일</span>';
      if (d.qa_count) tags += '<span class="tag t-qa">QA ' + d.qa_count + '건</span>';
      return '<article class="item' + (d.indexed ? '' : ' is_raw') + '" data-doc="' + esc(d.doc_id) + '">' +
        '<div class="thumb">' + fileIcon(d.kind) + '</div>' +
        '<div class="info"><div class="name-row"><span class="name">' + esc(d.title) + '</span>' + tags + '</div>' +
        '<div class="meta"><span>' + esc(d.project_name) + '</span><i></i><span>' +
        (d.indexed ? d.chunk_count + '개 절' : '본문 없음') + '</span></div></div>' +
        '<div class="side"><div class="size">' + fmtSize(d.bytes) + '</div>' +
        '<div class="when">' + fmtDate(d.updated) + '</div></div>' +
        '<a class="dl" href="' + esc(fileUrl(d)) + '" download title="내려받기" aria-label="' +
        esc(d.title) + ' 내려받기"><svg class="i"><use href="#ic-download"/></svg></a></article>';
    }).join('');

    var left = total - rows.length;
    show($('moreWrap'), left > 0);
    if (left > 0) $('moreText').innerHTML = '더보기 <small>' + rows.length + ' / ' + total + '</small>';

    var emptyEl = $('empty');
    emptyEl.style.display = rows.length ? 'none' : 'block';
    if (!state.projects.filter(inView).length) {
      emptyEl.textContent = state.view === 'library'
        ? '아직 자료실이 없습니다. 관리자 설정 → 프로젝트에서 용도를 \'자료실\' 로 만드세요.'
        : '아직 프로젝트가 없습니다. 관리자 설정 → 프로젝트에서 만드세요.';
    } else {
      emptyEl.textContent = total
        ? '조건에 맞는 자료가 없습니다.'
        : (STUDIO ? '아직 자료가 없습니다. 아래 영역에 파일을 끌어다 놓으세요.'
                  : '아직 자료가 없습니다. 관리자가 자료를 등록하면 보입니다.');
    }

    var p = projectOf(state.projectId);
    var scope = p
      ? '<span class="scope sel"><svg class="i"><use href="#ic-folder"/></svg>' + esc(p.name) +
        '<button type="button" class="scope-x" aria-label="전체 보기"><svg class="i"><use href="#ic-x"/></svg></button></span>'
      : '<span class="scope">전체</span>';
    $('resultText').innerHTML = scope + '<b>' + total + '</b>건의 자료가 있습니다';
  }

  listEl.addEventListener('click', function (e) {
    if (e.target.closest('.dl')) return;          /* 내려받기는 <a> 가 그대로 처리합니다 */
    var card = e.target.closest('.item');
    if (card) openDoc(card.dataset.doc);
  });
  $('sort').addEventListener('change', function (e) { state.sort = e.target.value; state.limit = pageSize(); renderFiles(); });
  pageSizeEl.addEventListener('change', function () { state.limit = pageSize(); renderFiles(); });
  $('moreBtn').addEventListener('click', function () { state.limit += pageSize(); renderFiles(); });
  $('resultText').addEventListener('click', function (e) { if (e.target.closest('.scope-x')) selectProject(null); });

  /* ================= 필터 ================= */
  var filterWrap = $('filterWrap'), filterBtn = $('filterBtn');

  function renderPanel() {
    var used = {};
    state.docs.forEach(function (d) { used[d.kind] = true; });
    $('fpTypes').innerHTML = KIND_ORDER.filter(function (k) { return used[k]; }).map(function (k) {
      return '<button type="button" class="fp-opt" data-type="' + k + '" aria-pressed="' + !!state.draftKinds[k] + '">' +
        '<i class="dot" style="background:' + KINDS[k].color + '"></i>' + KIND_NAMES[k] + '</button>';
    }).join('') || '<button type="button" class="fp-opt" disabled>아직 없습니다</button>';

    $('fpFolders').innerHTML = state.projects.filter(inView).map(function (p) {
      return '<button type="button" class="fp-opt" data-folder="' + esc(p.project_id) + '" aria-pressed="' +
        !!state.draftProjects[p.project_id] + '"><svg class="i"><use href="#ic-folder"/></svg>' + esc(p.name) + '</button>';
    }).join('');
    updateApplyCount();
  }
  function updateApplyCount() {
    var n = state.docs.filter(function (d) {
      return (!count(state.draftKinds) || state.draftKinds[d.kind]) &&
        (!count(state.draftProjects) || state.draftProjects[d.project]) &&
        (!state.projectId || d.project === state.projectId);
    }).length;
    $('fpApply').innerHTML = '적용하기 <small>' + n + '건</small>';
  }
  function openPanel() {
    state.draftKinds = {}; keys(state.selKinds).forEach(function (k) { state.draftKinds[k] = true; });
    state.draftProjects = {}; keys(state.selProjects).forEach(function (k) { state.draftProjects[k] = true; });
    renderPanel();
    filterWrap.classList.add('open'); filterBtn.setAttribute('aria-expanded', 'true');
  }
  function closePanel() { filterWrap.classList.remove('open'); filterBtn.setAttribute('aria-expanded', 'false'); }
  filterBtn.addEventListener('click', function () {
    filterWrap.classList.contains('open') ? closePanel() : openPanel();
  });
  $('filterPanel').addEventListener('click', function (e) {
    var o = e.target.closest('.fp-opt');
    if (!o || o.disabled) return;
    var bag = o.dataset.type ? state.draftKinds : state.draftProjects;
    var key = o.dataset.type || o.dataset.folder;
    if (bag[key]) delete bag[key]; else bag[key] = true;
    o.setAttribute('aria-pressed', !!bag[key]);
    updateApplyCount();
  });
  $('fpReset').addEventListener('click', function (e) {
    e.stopPropagation(); state.draftKinds = {}; state.draftProjects = {}; renderPanel();
  });
  $('fpApply').addEventListener('click', function () {
    state.selKinds = state.draftKinds; state.selProjects = state.draftProjects;
    closePanel(); state.limit = pageSize(); renderChips(); renderFiles();
  });
  document.addEventListener('click', function (e) { if (!e.target.closest('#filterWrap')) closePanel(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closePanel(); });

  function renderChips() {
    var x = '<svg class="i"><use href="#ic-x"/></svg>';
    var html = '';
    KIND_ORDER.filter(function (k) { return state.selKinds[k]; }).forEach(function (k) {
      html += '<span class="chip"><button type="button" data-kind="type" data-key="' + k + '" aria-label="' +
        KIND_NAMES[k] + ' 조건 지우기">' + x + '</button><i class="dot" style="background:' + KINDS[k].color + '"></i>' + KIND_NAMES[k] + '</span>';
    });
    keys(state.selProjects).forEach(function (id) {
      var p = projectOf(id);
      html += '<span class="chip"><button type="button" data-kind="folder" data-key="' + esc(id) + '" aria-label="조건 지우기">' +
        x + '</button><svg class="i fold-ico"><use href="#ic-folder"/></svg>' + esc(p ? p.name : id) + '</span>';
    });
    $('chipList').innerHTML = html;
    var n = count(state.selKinds) + count(state.selProjects);
    var num = $('filterCount');
    num.textContent = n; num.style.display = n ? '' : 'none';
    $('clearAll').style.display = n ? '' : 'none';
  }
  $('chipList').addEventListener('click', function (e) {
    var b = e.target.closest('button[data-kind]');
    if (!b) return;
    if (b.dataset.kind === 'type') delete state.selKinds[b.dataset.key];
    if (b.dataset.kind === 'folder') delete state.selProjects[b.dataset.key];
    state.limit = pageSize(); renderChips(); renderFiles();
  });
  $('clearAll').addEventListener('click', function () {
    state.selKinds = {}; state.selProjects = {};
    state.limit = pageSize(); renderChips(); renderFiles();
  });

  /* ================= 토스트 ================= */
  var toastTimer = null;
  function toast(msg) {
    var el = $('toast');
    el.textContent = msg; el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.classList.remove('show'); }, 2800);
  }

  /* ================= 대화 =================
     산출물에는 없는 부분입니다. 이전 사용자 화면(chat.js)의 말풍선·스트리밍·경과 시간을
     이 디자인의 클래스로 옮겼습니다. */
  var aiForm = $('aiForm'), ansBody = $('ansBody');

  /* 결과 영역은 검색창 **아래의 따로 있는 블록**입니다. 검색창은 늘 같은 자리에 있습니다. */
  function panelOpen(on) { show($('aiAnswer'), on); }
  function scrollDown() { if (state.stick) ansBody.scrollTop = ansBody.scrollHeight; }
  ansBody.addEventListener('scroll', function () {
    state.stick = ansBody.scrollHeight - ansBody.scrollTop - ansBody.clientHeight < 48;
  });

  function renderSuggest() {
    /* 검색 화면은 전체 범위라 모든 프로젝트의 추천 질문을 섞습니다. */
    var p = projectOf(searchProject());
    var pool = p ? p.questions : state.projects.reduce(function (a, x) { return a.concat(x.questions); }, []);
    ansBody.innerHTML = '';
    if (!pool.length) {
      ansBody.innerHTML = '<p class="muted">무엇이든 물어보세요. 담당자가 검수해 둔 답변이 있으면 그대로 보여드립니다.</p>';
      return;
    }
    var head = document.createElement('p');
    head.className = 'muted';
    head.textContent = '이런 것을 물어볼 수 있습니다';
    ansBody.appendChild(head);
    pool.slice(0, 8).forEach(function (text) {
      var b = fill(tpl('tpl_suggest'), { text: text, topic: p ? p.name : '' });
      b.setAttribute('data-question', text);
      ansBody.appendChild(b);
    });
  }

  function BotMessage(opts) {
    var el = tpl('tpl_bot');
    var m = {
      el: el, mode: opts.ai ? 'ai' : 'verified', reasoning: opts.reasoning, model: opts.model,
      question: opts.question, project: opts.project,
      think: '', answer: '', sources: [], logId: '', ticketId: '',
      t0: Date.now(), thinkEnd: null, answerStarted: false, userToggled: false, phase: 'waiting',
      think_el: q(el, '.msg_think'), md_el: q(el, '.msg_md'), wait_el: q(el, '.msg_wait')
    };
    el.setAttribute('data-mode', m.mode);
    /* 배지는 **서버가 무엇으로 답했는지**(`result_type`)가 정합니다. 처음에는 AI 스위치
       상태로만 골라서, 자료만 찾은 질문에도 '담당자 검수 답변' 이 붙었습니다. */
    showBadge(m);
    if (m.reasoning) { show(m.think_el, true); m.think_el.classList.add('is_streaming'); m.phase = 'thinking'; }

    q(el, '.msg_think_toggle').addEventListener('click', function () {
      m.userToggled = true; setThinkOpen(m, m.think_el.classList.contains('is_collapsed'));
    });
    q(el, '.msg_copy').addEventListener('click', function () {
      try { navigator.clipboard.writeText(m.answer); } catch (err) { /* 권한 없는 브라우저 */ }
      fill(el, { copy_label: '복사됨' });
      setTimeout(function () { fill(el, { copy_label: '복사' }); }, 1500);
    });
    bindFeedback(m);
    bindSupport(m);
    return m;
  }
  function setThinkOpen(m, open) {
    m.think_el.classList.toggle('is_collapsed', !open);
    q(m.el, '.msg_think_toggle').setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  function tickMessage(m) {
    var now = Date.now();
    if (m.reasoning) {
      fill(m.el, {
        think_sec: sec((m.thinkEnd || now) - m.t0) + '초',
        think_label: m.thinkEnd ? '생각하는 과정' : '생각하는 중…'
      });
    }
    if (!m.answerStarted)
      fill(m.el, { wait: (m.mode === 'ai' ? '자료를 읽는 중… ' : '검수된 답변을 찾는 중… ') + sec(now - m.t0) + '초' });
  }
  function endThinking(m) {
    if (!m.reasoning || m.thinkEnd) return;
    m.thinkEnd = Date.now();
    m.think_el.classList.remove('is_streaming');
    if (!m.userToggled) setThinkOpen(m, false);     /* 답이 시작되면 접습니다 */
  }

  function finishMessage(m, stopped, elapsed) {
    m.phase = stopped ? 'stopped' : 'done';
    endThinking(m); tickMessage(m);
    show(m.wait_el, false);
    m.md_el.innerHTML = md(m.answer);

    if (!stopped && m.sources.length) {
      var list = q(m.el, '.msg_refs_list');
      m.sources.forEach(function (d) {
        var ref = fill(tpl('tpl_ref'), { kind: (KINDS[d.file_kind] || KINDS.etc).label, title: d.title });
        ref.setAttribute('data-kind', d.file_kind || 'md');
        q(ref, '[data-doc-open]').setAttribute('data-doc-open', d.doc_id);
        var dl = q(ref, '[data-doc-download]');
        dl.setAttribute('href', fileUrl({ doc_id: d.doc_id, project: d.project }));
        dl.setAttribute('title', d.file_name + ' 내려받기');
        list.appendChild(ref);
      });
      show(q(m.el, '.msg_refs'), true);
    }

    /* 검수 답변에는 'AI가 정리했다' 주의문을 띄우지 않습니다 — 사람이 승인한 문장이라
       "다를 수 있다"가 틀린 말이 되고, 검수의 의미가 흐려집니다. */
    show(q(m.el, '.msg_note'), m.mode === 'ai' && !stopped);

    var foot = q(m.el, '.msg_foot');
    var parts = [];
    /* 전체 검색에서는 **어느 자료에서 왔는지**를 적습니다. 사용자가 범위를 안 골랐으니
       모르는 것이 당연하고, 모르면 답을 어디까지 믿을지 정할 수가 없습니다.
       프로젝트 안에서 물었을 때는 이미 알고 있으므로 적지 않습니다. */
    if (state.view === 'search' && m.project) {
      var from = projectOf(m.project);
      if (from) parts.push(from.name);
    }
    if (m.mode === 'ai') { if (m.model) parts.push(m.model); parts.push(sec(elapsed) + '초', '검수 전'); }
    /* '담당자 검수 완료' 는 **검수된 답변이 나갔을 때만** 적습니다. 자료만 찾아 준 것에
       붙이면, 사람이 확인하지 않은 것을 확인했다고 말하는 것이 됩니다. */
    else if (m.resultType === 'answer') parts.push('담당자 검수 완료', sec(elapsed) + '초');
    else parts.push(sec(elapsed) + '초');
    if (stopped) parts.push('중단됨');
    fill(foot, { foot: parts.join(' · ') });
    show(foot, true);

    /* 👍/👎 는 **검수된 답변에만** 붙습니다. AI 초안은 아직 검수 대상이 아니고, 서버가
       이어 줄 `log_id` 도 주지 않습니다. */
    show(q(m.el, '.fb'), m.mode === 'verified' && !!m.logId && !stopped);

    /* 접수번호는 **서버가 준 값만** 보여 줍니다. 화면이 만들면 사용자가 부르는 번호와
       이력에 남은 번호가 달라져 담당자가 찾지 못합니다. */
    if (m.ticketId) showTicket(m, m.ticketId);
    else show(q(m.el, '.msg_ask'), m.mode === 'verified' && !stopped);
  }

  function showTicket(m, ticketId) {
    show(q(m.el, '.msg_ask'), false);
    fill(m.el, { ticket_id: ticketId });
    show(q(m.el, '.ticket'), true);
  }

  function bindFeedback(m) {
    var up = q(m.el, '.fb_up'), dn = q(m.el, '.fb_down'), why = q(m.el, '.fb_why');
    function sent() {
      show(q(m.el, '.fb'), false); show(why, false);
      show(q(m.el, '.fb_done'), true);
      setTimeout(function () { show(q(m.el, '.fb_done'), false); }, 2000);
    }
    up.addEventListener('click', function () {
      var on = up.classList.toggle('is_on');
      dn.classList.remove('is_on'); show(why, false);
      sendFeedback(m.logId, on ? 'up' : '', null, m.project).then(function () { if (on) sent(); });
    });
    dn.addEventListener('click', function () {
      var on = dn.classList.toggle('is_on');
      up.classList.remove('is_on');
      show(why, on);
      if (!on) sendFeedback(m.logId, '', null, m.project);
    });
    q(m.el, '.fb_why_close').addEventListener('click', function () { show(why, false); });
    [].forEach.call(m.el.querySelectorAll('.fb_reason'), function (b) {
      b.addEventListener('click', function () {
        sendFeedback(m.logId, 'down', b.getAttribute('data-reason'), m.project).then(sent, sent);
      });
    });
  }

  function bindSupport(m) {
    var btn = q(m.el, '.msg_ask_btn');
    btn.addEventListener('click', function () {
      btn.disabled = true;                 /* 두 번 누르면 번호가 두 개 생깁니다 */
      sendSupport(m.question, m.project).then(function (r) {
        if (r && r.ticket_id) showTicket(m, r.ticket_id);
        else { btn.disabled = false; toast('접수하지 못했습니다. 잠시 뒤 다시 시도해 주세요.'); }
      }, function () {
        btn.disabled = false; toast('접수하지 못했습니다. 잠시 뒤 다시 시도해 주세요.');
      });
    });
    q(m.el, '.ticket_copy').addEventListener('click', function () {
      try { navigator.clipboard.writeText(q(m.el, '.ticket_no b').textContent); toast('접수번호를 복사했습니다'); }
      catch (err) { /* 권한 없는 브라우저 */ }
    });
  }

  var ticker = null, stream = null;

  function send(text) {
    text = String(text == null ? $('aiQ').value : text).trim();
    if (!text || state.streaming) return;
    var ai = aiActive();

    /* **한 건씩** 봅니다. 새로 물으면 앞의 답을 대체합니다 — 쌓아 두면 대화처럼 보이는데,
       이어 묻기는 받지 않으므로 할 수 있는 것보다 많아 보이게 됩니다. */
    ansBody.innerHTML = '';
    panelOpen(true);
    $('ansQ').textContent = '“' + text + '”';

    var m = BotMessage({
      ai: ai, reasoning: ai && state.reasoning, model: modelName(),
      question: text, project: searchProject()
    });
    ansBody.appendChild(m.el);

    $('aiQ').value = '';
    state.streaming = true; state.current = m; state.stick = true;
    renderSend(); tickMessage(m); scrollDown();

    ticker = setInterval(function () { tickMessage(m); }, 250);
    stream = openStream({
      question: text, project: searchProject(), ai: ai, reasoning: m.reasoning, model: m.model
    }, {
      thinking: function (d) { m.think += d.text; fill(m.el, { think: m.think }); scrollDown(); },
      answer: function (d) {
        if (!m.answerStarted) { m.answerStarted = true; m.phase = 'answer'; endThinking(m); show(m.wait_el, false); }
        m.answer += d.text;
        m.md_el.innerHTML = withCursor(md(m.answer));
        scrollDown();
      },
      sources: function (d) { m.sources = d.docs || []; },
      done: function (d) {
        m.logId = d.log_id || ''; m.ticketId = d.ticket_id || '';
        m.resultType = d.result_type || '';
        /* 어느 프로젝트가 답했는지 서버가 알려 줍니다. 뒤이어 보내는 문의가 **그 팩에**
           쌓여야 담당자가 접수번호로 찾을 수 있습니다 — '전체' 로 물었을 때가 그렇습니다. */
        if (d.project) m.project = d.project;
        if (d.model) m.model = d.model;
        stopTicker(); finishMessage(m, false, d.elapsed_ms); endStream(); scrollDown();
      },
      error: function (err) {
        m.answer = m.answer || ('답변을 가져오지 못했습니다. ' + (err && err.message ? err.message : ''));
        stopTicker(); finishMessage(m, true, Date.now() - m.t0); endStream(); scrollDown();
      }
    });
  }
  /* `answer` 일 때만 검수 배지를 붙입니다. AI 가 쓴 것은 검수 전이므로 늘 'AI 정리' 입니다.
     `result_type` 이 아직 없으면(응답 중) 아무것도 붙이지 않습니다 — 잠깐 떴다 바뀌는 배지는
     사용자가 먼저 본 쪽을 기억합니다. */
  function showBadge(m) {
    var el = m.el;
    ['.badge_verified', '.badge_docs', '.badge_open', '.badge_ai'].forEach(function (sel) {
      show(q(el, sel), false);
    });
    if (m.mode === 'ai') { show(q(el, '.badge_ai'), true); return; }
    if (m.resultType === 'answer') show(q(el, '.badge_verified'), true);
    else if (m.resultType === 'related_docs') show(q(el, '.badge_docs'), true);
    else if (m.resultType === 'unresolved') show(q(el, '.badge_open'), true);
  }

  function stopTicker() { clearInterval(ticker); ticker = null; }
  function endStream() { state.streaming = false; state.current = null; stream = null; renderSend(); }
  function stop() {
    if (!state.streaming) return;
    if (stream) stream.close();
    var m = state.current;
    stopTicker(); finishMessage(m, true, Date.now() - m.t0); endStream();
  }

  function renderSend() {
    var b = $('aiSend');
    b.setAttribute('data-state', state.streaming ? 'stop' : 'send');
    b.setAttribute('aria-label', state.streaming ? '답변 중단' : '질문 보내기');
    b.classList.toggle('is_stop', state.streaming);
    q(b, 'use').setAttribute('href', state.streaming ? '#ic-x' : '#ic-send');
  }

  /* ================= AI 선택 세 가지 ================= */
  function renderOpts() {
    var ai = aiActive();
    var mode = $('aiMode');
    mode.checked = ai;
    mode.disabled = state.llmDown;
    show(q($('aiModeWrap'), '[data-blocker]'), state.llmDown);

    show($('aiReasonWrap'), REASONING);
    var multi = state.models.length > 1;
    show($('aiModel'), multi);
    show($('aiModelName'), !multi);
    $('aiModelName').textContent = modelName() || '없음';
    $('aiModel').disabled = !ai;
    $('aiReasoning').disabled = !ai;
    $('aiReasoning').checked = ai && state.reasoning;
    $('aiDepWrap').classList.toggle('is_disabled', !ai);
    show(q($('aiDepWrap'), '[data-blocker]'), !ai);

    /* AI 를 켠 상태에서는 여기에 안내를 두지 않습니다. 같은 경고가 답변 말풍선 안
       (`.msg_note`)에 이미 붙고, 두 번 적으면 읽히지 않습니다. */
    $('aiNote').textContent = state.llmDown
      ? '지금은 AI 답변을 쓸 수 없습니다. 담당자가 검수한 답변만 보여드립니다.'
      : ai ? '' : '담당자가 검수한 답변만 보여드립니다.';
  }

  var hintTimer = null;
  function hint(text) {
    clearTimeout(hintTimer);
    $('aiHint').textContent = text;
    show($('aiHint'), true);
    hintTimer = setTimeout(function () { show($('aiHint'), false); }, 3600);
  }

  /* ================= 자료 원문 모달 ================= */
  var lastFocus = null;
  function openDoc(docId) {
    var d = docOf(docId);
    if (!d) return;
    lastFocus = document.activeElement;
    var modal = $('docModal');
    fill(modal, {
      title: d.title,
      meta: (d.indexed ? d.chunk_count + '개 절' : '본문 없음') +
        (d.category ? ' · ' + d.category : '') + ' · ' + esc(d.project_name)
    });
    /* 묶인 원본을 **전부** 건다. 하나면 버튼 하나, 여럿이면 파일마다 하나입니다 —
       긴 발표자료를 주제별로 쪼개 쓰면 본문 하나가 원본 둘을 가리킬 수 있습니다. */
    var dls = $('docDownloads');
    dls.innerHTML = '';
    var files = (d.files && d.files.length) ? d.files : [{ name: d.file_name, kind: d.kind }];
    files.forEach(function (f) {
      var a = document.createElement('a');
      a.className = 'modal_dl';
      a.setAttribute('download', '');
      a.setAttribute('href', fileUrl(d) + (d.files && d.files.length
        ? (d.project ? '&' : '?') + 'name=' + encodeURIComponent(f.name) : ''));
      a.innerHTML = '<svg class="i"><use href="#ic-download"/></svg>' +
        esc(files.length > 1 ? f.name : '원본 내려받기');
      dls.appendChild(a);
    });
    $('docBody').textContent = d.indexed ? '불러오는 중…' : '정리한 본문(.md)이 없는 자료입니다. 원본을 내려받아 확인해 주세요.';
    $('docBody').classList.toggle('is_md', !!d.indexed);
    modal.classList.add('is_open');
    $('docClose').focus();
    if (!d.indexed) return;
    getJson('/api/docs/' + encodeURIComponent(d.doc_id) + (d.project ? '?project=' + encodeURIComponent(d.project) : ''))
      .then(function (r) {
        /* 원본은 마크다운입니다. 글자 그대로 보여 주면 `##` 과 `**` 이 그대로 보여,
           같은 글이 답변 말풍선·검수 미리보기와 다르게 읽힙니다. */
        $('docBody').innerHTML = md(r.text || '');
      }, function () {
        $('docBody').classList.remove('is_md');
        $('docBody').textContent = '원문을 불러오지 못했습니다.';
      });
  }
  function closeDoc() {
    $('docModal').classList.remove('is_open');
    if (lastFocus) lastFocus.focus();
  }

  /* ================= 자료 올리기 ================= */
  var dropzone = $('dropzone');

  /* 몇 건씩 나눠 보냅니다. 한 요청에 다 보내면 진행 상황을 보여줄 수 없고, 타임아웃 뒤에
     무엇이 들어갔는지 알 수 없습니다(app/ingestion/doc_upload.py 의 같은 판단). */
  function batches(files) {
    var out = [], cur = [], bytes = 0;
    files.forEach(function (f) {
      if (cur.length && (cur.length >= UP_FILES || bytes + f.size > UP_BYTES)) { out.push(cur); cur = []; bytes = 0; }
      cur.push(f); bytes += f.size;
    });
    if (cur.length) out.push(cur);
    return out;
  }

  function upload(files) {
    var list = [].slice.call(files);
    if (!list.length) return;
    if (!state.projectId) { toast('어느 프로젝트에 넣을지 먼저 고르세요'); return; }

    var groups = batches(list), done = 0, rows = {};
    show($('upbar'), true);
    $('upList').innerHTML = '';
    $('upTitle').textContent = '올리는 중…';
    list.forEach(function (f) {
      var li = fill(tpl('tpl_up_item'), { name: f.name, state: '대기' });
      rows[f.name] = li; $('upList').appendChild(li);
    });

    function tick() {
      $('upCount').textContent = done + ' / ' + list.length;
      $('upFill').style.width = Math.round(done / list.length * 100) + '%';
    }
    tick();

    function step(i) {
      if (i >= groups.length) {
        $('upTitle').textContent = '올리기를 마쳤습니다';
        return refresh().then(function () { renderFiles(); renderFolders(); });
      }
      return uploadBatch(groups[i], state.projectId, true).then(function (r) {
        (r.items || []).forEach(function (item) {
          var li = rows[String(item.path).split('/').pop()];
          if (!li) return;
          var label = { created: '등록', updated: '갱신', attached: '원본 보관', skipped: '건너뜀', failed: '실패' }[item.status] || item.status;
          fill(li, { state: item.reason ? label + ' · ' + item.reason : label });
          li.classList.toggle('is_bad', item.status === 'skipped' || item.status === 'failed');
        });
        done += groups[i].length; tick();
        return step(i + 1);
      }, function (err) {
        if (err && err.message === 'auth') {
          $('upTitle').textContent = '관리자 로그인이 필요합니다';
          toast('자료 등록은 관리자만 할 수 있습니다. 관리자 설정에서 로그인해 주세요.');
        } else {
          $('upTitle').textContent = '올리지 못했습니다';
          toast(err && err.message ? err.message : '자료를 올리지 못했습니다');
        }
      });
    }
    step(0);
  }

  if (dropzone) {
    ['dragenter', 'dragover'].forEach(function (ev) {
      dropzone.addEventListener(ev, function (e) { e.preventDefault(); dropzone.classList.add('over'); });
    });
    ['dragleave', 'drop'].forEach(function (ev) {
      dropzone.addEventListener(ev, function (e) {
        e.preventDefault();
        if (ev === 'drop' || !dropzone.contains(e.relatedTarget)) dropzone.classList.remove('over');
      });
    });
    dropzone.addEventListener('drop', function (e) { upload(e.dataTransfer.files); });
    $('fileInput').addEventListener('change', function (e) { upload(e.target.files); e.target.value = ''; });
  }
  /* 영역 밖에 떨어뜨려도 브라우저가 파일을 열지 않도록 */
  window.addEventListener('dragover', function (e) { e.preventDefault(); });
  window.addEventListener('drop', function (e) { e.preventDefault(); });

  /* ================= 배선 ================= */
  function bind() {
    aiForm.addEventListener('submit', function (e) {
      e.preventDefault();
      if (state.streaming) stop(); else send();
    });
    $('aiQ').addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); if (!state.streaming) send(); }
    });
    $('ansClose').addEventListener('click', function () {
      stop(); panelOpen(false); ansBody.innerHTML = ''; $('ansQ').textContent = '';
    });
    $('navAsk').addEventListener('click', function (e) {
      e.preventDefault();
      setView('search');
      if (!ansBody.children.length) renderSuggest();
      panelOpen(true);
      $('aiQ').focus();
    });
    $('navDrive').addEventListener('click', function (e) {
      e.preventDefault();
      /* 이미 프로젝트 화면이면 접었다 폈다 합니다. 다른 화면에서 누르면 넘어오면서 폅니다. */
      if (state.view === 'browse') openNavProjects($('navProjects').hidden);
      else setView('browse');
    });
    $('navProjects').addEventListener('click', function (e) {
      var a = e.target.closest('a[data-np]');
      if (!a) return;
      e.preventDefault();
      if (state.view !== 'browse') setView('browse');
      selectProject(a.dataset.np || null);
    });
    $('navLibrary').addEventListener('click', function (e) { e.preventDefault(); setView('library'); });

    $('aiMode').addEventListener('change', function (e) {
      state.aiOn = e.target.checked; show($('aiHint'), false); renderOpts();
    });
    $('aiModel').addEventListener('change', function (e) { state.model = e.target.value; });
    $('aiReasoning').addEventListener('change', function (e) { state.reasoning = e.target.checked; });
    q($('aiModeWrap'), '[data-blocker]').addEventListener('click', function () {
      hint('지금은 AI 답변을 쓸 수 없습니다. 담당자가 검수한 답변으로 안내합니다.');
    });
    q($('aiDepWrap'), '[data-blocker]').addEventListener('click', function () {
      hint(state.llmDown ? '지금은 AI 답변을 쓸 수 없습니다.'
        : 'AI 답변을 켜야 모델과 추론 과정을 고를 수 있습니다. 끈 상태에서는 검수된 답변만 보여드립니다.');
    });

    document.addEventListener('click', function (e) {
      var open = e.target.closest('[data-doc-open]');
      if (open) { openDoc(open.getAttribute('data-doc-open')); return; }
      var s = e.target.closest('[data-question]');
      if (s) send(s.getAttribute('data-question'));
    });
    $('docClose').addEventListener('click', closeDoc);
    $('docModal').addEventListener('click', function (e) { if (e.target === e.currentTarget) closeDoc(); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && $('docModal').classList.contains('is_open')) closeDoc();
    });
  }

  /* ================= 두 화면 ================= */
  /* `AI 지식 검색` 은 **늘 전체 범위**입니다. 고른 프로젝트가 있어도 무시합니다 — 메뉴
     이름이 '전체' 를 약속하는데 조용히 좁혀 찾으면 왜 안 나오는지 알 길이 없습니다. */
  function searchProject() { return state.view === 'search' ? '' : (state.projectId || ''); }

  /* 프로젝트에는 **용도**가 있습니다 — 묻고 답하는 `knowledge`, 받아 쓰는 `library`(자료실).
     담는 것이 달라 메뉴를 나누지만 올리고 내려주는 구조는 같습니다(app/core/projects.py). */
  function viewRole() { return state.view === 'library' ? 'library' : 'knowledge'; }
  function roleOf(projectId) {
    var p = projectOf(projectId);
    return (p && p.role) || 'knowledge';
  }
  function inView(p) { return ((p && p.role) || 'knowledge') === viewRole(); }

  var VIEW_TITLE = { search: 'AI 지식 검색', browse: '프로젝트', library: '자료실' };

  /* ---------- 좌측 `프로젝트` 하위 메뉴 ----------
     폴더 카드와 **같은 것을 두 군데**에서 고를 수 있습니다. 카드는 둘러보는 자리이고,
     하위 메뉴는 지금 어느 프로젝트에 들어와 있는지를 늘 보이게 하는 자리입니다 —
     검색 범위가 거기서 정해지므로(`searchProject`), 화면 어딘가에 항상 적혀 있어야
     합니다. 그래서 고르는 길은 하나(`selectProject`)로 모읍니다. */
  function renderNavProjects() {
    var box = $('navProjects');
    var mine = state.projects.filter(function (p) { return (p.role || 'knowledge') === 'knowledge'; });
    if (!mine.length) {
      box.innerHTML = '<span class="nav_sub_empty">아직 프로젝트가 없습니다</span>';
      return;
    }
    var rows = ['<a href="#" data-np="" class="' + (state.projectId ? '' : 'on') + '">전체</a>'];
    box.innerHTML = rows.concat(mine.map(function (p) {
      return '<a href="#" data-np="' + esc(p.project_id) + '"' +
        (p.project_id === state.projectId ? ' class="on"' : '') + '>' +
        esc(p.name) + '<em>' + p.doc_count + '</em></a>';
    })).join('');
  }

  function openNavProjects(open) {
    $('navProjects').hidden = !open;
    $('navDrive').setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) renderNavProjects();
  }

  function setView(view) {
    state.view = view;
    var search = view === 'search';
    $('app').classList.toggle('is_search', search);
    $('navAsk').classList.toggle('active', search);
    $('navDrive').classList.toggle('active', view === 'browse');
    $('navLibrary').classList.toggle('active', view === 'library');
    openNavProjects(view === 'browse');
    if (search) {
      $('pageTitle').textContent = VIEW_TITLE.search;
      $('crumb').textContent = '전체 자료에서 찾습니다';
      /* 안내 문구도 되돌립니다. 이 화면은 `searchProject()` 가 '' 라 **전체**가 범위인데,
         프로젝트에 들어갔다 나온 뒤 이름이 남아 있으면 실제 범위와 어긋납니다. */
      $('aiQ').placeholder = DEFAULT_ASK;
      return;
    }
    /* 고른 것이 이 메뉴의 것이 아니면 놓습니다 — 자료실에서 지식 프로젝트가 골라진 채로
       남아 있으면 목록이 비는데 왜 비었는지 알 수가 없습니다. */
    if (state.projectId && roleOf(state.projectId) !== viewRole()) state.projectId = null;
    state.limit = pageSize();
    showScope();
    renderFolders(); renderChips(); renderFiles();
  }

  /* 지금 어디를 보고 있는지. 제목에 **프로젝트 이름**을 올립니다 — 검색 범위가 여기서
     정해지므로, 'API Manager 안에서 찾고 있다' 가 한눈에 보여야 합니다. */
  var DEFAULT_ASK = $('aiQ').placeholder;

  function showScope() {
    var p = projectOf(state.projectId);
    var menu = VIEW_TITLE[state.view] || VIEW_TITLE.browse;
    $('pageTitle').textContent = p ? p.name : menu;
    $('crumb').textContent = p
      ? menu + ' / 이 프로젝트 안에서 찾습니다'
      : (state.view === 'library' ? '견적서 양식·템플릿처럼 받아서 쓰는 문서'
                                  : '프로젝트를 고르면 그 안에서만 찾습니다');
    $('aiQ').placeholder = p ? p.name + ' 에서 찾습니다. 한 문장으로 물어보세요.' : DEFAULT_ASK;
  }

  /* ================= 시작 ================= */
  function refresh() {
    return loadDrive().then(function (r) {
      state.projects = r.projects || [];
      state.docs = r.docs || [];
      $('stDocs').textContent = state.docs.length;
      $('stSize').textContent = fmtSize(r.total_bytes || 0);
    });
  }

  function init() {
    bind();
    show(dropzone, STUDIO);
    renderSend(); renderOpts();

    var models = loadModels().then(function (list) {
      state.models = list || [];
      state.llmDown = !state.models.length;
      var sel = $('aiModel');
      sel.innerHTML = '';
      state.models.forEach(function (m) {
        var o = document.createElement('option');
        o.value = m.name; o.textContent = m.label || m.name; o.selected = !!m.default;
        sel.appendChild(o);
      });
    }, function () { state.models = []; state.llmDown = true; });

    Promise.all([refresh(), models]).then(function () {
      /* 새 프로젝트를 만든 뒤 `/?project=...` 로 돌아옵니다. 고른 상태로 열어야 바로
         자료를 올릴 수 있습니다 — 다시 찾아 누르게 하면 흐름이 한 번 끊깁니다. */
      /* 새 프로젝트를 만들고 `/?project=...` 로 돌아오면 **둘러보기**로 엽니다 —
         방금 만든 프로젝트에 자료를 넣으러 온 것이기 때문입니다. 그 밖에는 검색 화면이
         첫 화면입니다(제품의 첫 일이 찾는 것입니다). */
      var wanted = new URLSearchParams(location.search).get('project');
      if (wanted && projectOf(wanted)) state.projectId = wanted;
      renderFolders(); renderChips(); renderFiles(); renderOpts();
      setView(wanted && projectOf(wanted) ? 'browse' : 'search');
      /* `enhanceSelect` 는 옵션이 다 들어온 뒤에 한 번만 부릅니다 — 안쪽에서 목록을
         미리 그려 두므로, 나중에 옵션을 넣으면 그 목록이 갱신되지 않습니다. */
      enhanceSelect(pageSizeEl, { variant: 'inline' });
      enhanceSelect($('sort'), { variant: 'inline', align: 'right' });
    }, function (err) {
      toast('자료 목록을 불러오지 못했습니다');
      $('empty').style.display = 'block';
      $('empty').textContent = '자료 목록을 불러오지 못했습니다. 잠시 뒤 다시 시도해 주세요.';
      if (window.console) console.error(err);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
