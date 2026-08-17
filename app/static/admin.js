/* ============================================================
   API Manager 도우미 — 관리자 화면 (퍼블 산출물 이식본)

   원본: 퍼블/forever-chat-serve/admin.js (더미 데이터로 동작하는 산출물)
   여기서 바꾼 것은 두 가지뿐입니다.

   1. 이 머리 부분 — 더미 상수를 걷어내고 **서버에서 받아 같은 모양으로** 채웁니다.
   2. 저장·실행 지점 — `mockSave` / `setTimeout` 흉내를 실제 API 호출로 바꿨습니다.

   **렌더·이벤트 코드는 건드리지 않았습니다.** 다음 퍼블 산출물이 오면 이 두 곳만 다시
   옮기면 됩니다. 화면 로직에 서버 사정을 섞기 시작하면 산출물을 갈아 끼울 때마다
   같은 작업을 처음부터 다시 하게 됩니다.

   ── 서버 응답 → 화면 모양 ─────────────────────────────────────
   | 화면        | 서버                                   | 다른 점                 |
   | QA 상태     | approved/pending/hold/disabled          | done/wait/hold/unused   |
   | 카테고리    | enabled                                 | used                    |
   | 문서        | chunk_count / linked_qa_count           | chunks / qa_count       |
   | 이력        | log_id / asked_at / similarity          | hist_id / ts / score    |
   이름을 서버에 맞추지 않고 화면 쪽에 맞춘 이유: 화면은 통째로 교체되는 산출물이고,
   변환은 이 파일 한 곳에만 있으면 됩니다.
   ============================================================ */

function pad(n){ return (n < 10 ? '0' : '') + n; }
function fmtDate(d){ return d.getFullYear() + '-' + pad(d.getMonth()+1) + '-' + pad(d.getDate()); }
function fmtTs(d){ return pad(d.getMonth()+1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()); }

/* ------------------------------------------------------------
   서버 호출
   ------------------------------------------------------------ */
var API = {
  get: function(url){ return $.ajax({ url:url, method:'GET', dataType:'json' }); },
  send: function(method, url, body){
    return $.ajax({
      url:url, method:method, dataType:'json',
      contentType:'application/json; charset=utf-8',
      data: body === undefined ? undefined : JSON.stringify(body)
    });
  },
  /* 파일 업로드(multipart). contentType:false 여야 브라우저가 경계 문자열을 직접 붙입니다.
     processData:false 가 없으면 jQuery 가 FormData 를 문자열로 만들어 파일이 사라집니다. */
  upload: function(url, formData){
    return $.ajax({
      url:url, method:'POST', dataType:'json',
      data:formData, processData:false, contentType:false
    });
  }
};

/* 서버가 보내는 오류 문구를 그대로 보여줍니다 — 화면이 만든 문구보다 정확합니다. */
function apiError(xhr, fallback){
  try { return (xhr.responseJSON && xhr.responseJSON.detail) || fallback; }
  catch(e){ return fallback; }
}

/* 세션이 끊기면(401) 로그인 모달을 다시 띄웁니다. 하던 작업은 화면에 그대로 남습니다. */
$(document).ajaxError(function(_, xhr, settings){
  if(xhr.status !== 401) return;
  if(String(settings.url).indexOf('/api/admin/login') > -1) return;
  $(document).trigger('admin:unauthorized');
});

/* ------------------------------------------------------------
   화면이 읽는 전역 — 서버 응답으로 채웁니다
   ------------------------------------------------------------ */
var CATEGORY_GROUPS = [];
var QUICK_CATEGORY_IDS = [];
var ALL_CATS = [];
var DOCS = [];
var QA_ITEMS = [];
var HISTORY = [];
var CLUSTERS = [];
var REVIEW_QUEUE = [];      /* 검수 대기(pending)만. QA_ITEMS 에서 파생됩니다 */
var BRAND = { organization:'KT', service_name:'API Manager 도우미', service_desc:'API 등록 · 그룹 · 템플릿' };

/* 진행 현황은 서버가 판단까지 끝내서 내려줍니다. 화면은 그대로 그리기만 합니다 —
   화면이 숫자를 보고 다시 판단하면 임계값이 화면과 서버 두 곳에 생깁니다. */
var FLOW_STEPS = [];        /* [{key, value, note, state}] 순서 그대로 그립니다 */
var FLOW_TODO = null;       /* 서버가 고른 병목 하나. kind==='clear' 면 null */
var FLOW_SUMMARY = null;    /* 흐름 요약. has_run 이 false 면 null */
var FLOW_AT = '';

var QA_STATUS_TO_VIEW = { approved:'done', pending:'wait', hold:'hold', disabled:'unused' };
var QA_STATUS_TO_API  = { done:'approved', wait:'pending', hold:'hold', unused:'disabled' };

function rebuildCats(){
  ALL_CATS = [];
  $.each(CATEGORY_GROUPS, function(_, g){
    $.each(g.categories, function(_, c){
      ALL_CATS.push($.extend({ group_id:g.group_id, group_name:g.group_name }, c));
    });
  });
}
function catName(id){
  for(var i = 0; i < ALL_CATS.length; i++) if(ALL_CATS[i].category_id === id) return ALL_CATS[i].name;
  return '';
}

/* ------------------------------------------------------------
   서버 → 화면 변환
   ------------------------------------------------------------ */
function mapCategories(store){
  CATEGORY_GROUPS = (store.groups || []).map(function(g){
    return {
      group_id:g.group_id, group_name:g.group_name, used:g.enabled !== false,
      categories:(g.categories || []).map(function(c){
        return {
          category_id:c.category_id, name:c.name, used:c.enabled !== false,
          questions:c.questions || []
        };
      })
    };
  });
  QUICK_CATEGORY_IDS = store.quick_category_ids || [];
  rebuildCats();
}

/* 화면 모양 → 서버 저장 형식. 저장은 항상 트리 전체를 한 번에 보냅니다(PUT). */
function toCategoryStore(){
  return {
    groups: CATEGORY_GROUPS.map(function(g, gi){
      return {
        group_id:g.group_id, group_name:g.group_name, enabled:g.used !== false, sort:gi,
        categories:g.categories.map(function(c, ci){
          return {
            category_id:c.category_id, name:c.name, group_id:g.group_id,
            questions:c.questions || [], enabled:c.used !== false, sort:ci
          };
        })
      };
    }),
    quick_category_ids: QUICK_CATEGORY_IDS
  };
}

function mapQa(row){
  return {
    qa_id:row.qa_id,
    question:row.question,
    /* 목록 응답에는 답변 전문이 없습니다(80건이면 수백 KB). 검수 모달을 열 때 따로 받습니다. */
    answer:row.answer != null ? row.answer : (row.answer_preview || ''),
    answer_loaded:row.answer != null,
    category_id:row.category_id || '',
    category_name:catName(row.category_id) || '미분류',
    variants:row.variants || [],
    variant_count:row.variant_count != null ? row.variant_count : (row.variants || []).length,
    hit:row.hit_count || 0,
    status:QA_STATUS_TO_VIEW[row.status] || 'wait',
    updated:(row.updated_at || '').slice(0, 10),
    note:row.note || '',
    /* 생성 때 판정 모델이 매긴 점수. 검수 화면이 낮은 점수부터 보여주는 근거입니다. */
    score:row.score || 0,
    judge_model:row.judge_model || '',
    judge_reason:row.judge_reason || '',
    /* 사용자 신고(요청서 10 C). 목록 응답에는 개수만, 한 건을 열면 원문 목록이 함께 옵니다. */
    report_count:row.report_count || 0,
    reports:row.reports || [],
    sources:(row.source_doc_ids || []).map(function(id){
      var d = DOCS.filter(function(x){ return x.doc_id === id; })[0];
      return d || { doc_id:id, title:id };
    })
  };
}

/* 검수 화면이 읽는 모양. 목록 응답에는 답변 전문이 없어서 `answer_loaded` 로 표시해 두고,
   그 건을 실제로 열 때 한 건만 받아옵니다(QA 모달과 같은 방식). */
function mapReviewItem(q){
  return {
    qa_id:q.qa_id, question:q.question, answer:q.answer, answer_loaded:q.answer_loaded,
    category_id:q.category_id, category_name:q.category_name,
    variants:q.variants, sources:q.sources, note:q.note || '',
    /* 0 은 점수가 아니라 '채점하지 않음' 입니다. 화면이 '채점 없음' 으로 그리도록 null 로 바꿉니다. */
    score:q.score ? q.score : null,
    score_model:q.judge_model || '', score_why:q.judge_reason || '',
    report_count:q.report_count || 0, reports:q.reports || [],
    hit:q.hit, created:q.updated || ''
  };
}
function rebuildReviewQueue(){
  REVIEW_QUEUE = QA_ITEMS.filter(function(q){ return q.status === 'wait'; }).map(mapReviewItem);
}

function mapDoc(row){
  return {
    doc_id:row.doc_id,
    title:row.title || row.doc_id,
    category_id:'',
    category_name:row.category || '',
    updated:(row.updated || '').slice(0, 10),
    chunks:row.chunk_count || 0,
    qa_count:row.linked_qa_count || 0,
    body:null   /* 편집 모달을 열 때 받아옵니다 */
  };
}

function mapHistory(row){
  var d = new Date((row.asked_at || '').replace(' ', 'T'));
  if(isNaN(d.getTime())) d = new Date();
  return {
    hist_id:row.log_id,
    ts:d, ts_txt:fmtTs(d),
    question:row.question,
    result_type:row.result_type || 'unresolved',
    /* 이력에 저장된 답변을 그대로 씁니다 — QA를 나중에 고쳐도 그때 나간 답변이 보여야 합니다. */
    matched_qa:row.matched_qa_id ? {
      qa_id:row.matched_qa_id,
      question:row.matched_question || row.question,
      answer:row.answer || '',
      sources:(row.source_doc_titles || []).map(function(t){ return { title:t }; })
    } : null,
    score:row.similarity == null ? null : Math.round(row.similarity * 100) / 100,
    category_id:row.category_id || '',
    category_name:row.category_label || '',
    channel:row.channel === 'web' ? '챗봇' : row.channel,
    is_test:row.channel !== 'web',
    ticket:row.ticket_id || '',
    /* 사용자 신고(요청서 10). 대부분의 행은 빈 값이고 그게 정상입니다 —
       비율(만족도 %)로 읽으면 안 됩니다. 어느 QA에 👎가 몰리는지만 봅니다. */
    fb:row.feedback || '',
    fb_reason:row.feedback_reason || '',
    related:(row.source_doc_titles || []).map(function(t){ return { title:t }; })
  };
}

/* ------------------------------------------------------------
   불러오기
   ------------------------------------------------------------ */
function loadCategories(){
  return API.get('/api/admin/categories').done(mapCategories);
}
function loadDocs(){
  return API.get('/api/admin/docs').done(function(rows){ DOCS = (rows || []).map(mapDoc); });
}
function loadQa(){
  /* 목록은 500건까지. 그 이상이면 화면 페이지네이션이 아니라 서버 페이징으로 옮겨야 합니다. */
  return API.get('/api/admin/qa?limit=500&sort=hit_count').done(function(page){
    QA_ITEMS = (page.items || []).map(mapQa);
    rebuildReviewQueue();
  });
}
/* 진행 현황 — 여섯 칸을 한 번에 받습니다. 칸마다 부르면 요청 사이에 승인이 일어나
   칸끼리 앞뒤가 안 맞는 화면이 나옵니다. */
function loadFlow(){
  return API.get('/api/admin/pipeline/status').done(function(s){
    FLOW_STEPS = s.steps || [];
    FLOW_TODO = (s.todo && s.todo.kind !== 'clear') ? s.todo : null;
    FLOW_SUMMARY = (s.summary && s.summary.has_run) ? s.summary : null;
    FLOW_AT = (s.checked_at || '').replace('T', ' ').slice(0, 16);
  });
}
/* 서버가 쓰고 있는 모델·컨텍스트. `.env` 에서 오고 기동할 때 고정되므로 화면은 **보여주기만**
   합니다(설정 → 생성 설정, 품질 평가의 임베딩 표시). 고칠 수 있는 값은 임계값뿐입니다. */
function loadRuntimeModels(){
  return API.get('/api/admin/mode').done(function(m){
    $('#evalEmbedModel').text(m.embed_model || '—');
    $('#setQuestionModel').text(m.question_model || '—');
    $('#setAnswerModel').text(m.answer_model || '—');
    /* 채점 모델이 비어 있는 것은 설정 누락이 아니라 '채점 안 함'입니다. */
    $('#setJudgeModel').text(m.judge_model || '채점 안 함');
    $('#setCtx').text(m.num_ctx ? m.num_ctx.toLocaleString('ko-KR') : '—');
    $('#setMaxLen').text(m.num_predict ? m.num_predict.toLocaleString('ko-KR') : '—');
    /* 문서 작성 안내의 길이 기준. 화면에 숫자를 박아 두면 설정과 조용히 어긋납니다. */
    if(m.embed_warn_chars) $('#guideWarnChars').text(m.embed_warn_chars.toLocaleString('ko-KR'));
  });
}
function loadProfile(){
  return API.get('/api/admin/profile').done(function(p){
    BRAND = p;
    $('#profOrg').val(p.organization);
    $('#profName').val(p.service_name);
    $('#profDesc').val(p.service_desc);
    $('#profDomain').val(p.domain_intro);
    $('#profLang').val(p.language);
  });
}
function loadHistory(){
  return API.get('/api/admin/questions?limit=500&include_test=true').done(function(page){
    HISTORY = (page.items || []).map(mapHistory);
  });
}
function loadAnalytics(){
  return API.get('/api/admin/analytics').done(function(result){
    CLUSTERS = (result.clusters || []).map(function(c){
      return $.extend({}, c, { category_name:c.category_name || '미분류' });
    });
  });
}
function loadSettings(){
  return API.get('/api/admin/settings').done(function(s){
    $('#thMatch').val(s.qa_match_threshold);
    $('#thRelated').val(s.related_docs_floor);
    $('#thRelatedCount').val(s.related_docs_count);
  });
}

/* 문서 → QA → 이력 순서가 중요합니다. QA의 출처 표기와 이력의 주제 이름이
   앞 단계 결과를 참조합니다. */
function loadAll(){
  return loadCategories()
    .then(loadDocs)
    .then(loadQa)
    .then(loadHistory)
    .then(loadAnalytics)
    .then(loadSettings)
    .then(loadProfile)
    .then(loadRuntimeModels)
    .then(loadFlow);
}

$(function(){

  var MODE = $('body').attr('data-mode') || 'serve';
  var PAGE_SIZE = { hist:20, an:20, qa:20, doc:20 };
  var PAGE = { hist:1, an:1, qa:1, doc:1 };
  var SORT = { hist:{ key:'ts', dir:'desc' }, an:{ key:'count', dir:'desc' }, qa:{ key:'hit', dir:'desc' } };
  var FILTER = {
    hist:{ rt:'', cat:'', q:'', test:false, fb:'' },
    an:{ f:'', cat:'', sort:'count' },
    qa:{ f:'', cat:'', q:'', sort:'hit' },
    doc:{ q:'' }
  };
  var QUICK = [];   /* 서버에서 받은 뒤 renderAll() 이 채운다 */
  var currentCat = null, currentQa = null, currentDoc = null, confirmCb = null;

  /* ---------- 유틸 ---------- */
  function esc(s){
    return String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
  function tpl(id){ return $($('#'+id).prop('content').cloneNode(true)); }
  function findCat(id){ for(var i=0;i<ALL_CATS.length;i++) if(ALL_CATS[i].category_id === id) return ALL_CATS[i]; return null; }
  function findGroup(id){ for(var i=0;i<CATEGORY_GROUPS.length;i++) if(CATEGORY_GROUPS[i].group_id === id) return CATEGORY_GROUPS[i]; return null; }
  function num(n){ return Number(n || 0).toLocaleString('ko-KR'); }

  function inline(t){
    return esc(t).replace(/`([^`]+)`/g,'<code>$1</code>').replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>');
  }
  function renderMarkdown(src){
    var html = '';
    $.each(String(src || '').replace(/\r\n/g,'\n').split(/\n{2,}/), function(_, block){
      var lines = block.split('\n').filter(function(l){ return l.trim() !== ''; });
      if(!lines.length) return;
      if(/^\s*\d+\.\s/.test(lines[0])){
        html += '<ol>' + lines.map(function(l){ return '<li>' + inline(l.replace(/^\s*\d+\.\s/,'')) + '</li>'; }).join('') + '</ol>';
      } else if(/^\s*[-*]\s/.test(lines[0])){
        html += '<ul>' + lines.map(function(l){ return '<li>' + inline(l.replace(/^\s*[-*]\s/,'')) + '</li>'; }).join('') + '</ul>';
      } else {
        html += '<p>' + lines.map(inline).join('<br>') + '</p>';
      }
    });
    return html;
  }
  function plain(md){ return String(md || '').replace(/[*`#>\-]/g,'').replace(/\s+/g,' ').trim(); }

  function rtBadge(rt){
    var m = { answer:['is_answer','answer'], related_docs:['is_related','related_docs'], unresolved:['is_unresolved','unresolved'] }[rt];
    return m ? '<span class="admin_rt ' + m[0] + '">' + m[1] + '</span>' : '—';
  }
  var QA_ST = { wait:['is_wait','검수대기'], done:['is_done','검수완료'], hold:['is_hold','보류'], unused:['is_unused','미사용'] };
  var CL_ST = { new:['is_new','신규'], reviewed:['is_reviewed','검토됨'], generated:['is_generated','QA 생성됨'], applied:['is_applied','반영됨'], excluded:['is_excluded','제외'] };
  function stBadge(map, k){ var m = map[k]; return m ? '<span class="admin_st ' + m[0] + '">' + m[1] + '</span>' : '—'; }

  /* ---------- 토스트 ---------- */
  function toast(msg, kind){
    var $t = tpl('tpl_toast').children();
    $t.addClass(kind === 'err' ? 'is_err' : 'is_ok');
    $t.find('.admin_toast_ico').text(kind === 'err' ? '!' : '✓');
    $t.find('.admin_toast_txt').text(msg);
    $('#adminToasts').append($t);
    setTimeout(function(){ $t.addClass('is_hide'); setTimeout(function(){ $t.remove(); }, 220); }, 3000);
  }

  /* ---------- 저장 상태 ---------- */
  function saveState(key, state, txt){
    var $s = $('[data-save-state="' + key + '"]');
    $s.removeClass('is_busy is_ok is_err');
    if(!state) return;
    $s.addClass('is_' + state);
    $s.find('.admin_save_txt').text(txt || ({ busy:'저장 중…', ok:'저장했습니다', err:'저장 실패' }[state]));
    if(state === 'ok') setTimeout(function(){ $s.removeClass('is_ok'); }, 2500);
  }
  /* 퍼블 산출물의 mockSave/fakeRun 은 걷어냈다. 저장은 각 탭에서 실제 API를 부르고,
     결과가 온 뒤에 상태를 바꾼다 — 흉내 저장이 남아 있으면 실패해도 성공처럼 보인다. */

  /* ---------- 진행바 ---------- */
  function progress($p, opt){
    opt = opt || {};
    $p.addClass('is_shown').toggleClass('is_indeterminate', !!opt.indeterminate).toggleClass('is_err', !!opt.error);
    $p.find('.admin_progress_txt').text(opt.text || '');
    $p.find('.admin_progress_pct').text(opt.indeterminate || opt.pct == null ? '' : Math.round(opt.pct) + '%');
    $p.find('.admin_progress_bar').css('width', (opt.indeterminate ? 35 : (opt.pct || 0)) + '%');
  }

  /* ---------- 모드 ---------- */
  function applyMode(mode){
    MODE = mode;
    $('body').attr('data-mode', mode);
    $('#adminModeBadge').removeClass('is_serve is_studio')
      .addClass(mode === 'studio' ? 'is_studio' : 'is_serve')
      .text(mode === 'studio' ? '스튜디오' : '운영');
    $('[data-studio-only]').prop('hidden', mode !== 'studio');
    $('[data-serve-only]').prop('hidden', mode === 'studio');
    syncNavGroups();
    /* studio 전용 화면이 열려 있으면 홈으로 되돌립니다 */
    var $active = $('.admin_nav_item.is_active');
    if(mode !== 'studio' && $active.is('[data-studio-only]')) selectTab('flow');
    if(mode !== 'studio' && $('.admin_subtab.is_active').is('[data-studio-only]')) selectSubtab('matching');
    $('#qaModal').toggleClass('is_readonly', mode !== 'studio');
    /* serve 에서도 검수는 됩니다 — QA 편집이 막히는 것과 달리 승인은 운영에서 해야 합니다. */
    $('#panel_review').toggleClass('is_readonly', false);
    renderQa(); renderDocs(); renderFlow();
  }

  /* ---------- 탭 ---------- */
  function selectTab(key){
    var $item = $('.admin_nav_item[data-tab="' + key + '"]');
    if(!$item.length || $item.prop('hidden')) key = 'flow';
    $('.admin_nav_item').removeClass('is_active').removeAttr('aria-current');
    $('.admin_nav_item[data-tab="' + key + '"]').addClass('is_active').attr('aria-current','page');
    $('.admin_panel').removeClass('is_active');
    $('#panel_' + key).addClass('is_active');
    if(key === 'review') renderReview();
    if(key === 'flow') renderFlow();
    if(location.hash !== '#' + key) history.replaceState(null, '', '#' + key);
  }
  $('#adminNav').on('click', '.admin_nav_item', function(){ selectTab($(this).data('tab')); });
  $(document).on('click', '[data-goto-tab]', function(){ selectTab($(this).data('goto-tab')); });

  /* 그룹에 남은 항목이 하나도 없으면 그룹 라벨까지 숨깁니다 */
  function syncNavGroups(){
    $('.admin_nav_group').each(function(){
      var left = $(this).find('.admin_nav_item').filter(function(){ return !$(this).prop('hidden'); }).length;
      $(this).prop('hidden', left === 0);
    });
  }
  /* 검수 대기 배지 — 0이면 숨기고 100 이상은 99+ */
  function renderNavBadge(n){
    $('#navReviewBadge').prop('hidden', !n).text(n > 99 ? '99+' : n);
  }

  /* ---------- 설정 하위 탭 ---------- */
  function selectSubtab(key){
    var $t = $('.admin_subtab[data-subtab="' + key + '"]');
    if(!$t.length || $t.prop('hidden')) key = 'matching';
    $('.admin_subtab').removeClass('is_active').attr('aria-selected','false');
    $('.admin_subtab[data-subtab="' + key + '"]').addClass('is_active').attr('aria-selected','true');
    $('.admin_subpanel').removeClass('is_active');
    $('#subpanel_' + key).addClass('is_active');
  }
  $('#settingsSubtabs').on('click', '.admin_subtab', function(){ selectSubtab($(this).data('subtab')); });

  /* ---------- 브랜드 치환 (data-brand) ----------
     조직 이름을 마크업에 박지 않기 위한 장치입니다. 서버도 같은 치환을 하지만
     (app/main.py), 설정에서 값을 바꾼 직후 새로고침 없이 반영하려면 화면에도 있어야 합니다. */
  function applyBrand(){
    var v = {
      '{organization}':String(BRAND.organization || '').slice(0, 4),
      '{service_name}':BRAND.service_name || '',
      '{service_desc}':BRAND.service_desc || ''
    };
    $('[data-brand]').each(function(){
      var out = $(this).attr('data-brand');
      $.each(v, function(k, val){ out = out.split(k).join(val); });
      if(this.tagName.toLowerCase() === 'title') document.title = out;
      else $(this).text(out);
    });
    $('#profLogoPreview').text(v['{organization}']);
  }

  /* ---------- 페이지네이션 ---------- */
  function renderPager(key, total){
    var $p = $('[data-pager="' + key + '"]');
    var size = PAGE_SIZE[key], pages = Math.max(1, Math.ceil(total / size));
    if(PAGE[key] > pages) PAGE[key] = pages;
    var cur = PAGE[key];
    var from = total ? (cur - 1) * size + 1 : 0, to = Math.min(cur * size, total);
    var html = '<span class="admin_pager_info">' + num(from) + '–' + num(to) + ' / ' + num(total) + '건</span>' +
      '<span class="admin_pager_size">페이지당 <select class="admin_select" data-page-size aria-label="페이지당 건수">' +
      [20,50,100].map(function(s){ return '<option value="' + s + '"' + (s === size ? ' selected' : '') + '>' + s + '</option>'; }).join('') +
      '</select></span><span class="admin_pager_nums">' +
      '<button type="button" class="admin_pager_btn" data-page="' + (cur-1) + '"' + (cur === 1 ? ' disabled' : '') + '>‹</button>';
    var list = [];
    for(var i = 1; i <= pages; i++){
      if(i === 1 || i === pages || Math.abs(i - cur) <= 1) list.push(i);
      else if(list[list.length-1] !== '…') list.push('…');
    }
    $.each(list, function(_, p){
      html += p === '…' ? '<span class="admin_pager_gap">…</span>'
        : '<button type="button" class="admin_pager_btn' + (p === cur ? ' is_active' : '') + '" data-page="' + p + '">' + p + '</button>';
    });
    html += '<button type="button" class="admin_pager_btn" data-page="' + (cur+1) + '"' + (cur === pages ? ' disabled' : '') + '>›</button></span>';
    $p.html(html);
  }
  $(document).on('click', '[data-pager] [data-page]', function(){
    var key = $(this).closest('[data-pager]').data('pager');
    PAGE[key] = Number($(this).data('page'));
    RENDER[key]();
  });
  $(document).on('change', '[data-pager] [data-page-size]', function(){
    var key = $(this).closest('[data-pager]').data('pager');
    PAGE_SIZE[key] = Number($(this).val()); PAGE[key] = 1; RENDER[key]();
  });
  function paged(key, rows){
    var size = PAGE_SIZE[key], start = (PAGE[key] - 1) * size;
    return rows.slice(start, start + size);
  }
  function emptyState(key, isEmpty){
    $('[data-empty="' + key + '"]').toggleClass('is_shown', !!isEmpty);
    $('[data-table-wrap="' + key + '"] table').prop('hidden', !!isEmpty);
  }

  /* ---------- 검색 컴포넌트 ---------- */
  $(document).on('input', '.admin_search_input', function(){
    var $w = $(this).closest('.admin_search');
    $w.toggleClass('is_filled', !!$(this).val());
  });
  $(document).on('click', '[data-search-clear]', function(){
    var $w = $(this).closest('.admin_search');
    $w.removeClass('is_filled is_noresult').find('.admin_search_input').val('').trigger('input').trigger('change');
  });

  /* ---------- 정렬 헤더 ---------- */
  $(document).on('click', '.admin_th_sort', function(){
    var $th = $(this), $table = $th.closest('table');
    var key = $table.attr('id') === 'histTable' ? 'hist' : 'qa';
    var col = $th.data('sort');
    var dir = SORT[key].key === col && SORT[key].dir === 'desc' ? 'asc' : 'desc';
    SORT[key] = { key:col, dir:dir };
    $table.find('.admin_th_sort').removeClass('is_asc is_desc');
    $th.addClass(dir === 'asc' ? 'is_asc' : 'is_desc');
    RENDER[key]();
  });

  /* ---------- 드롭다운 메뉴 ---------- */
  $(document).on('click', '#anBulkBtn, #qaBulkBtn', function(e){
    e.stopPropagation();
    var $m = $(this).siblings('.admin_menu');
    $('.admin_menu').not($m).removeClass('is_open');
    var open = !$m.hasClass('is_open');
    $m.toggleClass('is_open', open);
    $(this).attr('aria-expanded', open ? 'true' : 'false');
  });
  $(document).on('click', '.admin_menu_item', function(){
    var act = $(this).data('act');
    var scope = $(this).closest('.admin_menu').data('menu');
    $(this).closest('.admin_menu').removeClass('is_open');
    if(scope === 'qa') return runQaBulk(act);
    runAnalyticsBulk(act);
  });

  /* ---------- 일괄 작업: QA ---------- */
  /* 행의 식별자는 QA 는 data-qa-id, 묶음은 data-cl-id 에 있다(퍼블 산출물 규약). */
  function checkedIds(key){
    return $('[data-check="' + key + '"]:checked').map(function(){
      return $(this).closest('tr').data(key === 'qa' ? 'qa-id' : 'cl-id');
    }).get();
  }

  function runQaBulk(act){
    var ids = checkedIds('qa');
    if(!ids.length){ toast('선택한 항목이 없습니다', 'err'); return; }

    var actions = { approve:'approve', hold:'hold', unuse:'disable', delete:'delete' };
    var labels = { approve:'검수 완료 처리했습니다', hold:'보류로 변경했습니다',
      unuse:'사용 안 함으로 변경했습니다', delete:'삭제했습니다' };
    var action = actions[act];
    if(!action){ toast('지원하지 않는 작업입니다', 'err'); return; }

    function send(){
      API.send('POST', '/api/admin/qa/bulk', { qa_ids:ids, action:action })
        .done(function(res){
          toast(labels[act] + ' (' + res.changed + '건)', 'ok');
          loadQa().done(renderQa);
        })
        .fail(function(xhr){ toast(apiError(xhr, '처리하지 못했습니다'), 'err'); });
    }

    if(act === 'delete'){
      askConfirm(ids.length + '건을 삭제할까요?', '삭제하면 되돌릴 수 없습니다.', true, send);
      return;
    }
    send();
  }

  /* ---------- 일괄 작업: 질문 분석 ---------- */
  function runAnalyticsBulk(act){
    var ids = checkedIds('an');
    if(!ids.length){ toast('선택한 묶음이 없습니다', 'err'); return; }

    /* 화면 메뉴 → 묶음 상태. 'QA 바로 생성'(gen)은 생성 탭으로 넘긴다. */
    var statuses = { mark:'reviewed', exclude:'excluded' };
    if(act === 'gen'){
      selectTab('generate');
      $('#genTargetRadio input[value="uncovered"]').prop('checked', true).trigger('change');
      toast('QA 생성 탭으로 이동했습니다. 대상과 모델을 확인하고 시작하세요', 'ok');
      return;
    }
    if(act === 'topic'){ toast('주제 지정은 묶음 행에서 카테고리를 선택하세요', 'err'); return; }

    API.send('POST', '/api/admin/analytics/override',
      { kind:'status', cluster_ids:ids, value:statuses[act] || 'reviewed' })
      .done(function(result){
        CLUSTERS = result.clusters || [];
        renderAn(); renderKpis();
        toast('처리했습니다 (' + ids.length + '건)', 'ok');
      })
      .fail(function(xhr){ toast(apiError(xhr, '처리하지 못했습니다'), 'err'); });
  }

  /* ---------- 모달 ---------- */
  function openModal(id){ $('#' + id).addClass('is_open'); }
  function closeModal($m){ $m.removeClass('is_open'); }
  $(document).on('click', '[data-modal-close]', function(){ closeModal($(this).closest('.qr_modal_backdrop')); });
  $(document).on('click', '.qr_modal_backdrop', function(e){
    if($(this).is('#authModal')) return;            /* 인증 전에는 갈 곳이 없습니다 */
    if(e.target === this) closeModal($(this));
  });
  $(document).on('keydown', function(e){
    if(e.key !== 'Escape') return;
    if($('#authModal').hasClass('is_open')) return; /* 인증 모달은 ESC로 닫히지 않습니다 */
    var $open = $('.qr_modal_backdrop.is_open').not('#authModal').last();
    if($open.length){ closeModal($open); return; }
    $('.admin_cat_popover.is_open').removeClass('is_open');
    $('.admin_menu').removeClass('is_open');
  });
  $(document).on('click', function(){
    $('.admin_menu').removeClass('is_open');
    $('.admin_cat_popover.is_open').removeClass('is_open')
      .closest('.admin_cat_pop_wrap').find('[data-cat-trigger]').attr('aria-expanded','false');
  });

  function askConfirm(msg, sub, danger, cb){
    var $m = $('#confirmModal');
    $m.find('.qr_modal').toggleClass('admin_confirm_danger', !!danger);
    $m.find('[data-bind=message]').text(msg);
    $m.find('[data-bind=sub]').text(sub || '');
    $('#confirmOk').removeClass('qr_pill_teal qr_pill_accent').addClass(danger ? 'qr_pill_accent' : 'qr_pill_teal')
      .text(danger ? '삭제' : '확인');
    confirmCb = cb;
    openModal('confirmModal');
  }
  $('#confirmOk').on('click', function(){
    closeModal($('#confirmModal'));
    if(confirmCb){ confirmCb(); confirmCb = null; }
  });

  /* ============================================================
     카테고리 팝오버 (공용 컴포넌트)
     ============================================================ */
  var CAT_PICKER_OPTS = {
    hist:{ special:[{ id:'', label:'카테고리 전체' },{ id:'__none', label:'미분류' }], dir:'down', emptyLabel:'카테고리 전체' },
    an:{ special:[{ id:'', label:'카테고리 전체' },{ id:'__none', label:'미분류' }], dir:'down', emptyLabel:'카테고리 전체' },
    qa:{ special:[{ id:'', label:'카테고리 전체' },{ id:'__none', label:'미분류' }], dir:'down', emptyLabel:'카테고리 전체' },
    qaModal:{ special:[], dir:'down', emptyLabel:'주제 선택' },
    revEd:{ special:[], dir:'down', emptyLabel:'주제 선택' },
    revFilter:{ special:[{ id:'', label:'주제 전체' },{ id:'__none', label:'미분류' }], dir:'down', emptyLabel:'주제 전체' },
    gen:{ special:[], dir:'down', emptyLabel:'카테고리 선택' },
    quick:{ special:[], dir:'up', multi:true, emptyLabel:'주제 추가' }
  };
  function catPicker($wrap){
    var name = $wrap.data('cat-picker');
    var opt = CAT_PICKER_OPTS[name] || { special:[], dir:'down' };
    var $pop = $wrap.find('.admin_cat_popover');
    if(!$pop.length){
      $pop = tpl('tpl_cat_popover').children();
      $pop.attr('data-open-dir', opt.dir).appendTo($wrap);
    }
    return { $wrap:$wrap, $pop:$pop, name:name, opt:opt };
  }
  function buildCatList(p, query){
    var q = $.trim(query || '').toLowerCase();
    var $list = p.$pop.find('[data-cat-list]').empty();
    var picked = p.opt.multi ? QUICK : [];
    var hit = 0;

    if(!q) $.each(p.opt.special, function(_, s){
      $('<button type="button" class="admin_cat_special"></button>')
        .attr('data-category-id', s.id).text(s.label).appendTo($list);
    });

    $.each(CATEGORY_GROUPS, function(_, g){
      var cats = g.categories.filter(function(c){ return !q || c.name.toLowerCase().indexOf(q) > -1; });
      if(q && !cats.length) return;
      hit += cats.length;
      var $g = $('<div class="admin_cat_group"></div>').attr('data-group-id', g.group_id);
      $('<button type="button" class="admin_cat_group_head"></button>')
        .attr('aria-expanded', q ? 'true' : 'false')
        .append('<span class="admin_cat_group_arrow" aria-hidden="true">▸</span>')
        .append($('<span class="admin_cat_group_name"></span>').text(g.group_name))
        .append($('<span class="admin_cat_group_count"></span>').text('(' + g.categories.length + ')'))
        .appendTo($g);
      var $items = $('<div class="admin_cat_items"></div>').appendTo($g);
      $.each(cats, function(_, c){
        var label = esc(c.name);
        if(q){
          var i = c.name.toLowerCase().indexOf(q);
          label = esc(c.name.slice(0,i)) + '<mark>' + esc(c.name.slice(i, i+q.length)) + '</mark>' + esc(c.name.slice(i+q.length));
        }
        $('<button type="button" class="admin_cat_item" role="option"></button>')
          .attr('data-category-id', c.category_id)
          .attr('aria-selected', 'false')
          .toggleClass('is_picked', picked.indexOf(c.category_id) > -1)
          .attr('title', c.name)
          .append($('<span class="admin_cat_item_txt"></span>').html(label))
          .append('<span class="admin_cat_item_check" aria-hidden="true">✓</span>')
          .appendTo($items);
      });
      if(q) $g.addClass('is_open');
      $g.appendTo($list);
    });
    p.$pop.toggleClass('is_empty', hit === 0);
  }
  $(document).on('click', '[data-cat-trigger]', function(e){
    e.stopPropagation();
    var p = catPicker($(this).closest('.admin_cat_pop_wrap'));
    var open = !p.$pop.hasClass('is_open');
    $('.admin_cat_popover').removeClass('is_open');
    if(open){ buildCatList(p, ''); p.$pop.find('[data-cat-search]').val(''); p.$pop.addClass('is_open'); }
    $(this).attr('aria-expanded', open ? 'true' : 'false');
  });
  $(document).on('click', '.admin_cat_popover', function(e){ e.stopPropagation(); });
  $(document).on('click', '[data-cat-close]', function(){
    $(this).closest('.admin_cat_popover').removeClass('is_open')
      .closest('.admin_cat_pop_wrap').find('[data-cat-trigger]').attr('aria-expanded','false');
  });
  $(document).on('input', '[data-cat-search]', function(){
    buildCatList(catPicker($(this).closest('.admin_cat_pop_wrap')), $(this).val());
  });
  $(document).on('click', '.admin_cat_group_head', function(){
    var $g = $(this).closest('.admin_cat_group').toggleClass('is_open');
    $(this).attr('aria-expanded', $g.hasClass('is_open') ? 'true' : 'false');
  });
  $(document).on('click', '.admin_cat_item, .admin_cat_special', function(){
    var $wrap = $(this).closest('.admin_cat_pop_wrap');
    var name = $wrap.data('cat-picker');
    var id = $(this).attr('data-category-id');
    var cat = findCat(id);
    var label = cat ? cat.name : $(this).text().trim();

    if(name === 'quick'){
      if(QUICK.indexOf(id) > -1) QUICK.splice(QUICK.indexOf(id), 1);
      else if(QUICK.length >= 6){ toast('자주 찾는 주제는 6개까지입니다', 'err'); return; }
      else QUICK.push(id);
      renderQuick();
      buildCatList(catPicker($wrap), $wrap.find('[data-cat-search]').val());
      $('#quickCard').addClass('is_dirty');
      return;
    }

    $wrap.find('.admin_cat_trigger_label').text(id ? label : (CAT_PICKER_OPTS[name] || {}).emptyLabel || '전체');
    $wrap.find('[data-cat-trigger]').toggleClass('is_active', !!id).attr('data-category-id', id);
    $wrap.find('.admin_cat_popover').removeClass('is_open');

    if(name === 'hist'){ FILTER.hist.cat = id; PAGE.hist = 1; renderHist(); }
    if(name === 'an'){ FILTER.an.cat = id; PAGE.an = 1; renderAn(); }
    if(name === 'qa'){ FILTER.qa.cat = id; PAGE.qa = 1; renderQa(); }
    if(name === 'qaModal'){ $('#qaModal').addClass('is_dirty'); }
    if(name === 'revFilter'){ REV.cat = id; REV.idx = 0; renderReview(); }
  });

  /* ============================================================
     ① 질문 이력
     ============================================================ */
  /* 값은 셋뿐입니다 — 👍 / 👎 / –(안 누름). 대부분은 `–` 입니다.
     👎 는 눈에 띄어야 하지만 **행 전체를 칠하지는 않습니다** — 오류가 아니라 신고입니다. */
  function fbCell(r){
    if(r.fb === 'up') return '<span class="admin_fb_badge is_up" title="도움이 됐어요">👍</span>';
    if(r.fb === 'down'){
      return '<span class="admin_fb_badge is_down" title="' + esc(r.fb_reason || '이유 없음') + '">👎</span>';
    }
    return '<span class="admin_fb_none">–</span>';
  }

  function histRows(){
    var f = FILTER.hist;
    var rows = HISTORY.filter(function(r){
      if(!f.test && r.is_test) return false;
      if(f.fb === 'down' && r.fb !== 'down') return false;
      if(f.rt && r.result_type !== f.rt) return false;
      if(f.cat === '__none' && r.category_id) return false;
      if(f.cat && f.cat !== '__none' && r.category_id !== f.cat) return false;
      if(f.q && r.question.toLowerCase().indexOf(f.q.toLowerCase()) < 0) return false;
      return true;
    });
    var s = SORT.hist, m = s.dir === 'asc' ? 1 : -1;
    rows.sort(function(a, b){
      if(s.key === 'score') return ((a.score || 0) - (b.score || 0)) * m;
      return (a.ts - b.ts) * m;
    });
    return rows;
  }
  function renderHist(){
    var rows = histRows();
    $('[data-search="hist"]').toggleClass('is_noresult', !!FILTER.hist.q && !rows.length);
    var html = paged('hist', rows).map(function(r){
      return '<tr class="is_clickable" data-hist-id="' + r.hist_id + '">' +
        '<td>' + r.ts_txt + '</td>' +
        '<td class="admin_td_ellip"><span class="admin_row_title">' + esc(r.question) + '</span>' +
          (r.is_test ? ' <span class="admin_st">테스트</span>' : '') + '</td>' +
        '<td>' + rtBadge(r.result_type) + '</td>' +
        '<td class="admin_td_ellip">' + (r.matched_qa ? esc(r.matched_qa.question) : '—') + '</td>' +
        '<td class="qr_num">' + (r.score == null ? '—' : r.score.toFixed(2)) + '</td>' +
        '<td>' + fbCell(r) + '</td>' +
        '<td class="admin_td_ellip">' + (r.category_name ? esc(r.category_name) : '<span style="color:var(--qr-mute)">—</span>') + '</td>' +
        '<td>' + r.channel + '</td></tr>';
    }).join('');
    $('#histBody').html(html);
    emptyState('hist', !rows.length);
    renderPager('hist', rows.length);
  }
  $('#histSearch').on('input', function(){ FILTER.hist.q = $(this).val(); PAGE.hist = 1; renderHist(); });
  $('#histIncludeTest').on('change', function(){ FILTER.hist.test = $(this).is(':checked'); PAGE.hist = 1; renderHist(); });
  $('#histFilters').on('click', '[data-rt]', function(){
    $('#histFilters [data-rt], #histFilters [data-fb]').removeClass('is_active');
    $(this).addClass('is_active');
    FILTER.hist.rt = $(this).data('rt'); FILTER.hist.fb = ''; PAGE.hist = 1; renderHist();
  });
  /* `👎만` 은 결과 유형 칩과 한 줄에 있지만 배타적으로 동작합니다 */
  $('#histFilters').on('click', '[data-fb]', function(){
    var on = $(this).hasClass('is_active');
    $('#histFilters [data-rt], #histFilters [data-fb]').removeClass('is_active');
    FILTER.hist.rt = '';
    FILTER.hist.fb = on ? '' : 'down';
    if(on) $('#histFilters [data-rt=""]').addClass('is_active');
    else $(this).addClass('is_active');
    PAGE.hist = 1; renderHist();
  });
  $('#histPeriod').on('change', function(){
    var custom = $(this).val() === 'custom';
    $('#histFrom, #histTo').prop('hidden', !custom);
    renderHist();
  });
  $('#histExport').on('click', function(){
    /* 서버가 만든 CSV를 그대로 받는다(엑셀용 BOM 포함). 화면에서 만들면 필터 조건이
       목록과 어긋나고, 500건 넘는 이력을 브라우저 메모리에 다시 쌓게 된다. */
    var f = FILTER.hist;
    var params = ['include_test=' + (f.test ? 'true' : 'false')];
    if(f.fb) params.push('feedback=' + encodeURIComponent(f.fb));
    if(f.rt) params.push('result_type=' + encodeURIComponent(f.rt));
    if(f.cat && f.cat !== '__none') params.push('category_id=' + encodeURIComponent(f.cat));
    if(f.q) params.push('keyword=' + encodeURIComponent(f.q));
    window.location.href = '/api/admin/questions/export?' + params.join('&');
  });

  $('#histBody').on('click', 'tr', function(){
    var id = $(this).data('hist-id');
    var r = HISTORY.filter(function(x){ return x.hist_id === id; })[0];
    if(!r) return;
    var $m = $('#histModal');
    $m.find('[data-bind=result_type]').html(rtBadge(r.result_type));
    $m.find('[data-bind=ts]').text(r.ts_txt);
    $m.find('[data-bind=channel]').text(r.channel + (r.is_test ? ' (테스트)' : ''));
    $m.find('[data-bind=category]').text(r.category_name || '선택하지 않음');
    $m.find('[data-bind=score]').text(r.score == null ? '—' : r.score.toFixed(2));
    $m.find('[data-bind=matched]').text(r.matched_qa ? r.matched_qa.question : '—');
    $m.find('[data-bind=ticket]').text(r.ticket || '—');
    $m.find('[data-bind=question]').text(r.question);

    var $b = $m.find('[data-bind=answer_bubble]');
    if(r.result_type === 'answer'){
      $b.html('<div class="admin_md">' + renderMarkdown(r.matched_qa.answer) + '</div>' + srcBox(r.matched_qa.sources) + verifiedMeta());
    } else if(r.result_type === 'related_docs'){
      $b.html('<div class="admin_md"><p>딱 맞는 답변을 찾지 못해 관련 문서를 안내했습니다.</p></div>' + srcBox(r.related.slice(0,3)));
    } else {
      $b.html('<div class="admin_md"><p>답변을 찾지 못해 담당자 문의로 접수했습니다.</p></div>');
    }
    $m.find('[data-open-qa]').prop('disabled', !r.matched_qa).off('click').on('click', function(){
      closeModal($m);
      if(r.matched_qa) openQaModal(r.matched_qa.qa_id);
    });
    openModal('histModal');
  });
  function srcBox(docs){
    return '<div class="admin_bubble_src"><p class="admin_bubble_src_label">출처</p><div class="admin_bubble_src_items">' +
      (docs || []).map(function(d){ return '<span class="admin_bubble_src_item"><span aria-hidden="true">📄</span>' + esc(d.title) + '</span>'; }).join('') +
      '</div></div>';
  }
  function verifiedMeta(){
    return '<p class="admin_bubble_meta"><span class="admin_bubble_verified">' +
      '<span class="admin_bubble_verified_ico" aria-hidden="true">✓</span> 담당자 검수 완료</span>' +
      '<span aria-hidden="true">·</span><span>AI가 작성한 답변입니다</span></p>';
  }

  /* ============================================================
     ② 질문 분석
     ============================================================ */
  function renderKpis(){
    var total = HISTORY.filter(function(r){ return !r.is_test; }).length;
    var answers = HISTORY.filter(function(r){ return !r.is_test && r.result_type === 'answer'; }).length;
    var gaps = CLUSTERS.filter(function(c){ return !c.has_qa; }).length;
    var kpis = [
      { label:'총 질문', value:num(total), delta:'+12.4% 전월 대비', cls:'is_neutral' },
      { label:'고유 질문(묶음)', value:num(CLUSTERS.length), delta:'+6 전월 대비', cls:'is_neutral' },
      { label:'적중률', value:(total ? (answers / total * 100).toFixed(1) : '0.0') + '%', delta:'+3.2%p', cls:'is_good' },
      { label:'QA 없음', value:num(gaps), delta:'-4 전월 대비', cls:'is_good', click:true, alert:true },
      { label:'평균 응답', value:'2.1초', delta:'+0.3초', cls:'is_bad' }
    ];
    $('#anKpis').html(kpis.map(function(k){
      return '<div class="admin_kpi' + (k.click ? ' is_clickable' : '') + (k.alert ? ' is_alert' : '') + '"' +
        (k.click ? ' data-kpi="nogap" role="button" tabindex="0"' : '') + '>' +
        '<p class="admin_kpi_label">' + k.label + '</p>' +
        '<p class="admin_kpi_value">' + k.value + '</p>' +
        '<p class="admin_kpi_delta ' + k.cls + '">' + k.delta + '</p></div>';
    }).join(''));
  }
  $('#anKpis').on('click', '[data-kpi]', function(){
    $('[data-anf]').removeClass('is_active'); $('[data-anf="nogap"]').addClass('is_active');
    FILTER.an.f = 'nogap'; PAGE.an = 1; renderAn();
  });

  function renderCharts(){
    var rows = HISTORY.filter(function(r){ return !r.is_test; });
    var c = { answer:0, related_docs:0, unresolved:0 };
    $.each(rows, function(_, r){ c[r.result_type]++; });
    var t = rows.length || 1;
    $('[data-chart="dist"]').html(
      '<div class="admin_stack">' +
        '<span class="admin_stack_seg is_answer" style="width:' + (c.answer/t*100) + '%"></span>' +
        '<span class="admin_stack_seg is_related" style="width:' + (c.related_docs/t*100) + '%"></span>' +
        '<span class="admin_stack_seg is_unresolved" style="width:' + (c.unresolved/t*100) + '%"></span>' +
      '</div><div class="admin_legend">' +
        ['answer','related_docs','unresolved'].map(function(k){
          var cls = k === 'answer' ? 'is_answer' : k === 'related_docs' ? 'is_related' : 'is_unresolved';
          return '<span class="admin_legend_item"><span class="admin_legend_dot ' + cls + '"></span>' + k +
            ' <span class="admin_legend_val">' + num(c[k]) + '</span> (' + (c[k]/t*100).toFixed(1) + '%)</span>';
        }).join('') + '</div>');

    /* 추이: 14일 — 실제 질문 이력에서 센다. 질문이 없는 날도 0으로 채워 선이 끊기지 않게 한다. */
    var days = [], W = 320, H = 100;
    var byDay = {};
    $.each(HISTORY, function(_, r){
      if(r.is_test) return;
      var key = fmtDate(r.ts);
      if(!byDay[key]) byDay[key] = { tot:0, un:0 };
      byDay[key].tot++;
      if(r.result_type === 'unresolved') byDay[key].un++;
    });
    var today = new Date();
    for(var i = 13; i >= 0; i--){
      var d = new Date(today.getFullYear(), today.getMonth(), today.getDate() - i);
      var hit = byDay[fmtDate(d)] || { tot:0, un:0 };
      days.push({ d:pad(d.getMonth()+1) + '/' + pad(d.getDate()), tot:hit.tot, un:hit.un });
    }
    var max = Math.max(1, Math.max.apply(null, days.map(function(x){ return x.tot; }))) * 1.15;
    function pts(key){
      return days.map(function(x, i){
        return (i / (days.length-1) * W).toFixed(1) + ',' + (H - x[key] / max * H).toFixed(1);
      }).join(' ');
    }
    $('[data-chart="trend"]').html(
      '<svg class="admin_trend" viewBox="0 0 ' + W + ' ' + (H + 14) + '" preserveAspectRatio="none" role="img" aria-label="일자별 질문 추이">' +
        '<line class="admin_trend_grid" x1="0" y1="' + H + '" x2="' + W + '" y2="' + H + '"></line>' +
        '<line class="admin_trend_grid" x1="0" y1="' + H/2 + '" x2="' + W + '" y2="' + H/2 + '"></line>' +
        '<polygon class="admin_trend_area" points="0,' + H + ' ' + pts('tot') + ' ' + W + ',' + H + '"></polygon>' +
        '<polyline class="admin_trend_line" points="' + pts('tot') + '"></polyline>' +
        '<polyline class="admin_trend_line2" points="' + pts('un') + '"></polyline>' +
        '<text class="admin_trend_lbl" x="0" y="' + (H+12) + '">' + days[0].d + '</text>' +
        '<text class="admin_trend_lbl" x="' + (W-28) + '" y="' + (H+12) + '">' + days[days.length-1].d + '</text>' +
      '</svg>' +
      '<div class="admin_legend"><span class="admin_legend_item"><span class="admin_legend_dot is_answer"></span>전체</span>' +
      '<span class="admin_legend_item"><span class="admin_legend_dot is_unresolved"></span>미해결</span></div>');

    /* QA 없는 상위 주제 TOP5 */
    var byCat = {};
    $.each(CLUSTERS.filter(function(c2){ return !c2.has_qa; }), function(_, c2){
      var k = c2.category_id || '__none';
      byCat[k] = byCat[k] || { id:k, name:c2.category_name, n:0 };
      byCat[k].n += c2.count;
    });
    var top = Object.keys(byCat).map(function(k){ return byCat[k]; })
      .sort(function(a,b){ return b.n - a.n; }).slice(0,5);
    var mx = top.length ? top[0].n : 1;
    $('[data-chart="topgap"]').html('<div class="admin_hbars">' + top.map(function(x){
      return '<button type="button" class="admin_hbar" data-topgap="' + x.id + '">' +
        '<span class="admin_hbar_label">' + esc(x.name) + '</span>' +
        '<span class="admin_hbar_val">' + num(x.n) + '</span>' +
        '<span class="admin_hbar_track"><span class="admin_hbar_fill" style="width:' + (x.n/mx*100) + '%"></span></span></button>';
    }).join('') + '</div>');
  }
  $('#anCharts').on('click', '[data-topgap]', function(){
    var id = $(this).data('topgap');
    FILTER.an.cat = id === '__none' ? '__none' : id;
    var cat = findCat(id);
    var $w = $('[data-cat-picker="an"]');
    $w.find('.admin_cat_trigger_label').text(cat ? cat.name : '미분류');
    $w.find('[data-cat-trigger]').addClass('is_active');
    PAGE.an = 1; renderAn();
  });

  function anRows(){
    var f = FILTER.an;
    var rows = CLUSTERS.filter(function(c){
      if(f.f === 'nogap' && c.has_qa) return false;
      if(f.f === 'new' && c.status !== 'new') return false;
      if(f.f === 'applied' && c.status !== 'applied') return false;
      if(f.cat === '__none' && c.category_id) return false;
      if(f.cat && f.cat !== '__none' && c.category_id !== f.cat) return false;
      return true;
    });
    rows.sort(function(a,b){
      if(f.sort === 'hit') return a.hit_rate - b.hit_rate;
      if(f.sort === 'recent') return a.cluster_id < b.cluster_id ? 1 : -1;
      return b.count - a.count;
    });
    return rows;
  }
  function renderAn(){
    var rows = anRows();
    $('#anCount').text(num(rows.length) + '개 묶음');
    $('#anBody').html(paged('an', rows).map(function(c){
      return '<tr data-cl-id="' + c.cluster_id + '">' +
        '<td class="admin_col_check"><input type="checkbox" data-check="an" aria-label="선택"></td>' +
        '<td><button type="button" class="admin_row_expand" data-expand aria-label="원문 질문 보기">▶</button></td>' +
        '<td class="admin_td_ellip"><span class="admin_row_title">' + esc(c.question) + '</span>' +
          '<span class="admin_row_sub"> · ' + esc(c.summary) + '</span></td>' +
        '<td class="qr_num">' + num(c.count) + '</td>' +
        '<td class="qr_num">' + c.hit_rate + '%</td>' +
        '<td>' + rtBadge(c.result_type) + '</td>' +
        '<td class="admin_td_ellip">' + (c.category_id ? esc(c.category_name) : '<span style="color:var(--qr-mute)">미분류</span>') + '</td>' +
        '<td>' + stBadge(CL_ST, c.status) + '</td>' +
        '<td><button type="button" class="qr_pill qr_pill_outline qr_pill_sm" data-cl-topic>주제</button></td></tr>';
    }).join(''));
    emptyState('an', !rows.length);
    renderPager('an', rows.length);
  }
  $('#anBody').on('click', '[data-expand]', function(e){
    e.stopPropagation();
    var $tr = $(this).closest('tr');
    var id = $tr.data('cl-id');
    if($tr.hasClass('is_open')){ $tr.removeClass('is_open').next('.admin_subrow').remove(); return; }
    var c = CLUSTERS.filter(function(x){ return x.cluster_id === id; })[0];
    $tr.addClass('is_open');
    $('<tr class="admin_subrow"><td colspan="9"><div class="admin_subrow_inner">' +
      c.members.map(function(m){
        return '<div class="admin_sub_item"><span class="admin_sub_item_txt">' + esc(m) + '</span>' +
          '<button type="button" class="qr_pill qr_pill_outline qr_pill_sm" data-cl-exclude>이 질문 제외</button></div>';
      }).join('') + '</div></td></tr>').insertAfter($tr);
  });
  $('#anBody').on('click', '[data-cl-exclude]', function(){
    /* 화면에서만 감춘다. 원문 1건을 통계에서 빼는 것은 다음 분석에서 다시 살아나므로,
       지금은 "이 표현은 무시하고 보겠다" 수준으로만 둔다(서버 저장은 묶음 단위 상태로 한다). */
    $(this).closest('.admin_sub_item').fadeOut(150, function(){ $(this).remove(); });
    toast('이 원문을 화면에서 감췄습니다', 'ok');
  });

  /* 묶음에 주제 지정 — 지정한 값은 다시 분석해도 살아남는다(서버 overrides). */
  $('#anBody').on('click', '[data-cl-topic]', function(e){
    e.stopPropagation();
    var clusterId = $(this).closest('tr').data('cl-id');
    var $picker = $('[data-cat-picker="an"] [data-cat-trigger]');
    var categoryId = $picker.attr('data-category-id');
    if(!categoryId || categoryId === '__none'){
      toast('상단 카테고리 선택에서 주제를 먼저 고른 뒤 눌러 주세요', 'err');
      return;
    }
    API.send('POST', '/api/admin/analytics/override',
      { kind:'category', cluster_ids:[clusterId], value:categoryId })
      .done(function(result){
        CLUSTERS = result.clusters || [];
        renderAn();
        toast('주제를 지정했습니다', 'ok');
      })
      .fail(function(xhr){ toast(apiError(xhr, '지정하지 못했습니다'), 'err'); });
  });
  $('#panel_analytics').on('click', '[data-anf]', function(){
    $('[data-anf]').removeClass('is_active'); $(this).addClass('is_active');
    FILTER.an.f = $(this).data('anf'); PAGE.an = 1; renderAn();
  });
  $('#anSort').on('change', function(){ FILTER.an.sort = $(this).val(); PAGE.an = 1; renderAn(); });

  function runAnalysis(){
    $('#anRunBtn').prop('disabled', true);
    /* 진행률을 폴링하지 않는다 — 임베딩을 다시 만들지 않아 수천 건도 수십 초면 끝난다.
       대신 '진행률 불명' 막대를 띄워 멈춘 것처럼 보이지 않게 한다. */
    progress($('#anProgress'), { indeterminate:true, text:'비슷한 질문 묶는 중…' });
    API.send('POST', '/api/admin/analytics/run')
      .done(function(result){
        CLUSTERS = (result.clusters || []);
        $('#anLastRun').text(result.last_run_at || '');
        progress($('#anProgress'), { pct:100, text:'완료' });
        renderKpis(); renderCharts(); renderAn(); renderGenTargets();
        var skipped = result.unembedded || 0;
        toast('분석을 완료했습니다 (질문 ' + num(result.log_count) + '건 → 묶음 ' + result.clusters.length + '개)' +
          (skipped > 0 ? ' · 임베딩이 없는 ' + skipped + '건은 제외' : ''), 'ok');
        setTimeout(function(){ $('#anProgress').removeClass('is_shown'); }, 900);
      })
      .fail(function(xhr){
        progress($('#anProgress'), { pct:0, text:'실패', error:true });
        toast(apiError(xhr, '분석에 실패했습니다'), 'err');
      })
      .always(function(){ $('#anRunBtn').prop('disabled', false); });
  }
  $('#anRunBtn').on('click', runAnalysis);
  $(document).on('click', '[data-run-analysis]', runAnalysis);

  /* ============================================================
     ③ 질문 카테고리
     ============================================================ */
  function renderQuick(){
    var $wrap = $('#quickChips').empty();
    $.each(QUICK, function(_, id){
      var c = findCat(id);
      if(!c) return;
      var $t = tpl('tpl_tag').children().addClass('is_drag').attr('draggable','true').attr('data-category-id', id);
      $t.prepend('<span class="admin_drag" aria-hidden="true">⠿</span>');
      $t.find('.admin_tag_txt').text(c.name);
      if(!c.used){ $t.addClass('is_warn').attr('title','미사용 카테고리 — 챗봇에는 표시되지 않습니다'); }
      $wrap.append($t);
    });
    var full = QUICK.length >= 6;
    $wrap.append('<span class="admin_cat_pop_wrap" data-cat-picker="quick">' +
      '<button type="button" class="qr_pill qr_pill_outline qr_pill_sm" data-cat-trigger aria-expanded="false"' +
      (full ? ' disabled' : '') + '>+ 주제 추가</button></span>');
    $('#quickCount').text(QUICK.length + ' / 6').toggleClass('is_full', full);
    $('#quickHint').prop('hidden', !full);
    var hasUnused = QUICK.some(function(id){ var c = findCat(id); return c && !c.used; });
    $('#quickCard').find('.admin_notice').remove();
    if(hasUnused) $('#quickChips').before('<p class="admin_notice is_warn">미사용 카테고리가 담겨 있습니다. 챗봇에는 표시되지 않습니다.</p>');
  }
  $('#quickChips').on('click', '[data-tag-remove]', function(){
    var id = $(this).closest('.admin_tag').data('category-id');
    QUICK.splice(QUICK.indexOf(id), 1);
    renderQuick(); $('#quickCard').addClass('is_dirty');
  });
  /* 카테고리는 트리 전체를 한 번에 저장한다(PUT). 서버가 중복 id·없는 자주찾는주제를 막는다.
     저장이 성공하면 서버가 돌려준 결과로 다시 그린다 — 화면이 임의로 낙관 반영하면
     서버가 거부한 값이 화면에만 남는다. */
  function saveCategories(key, $host, okMsg, after){
    saveState(key, 'busy');
    API.send('PUT', '/api/admin/categories', toCategoryStore())
      .done(function(store){
        mapCategories(store);
        saveState(key, 'ok');
        if($host) $host.removeClass('is_dirty');
        toast(okMsg, 'ok');
        renderAll();
        if(after) after();
      })
      .fail(function(xhr){
        saveState(key, 'err');
        toast(apiError(xhr, '저장하지 못했습니다'), 'err');
      });
  }

  $('#quickSave').on('click', function(){
    QUICK_CATEGORY_IDS = QUICK.slice();
    saveCategories('quick', $('#quickCard'), '자주 찾는 주제를 저장했습니다');
  });

  function renderTree(query){
    var q = $.trim(query || '').toLowerCase();
    var $tree = $('#catTree').empty();
    $.each(CATEGORY_GROUPS, function(_, g){
      var cats = g.categories.filter(function(c){ return !q || c.name.toLowerCase().indexOf(q) > -1; });
      if(q && !cats.length) return;
      var $g = $('<div class="admin_tree_group admin_cat_group"></div>')
        .attr('data-group-id', g.group_id).attr('draggable','true');
      $('<div class="admin_tree_group_head" style="display:flex;"></div>')
        .append('<span class="admin_drag" aria-hidden="true">⠿</span>')
        .append('<button type="button" class="admin_tree_group_head" style="padding:0;flex:1 1 auto;" data-group-toggle>' +
          '<span class="admin_cat_group_arrow" aria-hidden="true">▸</span>' +
          '<span class="admin_cat_group_name">' + esc(g.group_name) + '</span>' +
          '<span class="admin_cat_group_count">(' + g.categories.length + ')</span></button>')
        .append('<span class="admin_tree_group_actions"><button type="button" class="admin_icon_btn" data-group-edit="' + g.group_id + '" aria-label="대분류 수정">✎</button></span>')
        .appendTo($g);
      var $items = $('<div class="admin_tree_items"></div>').appendTo($g);
      $.each(cats, function(_, c){
        var label = esc(c.name);
        if(q){
          var i = c.name.toLowerCase().indexOf(q);
          label = esc(c.name.slice(0,i)) + '<mark>' + esc(c.name.slice(i,i+q.length)) + '</mark>' + esc(c.name.slice(i+q.length));
        }
        $('<button type="button" class="admin_tree_item" draggable="true"></button>')
          .attr('data-category-id', c.category_id)
          .toggleClass('is_unused', !c.used)
          .toggleClass('is_active', currentCat === c.category_id)
          .append('<span class="admin_drag" aria-hidden="true">⠿</span>')
          .append($('<span class="admin_tree_item_txt"></span>').html(label))
          .append(c.used ? '' : '<span class="admin_tree_item_badge">미사용</span>')
          .appendTo($items);
      });
      if(q || currentCat && cats.some(function(c){ return c.category_id === currentCat; })) $g.addClass('is_open');
      $tree.append($g);
    });
    if(!$tree.children().length) $tree.html('<p class="admin_cat_empty" style="display:block;">일치하는 카테고리가 없습니다.</p>');
  }
  $('#catSearch').on('input', function(){
    var v = $(this).val();
    $('[data-search="cat"]').toggleClass('is_noresult', !!v && !ALL_CATS.some(function(c){ return c.name.toLowerCase().indexOf(v.toLowerCase()) > -1; }));
    renderTree(v);
  });
  $('#catTree').on('click', '[data-group-toggle]', function(e){
    e.stopPropagation();
    $(this).closest('.admin_tree_group').toggleClass('is_open');
  });
  $('#catTree').on('click', '[data-group-edit]', function(e){
    e.stopPropagation(); openGroupModal($(this).data('group-edit'));
  });
  $('#catTree').on('click', '.admin_tree_item', function(){ selectCategory($(this).data('category-id')); });

  function selectCategory(id){
    var c = findCat(id);
    if(!c) return;
    currentCat = id;
    $('#catDetail').find('[data-empty="cat"]').removeClass('is_shown');
    $('#catDetail').find('[data-cat-form]').prop('hidden', false);
    $('#catDetail').removeClass('is_dirty');
    $('#catGroupSel').html(CATEGORY_GROUPS.map(function(g){
      return '<option value="' + g.group_id + '"' + (g.group_id === c.group_id ? ' selected' : '') + '>' + esc(g.group_name) + '</option>';
    }).join(''));
    $('#catName').val(c.name);
    $('#catId').val(c.category_id);
    $('#catUsed').prop('checked', !!c.used);
    renderCatQuestions(c.questions || []);
    renderTree($('#catSearch').val());
  }
  function renderCatQuestions(list){
    var $w = $('#catQuestions').empty();
    $.each(list, function(_, q){
      var $r = tpl('tpl_row_input').children();
      $r.find('.admin_input').val(q).attr('aria-label','추천 질문');
      $w.append($r);
    });
    $('#catQCount').text('(' + list.length + ')');
  }
  $('#catQAdd').on('click', function(){
    var $r = tpl('tpl_row_input').children();
    $r.find('.admin_input').attr('placeholder','추천 질문을 입력하세요').attr('aria-label','추천 질문');
    $('#catQuestions').append($r).scrollTop(99999);
    $r.find('.admin_input').trigger('focus');
    $('#catQCount').text('(' + $('#catQuestions').children().length + ')');
    $('#catDetail').addClass('is_dirty');
  });
  $('#catQuestions').on('click', '[data-row-remove]', function(){
    $(this).closest('.admin_row_item').remove();
    $('#catQCount').text('(' + $('#catQuestions').children().length + ')');
    $('#catDetail').addClass('is_dirty');
  });
  $('#catDetail').on('input change', '.admin_input, .admin_select, #catUsed', function(){ $('#catDetail').addClass('is_dirty'); });
  $('#catSave').on('click', function(){
    var id = $.trim($('#catId').val());
    var name = $.trim($('#catName').val());
    if(!id || !name){ toast('카테고리 ID와 이름을 입력해 주세요', 'err'); return; }

    var payload = {
      category_id:id, name:name, used:$('#catUsed').is(':checked'),
      questions:$('#catQuestions .admin_input').map(function(){ return $.trim($(this).val()); }).get()
        .filter(function(q){ return q; })
    };
    var groupId = $('#catGroupSel').val();

    /* 화면 배열을 먼저 고치고 트리 전체를 보낸다. 대분류를 바꾼 경우 옮기기까지 한다. */
    $.each(CATEGORY_GROUPS, function(_, g){
      g.categories = g.categories.filter(function(c){ return c.category_id !== id; });
    });
    var target = CATEGORY_GROUPS.filter(function(g){ return g.group_id === groupId; })[0];
    if(!target){ toast('대분류를 선택해 주세요', 'err'); return; }
    target.categories.push(payload);
    rebuildCats();

    saveCategories('cat', $('#catDetail'), '카테고리를 저장했습니다', function(){ selectCategory(id); });
  });
  $('#catCancel').on('click', function(){ if(currentCat) selectCategory(currentCat); });
  $('#catDelete').on('click', function(){
    var id = $.trim($('#catId').val());
    if(!id) return;
    askConfirm('이 카테고리를 삭제할까요?', '추천 질문도 함께 삭제됩니다. 자주 찾는 주제에 있으면 함께 빠집니다.', true, function(){
      $.each(CATEGORY_GROUPS, function(_, g){
        g.categories = g.categories.filter(function(c){ return c.category_id !== id; });
      });
      /* 없는 카테고리가 자주 찾는 주제에 남으면 서버가 거부한다(400). 여기서 함께 뺀다. */
      QUICK_CATEGORY_IDS = QUICK_CATEGORY_IDS.filter(function(q){ return q !== id; });
      QUICK = QUICK.filter(function(q){ return q !== id; });
      rebuildCats();
      currentCat = null;
      saveCategories('cat', $('#catDetail'), '삭제했습니다', function(){
        $('#catDetail').find('[data-cat-form]').prop('hidden', true);
        $('#catDetail').find('[data-empty="cat"]').addClass('is_shown');
      });
    });
  });
  $('#catAddItem').on('click', function(){
    $('#catDetail').find('[data-empty="cat"]').removeClass('is_shown');
    $('#catDetail').find('[data-cat-form]').prop('hidden', false);
    currentCat = null;
    $('#catGroupSel').html(CATEGORY_GROUPS.map(function(g){ return '<option value="' + g.group_id + '">' + esc(g.group_name) + '</option>'; }).join(''));
    $('#catName').val(''); $('#catId').val('').prop('readonly', false).attr('placeholder','c_xxx');
    $('#catUsed').prop('checked', true);
    renderCatQuestions([]);
    $('#catName').trigger('focus');
  });

  function openGroupModal(groupId){
    var g = findGroup(groupId);
    $('#catGroupModalTitle').text(g ? '대분류 수정' : '대분류 추가');
    $('#catGroupName').val(g ? g.group_name : '');
    $('#catGroupId').val(g ? g.group_id : '').prop('readonly', !!g);
    $('#catGroupUsed').prop('checked', g ? !!g.used : true);
    $('#catGroupDelete').prop('hidden', !g);
    $('#catGroupWarn').prop('hidden', !g);
    if(g) $('#catGroupWarn').find('[data-bind=child_count]').text(g.categories.length);
    openModal('catGroupModal');
  }
  $('#catAddGroup').on('click', function(){ openGroupModal(null); });
  $('#catGroupSave').on('click', function(){
    var id = $.trim($('#catGroupId').val());
    var name = $.trim($('#catGroupName').val());
    if(!id || !name){ toast('대분류 ID와 이름을 입력해 주세요', 'err'); return; }

    var g = findGroup(id);
    if(g){
      g.group_name = name;
      g.used = $('#catGroupUsed').is(':checked');
    } else {
      CATEGORY_GROUPS.push({ group_id:id, group_name:name, used:$('#catGroupUsed').is(':checked'), categories:[] });
    }
    rebuildCats();
    saveCategories('cat', null, '대분류를 저장했습니다', function(){ closeModal($('#catGroupModal')); });
  });

  $('#catGroupDelete').on('click', function(){
    var id = $.trim($('#catGroupId').val());
    var g = findGroup(id);
    if(!g) return;
    var n = g.categories.length;
    askConfirm('대분류를 삭제할까요?', '하위 카테고리 ' + n + '개가 함께 사라집니다.', true, function(){
      var goneIds = g.categories.map(function(c){ return c.category_id; });
      CATEGORY_GROUPS = CATEGORY_GROUPS.filter(function(x){ return x.group_id !== id; });
      QUICK_CATEGORY_IDS = QUICK_CATEGORY_IDS.filter(function(q){ return goneIds.indexOf(q) < 0; });
      QUICK = QUICK.filter(function(q){ return goneIds.indexOf(q) < 0; });
      rebuildCats();
      saveCategories('cat', null, '삭제했습니다', function(){ closeModal($('#catGroupModal')); });
    });
  });

  /* ============================================================
     ④ QA 인덱스
     ============================================================ */
  function renderQaSummary(){
    var n = function(f){ return QA_ITEMS.filter(f).length; };
    var vs = QA_ITEMS.reduce(function(a, q){ return a + q.variants.length; }, 0);
    var tiles = [
      { f:'', label:'전체', value:num(QA_ITEMS.length) },
      { f:'done', label:'검수완료', value:num(n(function(q){ return q.status === 'done'; })) },
      { f:'wait', label:'검수대기', value:num(n(function(q){ return q.status === 'wait'; })) },
      { f:'hold', label:'보류', value:num(n(function(q){ return q.status === 'hold'; })) },
      { f:null, label:'변형 질문', value:num(vs) }
    ];
    $('#qaSummary').html(tiles.map(function(t){
      return '<div class="admin_sum' + (FILTER.qa.f === t.f ? ' is_active' : '') + '"' +
        (t.f === null ? '' : ' data-qasum="' + t.f + '" role="button" tabindex="0"') + '>' +
        '<p class="admin_sum_label">' + t.label + '</p><p class="admin_sum_value">' + t.value + '</p></div>';
    }).join(''));
  }
  $('#qaSummary').on('click', '[data-qasum]', function(){
    var f = $(this).data('qasum');
    FILTER.qa.f = f === 'done' ? 'done' : f;
    $('[data-qaf]').removeClass('is_active');
    $('[data-qaf="' + f + '"]').addClass('is_active');
    if(!f) $('[data-qaf=""]').addClass('is_active');
    PAGE.qa = 1; renderQa();
  });

  function qaRows(){
    var f = FILTER.qa;
    var rows = QA_ITEMS.filter(function(q){
      if(f.f && q.status !== f.f) return false;
      if(f.cat === '__none' && q.category_id) return false;
      if(f.cat && f.cat !== '__none' && q.category_id !== f.cat) return false;
      if(f.q){
        var s = f.q.toLowerCase();
        if(q.question.toLowerCase().indexOf(s) < 0 && q.answer.toLowerCase().indexOf(s) < 0) return false;
      }
      return true;
    });
    var s = SORT.qa, m = s.dir === 'asc' ? 1 : -1;
    rows.sort(function(a,b){
      if(s.key === 'variants') return (a.variants.length - b.variants.length) * m;
      if(s.key === 'recent') return (a.updated < b.updated ? -1 : 1) * m;
      return (a.hit - b.hit) * m;
    });
    return rows;
  }
  function renderQa(){
    var rows = qaRows();
    $('[data-search="qa"]').toggleClass('is_noresult', !!FILTER.qa.q && !rows.length);
    var studio = MODE === 'studio';
    $('#qaBody').html(paged('qa', rows).map(function(q){
      return '<tr class="is_clickable' + (q.status === 'unused' ? ' is_muted' : '') + '" data-qa-id="' + q.qa_id + '">' +
        (studio ? '<td class="admin_col_check"><input type="checkbox" data-check="qa" aria-label="선택"></td>' : '') +
        '<td class="admin_td_ellip"><span class="admin_row_title">' + esc(q.question) + '</span></td>' +
        '<td class="admin_td_ellip">' + esc(plain(q.answer).slice(0, 90)) + '</td>' +
        '<td class="admin_td_ellip">' + esc(q.category_name) + '</td>' +
        '<td class="qr_num">' + q.variants.length + '</td>' +
        '<td class="qr_num">' + num(q.hit) + '</td>' +
        '<td>' + stBadge(QA_ST, q.status) + '</td></tr>';
    }).join(''));
    emptyState('qa', !rows.length);
    renderPager('qa', rows.length);
    renderQaSummary();
  }
  $('#qaSearch').on('input', function(){ FILTER.qa.q = $(this).val(); PAGE.qa = 1; renderQa(); });
  $('#qaFilters').on('click', '[data-qaf]', function(){
    $('[data-qaf]').removeClass('is_active'); $(this).addClass('is_active');
    FILTER.qa.f = $(this).data('qaf'); PAGE.qa = 1; renderQa();
  });
  $('#qaSort').on('change', function(){
    SORT.qa = { key:$(this).val(), dir:'desc' };
    $('#qaTable .admin_th_sort').removeClass('is_asc is_desc');
    $('#qaTable .admin_th_sort[data-sort="' + $(this).val() + '"]').addClass('is_desc');
    renderQa();
  });
  $('#qaBody').on('click', 'tr', function(e){
    if($(e.target).is('input[type=checkbox]')) return;
    openQaModal($(this).data('qa-id'));
  });

  /* ============================================================
     공용 QA 편집 컴포넌트 (.admin_editor)
     QA 검수 모달과 검수 화면이 **같은 마크업 · 같은 함수**를 씁니다.
     두 벌로 두면 한쪽만 고쳐지고, 검수자가 본 모습과 사용자가 보는 모습이 갈립니다.
     ============================================================ */
  var ED_IDS = {
    qa:{ question:'qaMainQuestion', answer:'qaAnswerEditor', preview:'qaPreview', variants:'qaVariants',
         variantInput:'qaVariantInput', category:'qaCategorySel', sources:'qaSources', score:'qaScore', note:'qaNote' },
    rev:{ question:'revQuestion', answer:'revAnswer', preview:'revPreview', variants:'revVariants',
          variantInput:'revVariantInput', category:'revCategorySel', sources:'revSources', score:'revScore', note:'revNote' }
  };
  var ED_PICKER = { qa:'qaModal', rev:'revEd' };

  function mountEditor(which){
    var $host = $('.admin_editor[data-editor="' + which + '"]');
    if(!$host.children().length){
      $host.append(tpl('tpl_qa_editor')).attr('data-ed-which', which);
      $.each(ED_IDS[which], function(key, id){ $host.find('[data-ed="' + key + '"]').attr('id', id); });
      $host.find('.admin_cat_pop_wrap').attr('data-cat-picker', ED_PICKER[which]);
    }
    return $host;
  }
  function ed($host, key){ return $host.find('[data-ed="' + key + '"]'); }
  function edWhich($host){ return $host.attr('data-ed-which'); }
  function edDirty($host){ if(edWhich($host) === 'qa') $('#qaModal').addClass('is_dirty'); }

  function fillEditor($host, item){
    ed($host,'question').val(item.question);
    ed($host,'answer').val(item.answer);
    ed($host,'note').val(item.note || '');
    ed($host,'variantInput').val('');
    var $w = $host.find('.admin_cat_pop_wrap');
    $w.find('.admin_cat_trigger_label').text(item.category_name || '주제 선택');
    $w.find('[data-cat-trigger]')
      .toggleClass('is_active', !!item.category_id)
      .attr('data-category-id', item.category_id || '');
    renderEdSources($host, item.sources || []);
    renderEdVariants($host, item.variants || []);
    renderEdScore($host, item);
    renderEdFeedback($host, item);
    renderEdPreview($host);
  }

  /* 사용자 신고 (요청서 10 C) — 0건이면 영역을 통째로 감춥니다. 대부분이 여기 해당합니다.
     숫자보다 **질문 원문**이 핵심입니다. 검수자는 그걸 보고 "이 표현이 안 걸리는구나"를
     알고 변형 질문을 추가합니다. 여기서 QA 상태가 바뀌는 일은 없습니다. */
  function renderEdFeedback($host, item){
    var list = (item && item.reports) || [];
    var $w = ed($host,'feedback').prop('hidden', !list.length).removeClass('is_open');
    ed($host,'feedbackToggle').attr('aria-expanded','false');
    if(!list.length) return;

    ed($host,'feedbackCount').text('👎 ' + num(item.report_count || list.length));

    var tally = {};
    $.each(list, function(_, r){
      var label = r.reason_label || '이유 없음';
      tally[label] = (tally[label] || 0) + 1;
    });
    ed($host,'feedbackReasons').text($.map(tally, function(n, k){ return k + ' ' + n; }).join(' · '));

    ed($host,'feedbackItems').html(list.slice(0, 5).map(function(r){
      var score = r.similarity == null ? '—' : r.similarity.toFixed(2);
      return '<div class="admin_fb_item"><span class="admin_fb_item_at">' + esc((r.asked_at || '').slice(5, 16)) + '</span>' +
        '<span class="admin_fb_item_q" title="' + esc(r.question) + '">"' + esc(r.question) + '"</span>' +
        '<span class="admin_fb_item_score">' + score + '</span></div>';
    }).join(''));
    ed($host,'feedbackAll').prop('hidden', list.length <= 5);
  }
  /* 질문 이력으로 넘어갈 때 `👎만` 을 켜 준다 — 켜지 않으면 전체 목록에서 다시 찾아야 한다 */
  $(document).on('click', '.admin_editor [data-ed="feedbackAll"]', function(){
    if(!$('#histFilters [data-fb="down"]').hasClass('is_active')){
      $('#histFilters [data-fb="down"]').trigger('click');
    }
  });
  /* 접힘이 기본입니다 — 검수 화면은 이미 세로가 깁니다 */
  $(document).on('click', '.admin_editor [data-ed="feedbackToggle"]', function(){
    var open = $(this).closest('.admin_ed_feedback').toggleClass('is_open').hasClass('is_open');
    $(this).attr('aria-expanded', open ? 'true' : 'false');
  });

  /* 채점이 없으면 **0점이 아니라 '채점 없음'** 입니다. 0을 점수로 보여주면 검수자가
     최악 판정으로 읽습니다(app/studio/judge.py 의 NOT_JUDGED). */
  function renderEdScore($host, item){
    var $s = ed($host,'score').removeClass('is_low is_none');
    if(item.score == null){
      $s.addClass('is_none');
      $s.find('.admin_ed_score_val').text('채점 없음');
      $s.find('.admin_ed_score_why').text('');
      return;
    }
    if(item.score < 4) $s.addClass('is_low');
    $s.find('.admin_ed_score_val').text(item.score + '점');
    $s.find('.admin_ed_score_why').text([item.score_model, item.score_why].filter(Boolean).join(' · '));
  }

  /* 출처 배지 — 누르면 근거 발췌를 접었다 폅니다. 검수자가 원문과 대조하는 자리입니다. */
  function renderEdSources($host, docs){
    var $w = ed($host,'sources').empty();
    $.each(docs, function(_, d){ $w.append(edSourceItem(d.doc_id, d.title)); });
    if(!docs.length) $w.html('<p class="admin_card_sub">연결된 문서가 없습니다.</p>');
  }
  function edSourceItem(docId, title){
    var $s = tpl('tpl_src_item').children().attr('data-doc-id', docId);
    $s.find('.admin_src_name').text(title || docId);
    $s.find('.admin_src_excerpt').text('펼치면 원문을 불러옵니다.');
    return $s;
  }

  function renderEdVariants($host, list){
    var $w = ed($host,'variants').empty();
    $.each(list, function(_, v){
      var $r = tpl('tpl_row_input').children();
      $r.find('.admin_input').val(v).attr('aria-label','변형 질문');
      $w.append($r);
    });
    edCountVariants($host);
  }
  function edCountVariants($host){
    ed($host,'variantCount').text('(' + ed($host,'variants').children().length + ')');
    edMarkDup($host);
  }
  function edMarkDup($host){
    var seen = {};
    ed($host,'variants').children().each(function(){
      var v = $.trim($(this).find('.admin_input').val()).toLowerCase();
      var dup = !!v && seen[v];
      seen[v] = true;
      $(this).toggleClass('is_dup', !!dup);
    });
  }
  function edAddVariant($host, text){
    var v = $.trim(text != null ? text : ed($host,'variantInput').val());
    if(!v) return;
    var $r = tpl('tpl_row_input').children();
    $r.find('.admin_input').val(v).attr('aria-label','변형 질문');
    ed($host,'variants').append($r).scrollTop(99999);
    ed($host,'variantInput').val('').trigger('focus');
    edCountVariants($host); edDirty($host);
  }

  /* 미리보기는 챗봇 말풍선과 렌더 규칙이 같아야 합니다 — 다르면 검수가 의미를 잃습니다. */
  function renderEdPreview($host){
    var md = ed($host,'answer').val();
    var $p = ed($host,'preview');
    if(!$.trim(md)){
      $p.html('<p class="admin_preview_empty">답변을 입력하면 이곳에 사용자 화면 그대로 표시됩니다.</p>');
      return;
    }
    var docs = ed($host,'sources').find('.admin_src_item').map(function(){
      return { title:$(this).find('.admin_src_name').text() };
    }).get();
    var verified = edWhich($host) === 'qa' && $('#qaStatus').val() === 'done';
    $p.html('<div class="admin_bubble"><div class="admin_md">' + renderMarkdown(md) + '</div>' +
      (docs.length ? srcBox(docs) : '') + (verified ? verifiedMeta() : '') + '</div>');
  }

  /* ---------- 편집기 공통 이벤트 (두 곳 모두) ---------- */
  var edPreviewTimer = null;
  $(document).on('input', '.admin_editor [data-ed="answer"]', function(){
    var $host = $(this).closest('.admin_editor');
    edDirty($host);
    clearTimeout(edPreviewTimer);
    edPreviewTimer = setTimeout(function(){ renderEdPreview($host); }, 300);
  });
  $(document).on('input', '.admin_editor [data-ed="question"], .admin_editor [data-ed="note"]', function(){
    edDirty($(this).closest('.admin_editor'));
  });
  $(document).on('click', '.admin_editor [data-ed="variantAdd"]', function(){
    edAddVariant($(this).closest('.admin_editor'));
  });
  $(document).on('keydown', '.admin_editor [data-ed="variantInput"]', function(e){
    if(e.key !== 'Enter') return;
    e.preventDefault();
    edAddVariant($(this).closest('.admin_editor'));
  });
  $(document).on('input', '.admin_editor [data-ed="variants"] .admin_input', function(){
    var $host = $(this).closest('.admin_editor');
    edMarkDup($host); edDirty($host);
  });
  $(document).on('click', '.admin_editor [data-ed="variants"] [data-row-remove]', function(){
    var $host = $(this).closest('.admin_editor');
    $(this).closest('.admin_row_item').remove();
    edCountVariants($host); edDirty($host);
  });

  /* 발췌는 펼칠 때 받아옵니다. 검수 한 건마다 문서 3개를 미리 받으면 화면 전환이 느려집니다. */
  $(document).on('click', '.admin_editor [data-src-toggle]', function(e){
    if($(e.target).is('[data-tag-remove]')) return;
    var $item = $(this).closest('.admin_src_item').toggleClass('is_open');
    if(!$item.hasClass('is_open') || $item.data('loaded')) return;
    var id = $item.attr('data-doc-id');
    $item.data('loaded', true);
    API.get('/api/admin/docs/' + encodeURIComponent(id))
      .done(function(d){ $item.find('.admin_src_excerpt').text((d.content || '').slice(0, 600)); })
      .fail(function(){ $item.find('.admin_src_excerpt').text('발췌를 불러오지 못했습니다.'); });
  });
  $(document).on('click', '.admin_editor [data-tag-remove]', function(e){
    e.stopPropagation();
    var $host = $(this).closest('.admin_editor');
    $(this).closest('.admin_src_item').remove();
    renderEdPreview($host); edDirty($host);
  });

  $(document).on('click', '.admin_editor [data-ed="variantGen"]', function(){
    var $host = $(this).closest('.admin_editor');
    var key = edWhich($host);
    var base = $.trim(ed($host,'question').val());
    if(!base){ toast('대표 질문을 먼저 입력해 주세요', 'err'); return; }

    saveState(key, 'busy', '변형 질문 생성 중…');
    /* LLM 호출 한 번입니다. 모델이 크면 10~30초 걸립니다. */
    API.send('POST', '/api/studio/generate/variants', { question:base, count:10 })
      .done(function(variants){
        var exists = ed($host,'variants').find('.admin_input').map(function(){ return $.trim($(this).val()); }).get();
        var added = 0;
        $.each(variants, function(_, v){
          if(exists.indexOf(v) > -1) return;   /* 이미 있는 것은 넣지 않습니다 */
          var $r = tpl('tpl_row_input').children();
          $r.find('.admin_input').val(v).attr('aria-label','변형 질문');
          ed($host,'variants').append($r);
          added++;
        });
        edCountVariants($host);
        saveState(key, null);
        edDirty($host);
        toast('변형 질문 ' + added + '개를 추가했습니다. 저장해야 반영됩니다', 'ok');
      })
      .fail(function(xhr){
        saveState(key, 'err');
        toast(apiError(xhr, '변형 질문을 만들지 못했습니다'), 'err');
      });
  });

  /* 출처 문서 추가 — 어떤 편집기에서 열었는지 기억합니다 */
  var $pickHost = null;
  $(document).on('click', '.admin_editor [data-ed="sourceAdd"]', function(){
    $pickHost = $(this).closest('.admin_editor');
    $('#docPickList').html(DOCS.map(function(d){
      return '<label class="admin_check" style="display:flex;padding:6px 2px;">' +
        '<input type="checkbox" value="' + d.doc_id + '"> <span>' + esc(d.doc_id) + ' · ' + esc(d.title) + '</span></label>';
    }).join(''));
    openModal('docPickModal');
  });
  $('#docPickSearch').on('input', function(){
    var v = $(this).val().toLowerCase();
    $('#docPickList label').each(function(){
      $(this).toggle($(this).text().toLowerCase().indexOf(v) > -1);
    });
  });
  $('#docPickApply').on('click', function(){
    if(!$pickHost) return closeModal($('#docPickModal'));
    var $w = ed($pickHost,'sources');
    if(!$w.find('.admin_src_item').length) $w.empty();
    $('#docPickList input:checked').each(function(){
      var id = $(this).val();
      if($w.find('.admin_src_item[data-doc-id="' + id + '"]').length) return;
      var d = DOCS.filter(function(x){ return x.doc_id === id; })[0] || { doc_id:id, title:id };
      $w.append(edSourceItem(id, d.title));
    });
    closeModal($('#docPickModal'));
    renderEdPreview($pickHost); edDirty($pickHost);
  });

  /* 편집기 → 저장 요청. 상태는 화면 값(done/wait/…)을 서버 값으로 바꿔 보냅니다. */
  function collectEditor($host, item, status){
    return {
      qa_id:item ? item.qa_id : null,
      question:$.trim(ed($host,'question').val()),
      answer:ed($host,'answer').val(),
      variants:ed($host,'variants').find('.admin_input').map(function(){ return $.trim($(this).val()); }).get()
        .filter(function(v){ return v; }),
      /* 검수 중에 주제를 바꿨을 수 있습니다. 팝오버가 남긴 값을 먼저 봅니다. */
      category_id:$host.find('[data-cat-trigger]').attr('data-category-id') || (item && item.category_id) || null,
      source_doc_ids:ed($host,'sources').find('.admin_src_item').map(function(){ return $(this).attr('data-doc-id'); }).get(),
      note:ed($host,'note').val(),
      status:QA_STATUS_TO_API[status] || 'pending',
      created_by:'human'
    };
  }

  /* QA 목록이 바뀌면 검수 큐와 진행 현황도 같이 바뀝니다. 한 곳만 갱신하면
     사이드바 배지와 실제 대기 건수가 어긋납니다. */
  function refreshQaAndFlow(){
    return loadQa()
      .done(function(){ renderQa(); renderReview(); })
      .then(loadFlow)
      .done(renderFlow);
  }

  /* 무언가를 바꿨으면 진행 현황도 함께 다시 읽습니다. 안 그러면 그 화면으로 넘어갔을 때
     옛 숫자가 남아 있고, 새로고침해야 바뀝니다 — 값이 틀린 화면은 없는 화면보다 나쁩니다. */
  function refreshFlow(){
    return loadFlow().done(renderFlow);
  }

  /* ---------- QA 검수 모달 ---------- */
  function openQaModal(id, override){
    var q = QA_ITEMS.filter(function(x){ return x.qa_id === id; })[0];
    if(!q) return;

    /* 목록 응답에는 답변 전문과 변형 질문이 없습니다(80건이면 수백 KB). 열 때 한 건만 받아옵니다. */
    if(!q.answer_loaded){
      API.get('/api/admin/qa/' + encodeURIComponent(id))
        .done(function(full){
          $.extend(q, mapQa(full), { answer_loaded:true });
          renderQaModal(q, override);
        })
        .fail(function(xhr){ toast(apiError(xhr, 'QA 항목을 불러오지 못했습니다'), 'err'); });
      return;
    }
    renderQaModal(q, override);
  }

  function renderQaModal(q, override){
    currentQa = q;
    var readonly = MODE !== 'studio' || (override && override.readonly);
    var $m = $('#qaModal').removeClass('is_dirty');
    var $host = mountEditor('qa');

    $('#qaStatus').val((override && override.status) || q.status);
    fillEditor($host, mapReviewItem(q));

    $m.find('input, textarea, select').prop('disabled', readonly);
    $m.find('#qaSaveBtn, #qaApproveBtn, #qaDiscardBtn').prop('hidden', readonly);
    $host.find('[data-ed="variantAdd"], [data-ed="variantGen"], [data-ed="sourceAdd"]').prop('hidden', readonly);
    $host.find('[data-row-remove], [data-tag-remove]').prop('hidden', readonly);
    $('#qaModalTitle').text(readonly ? 'QA 항목 보기 (읽기 전용)' : 'QA 항목 검수');
    openModal('qaModal');
  }
  $('#qaStatus').on('change', function(){
    $('#qaModal').addClass('is_dirty');
    renderEdPreview(mountEditor('qa'));
  });

  function saveQa(status, okMsg, close){
    saveState('qa', 'busy');
    API.send('POST', '/api/admin/qa',
             collectEditor(mountEditor('qa'), currentQa, status || $('#qaStatus').val()))
      .done(function(){
        saveState('qa', 'ok');
        $('#qaModal').removeClass('is_dirty');
        if(status) $('#qaStatus').val(status);
        toast(okMsg, 'ok');
        if(close) closeModal($('#qaModal'));
        /* 저장 뒤 목록을 다시 받습니다 — 승인하면 검색 대상이 바뀌므로 요약 타일도 함께 변합니다. */
        refreshQaAndFlow().done(function(){ if(!close) renderEdPreview(mountEditor('qa')); });
      })
      .fail(function(xhr){
        saveState('qa', 'err');
        toast(apiError(xhr, '저장하지 못했습니다'), 'err');
      });
  }

  $('#qaSaveBtn').on('click', function(){ saveQa(null, 'QA 항목을 저장했습니다', false); });
  $('#qaApproveBtn').on('click', function(){
    var $host = mountEditor('qa');
    if($host.find('.is_dup').length){ toast('중복된 변형 질문이 있습니다', 'err'); return; }
    if(!$.trim(ed($host,'answer').val())){
      /* 서버도 막지만(400) 여기서 먼저 잡아 줍니다 — 승인은 이대로 나가도 된다는 뜻입니다. */
      toast('답변이 비어 있으면 승인할 수 없습니다', 'err'); return;
    }
    saveQa('done', '검수 완료로 저장했습니다', false);
  });
  $('#qaDiscardBtn').on('click', function(){
    if(!currentQa) return;
    var id = currentQa.qa_id;
    askConfirm('이 QA 항목을 폐기할까요?', '사용자 답변에서 즉시 제외됩니다.', true, function(){
      /* 지우지 않고 미사용으로 둡니다 — 잘못 눌러도 되돌릴 수 있고, 검수 이력이 남습니다. */
      API.send('POST', '/api/admin/qa/bulk', { qa_ids:[id], action:'disable' })
        .done(function(){
          closeModal($('#qaModal'));
          toast('폐기했습니다. 목록에서 미사용 상태로 남습니다', 'ok');
          refreshQaAndFlow();
        })
        .fail(function(xhr){ toast(apiError(xhr, '폐기하지 못했습니다'), 'err'); });
    });
  });

  /* ============================================================
     검수 #panel_review — 대기(pending) 한 건씩
     QA 인덱스가 자료실이라면 이 화면은 결재함입니다. 목록이 아니라 한 건이 주입니다.
     ============================================================ */
  var REV = { list:[], idx:0, cat:'', sort:'score_asc' };

  function revRows(){
    var rows = REVIEW_QUEUE.filter(function(r){
      if(REV.cat === '__none') return !r.category_id;
      if(REV.cat) return r.category_id === REV.cat;
      return true;
    });
    var s = REV.sort;
    rows.sort(function(a, b){
      /* 채점 없음(null)은 -1 로 두어 점수 낮은순에서 먼저 보이게 합니다 —
         사람이 판단할 근거가 없는 건이라 먼저 봐야 합니다. */
      var av = a.score == null ? -1 : a.score, bv = b.score == null ? -1 : b.score;
      if(s === 'score_asc') return av - bv;
      if(s === 'score_desc') return bv - av;
      if(s === 'hit') return b.hit - a.hit;
      /* 👎 많은순 — 신고가 몰린 QA를 그날 먼저 보게 합니다. 상태는 바꾸지 않습니다. */
      if(s === 'fb_desc') return (b.report_count || 0) - (a.report_count || 0);
      return a.created < b.created ? 1 : -1;
    });
    return rows;
  }

  function renderReview(){
    REV.list = revRows();
    var n = REV.list.length;
    if(REV.idx >= n) REV.idx = Math.max(0, n - 1);

    $('#revQueueCount').text(num(n));
    renderNavBadge(REVIEW_QUEUE.length);

    var empty = n === 0;
    $('[data-empty="rev"]').toggleClass('is_shown', empty);
    $('#revForm').prop('hidden', empty);
    $('#revActions').prop('hidden', empty);
    $('#revProgress').text((empty ? 0 : REV.idx + 1) + ' / ' + n);
    $('#revBar').css('width', (empty ? 0 : (REV.idx + 1) / n * 100) + '%');
    if(empty) return;

    var item = REV.list[REV.idx];
    /* 목록에는 답변 전문이 없습니다. 그 건을 실제로 볼 때 한 건만 받아옵니다. */
    if(!item.answer_loaded){
      $('[data-loading="rev"]').addClass('is_shown');
      API.get('/api/admin/qa/' + encodeURIComponent(item.qa_id))
        .done(function(full){
          var q = QA_ITEMS.filter(function(x){ return x.qa_id === item.qa_id; })[0];
          if(q) $.extend(q, mapQa(full), { answer_loaded:true });
          $.extend(item, mapReviewItem($.extend({}, item, mapQa(full), { answer_loaded:true })));
          $('[data-loading="rev"]').removeClass('is_shown');
          fillEditor(mountEditor('rev'), item);
        })
        .fail(function(xhr){
          $('[data-loading="rev"]').removeClass('is_shown');
          toast(apiError(xhr, '항목을 불러오지 못했습니다'), 'err');
        });
    } else {
      fillEditor(mountEditor('rev'), item);
    }
    $('#revPrev').prop('disabled', REV.idx === 0);
  }

  function revGo(step){
    var n = REV.list.length;
    if(!n) return;
    REV.idx = Math.min(Math.max(0, REV.idx + step), n - 1);
    renderReview();
  }

  /* 저장에 실패하면 **그 자리에 머무릅니다.** 넘어가 버리면 처리한 줄 알고 지나갑니다. */
  function revSave(status, label){
    if($('#panel_review').hasClass('is_busy')) return;
    var item = REV.list[REV.idx];
    if(!item) return;
    var $host = mountEditor('rev');
    if(status === 'done'){
      if($host.find('.is_dup').length){ toast('중복된 변형 질문이 있습니다', 'err'); return; }
      if(!$.trim(ed($host,'answer').val())){
        toast('답변이 비어 있으면 승인할 수 없습니다', 'err'); return;
      }
    }
    $('#panel_review').addClass('is_busy');
    saveState('rev','busy');
    API.send('POST', '/api/admin/qa', collectEditor($host, item, status))
      .done(function(){
        $('#panel_review').removeClass('is_busy');
        saveState('rev','ok');
        toast(label, 'ok');
        /* 목록을 다시 받으면 이 건은 대기에서 빠집니다 — 그 자리가 곧 다음 건입니다. */
        refreshQaAndFlow();
      })
      .fail(function(xhr){
        $('#panel_review').removeClass('is_busy');
        saveState('rev','err');
        toast(apiError(xhr, '저장하지 못했습니다. 다시 시도해 주세요'), 'err');
      });
  }
  $('#revPrev').on('click', function(){ revGo(-1); });
  $('#revHold').on('click', function(){ revSave('hold', '보류로 저장했습니다'); });
  $('#revDisable').on('click', function(){ revSave('unused', '미사용으로 저장했습니다'); });
  $('#revApproveNext').on('click', function(){ revSave('done', '승인했습니다'); });
  $('#revSort').on('change', function(){ REV.sort = $(this).val(); REV.idx = 0; renderReview(); });

  /* ============================================================
     진행 현황 #panel_flow — 보여주고 보내기만 합니다
     상태(ok/warn/todo/off)와 병목은 **서버가 정합니다**. 화면이 숫자를 보고 다시
     판단하면 임계값이 화면과 서버 두 곳에 생겨 조용히 어긋납니다.
     ============================================================ */
  var FLOW_META = {
    documents:{ no:1, title:'문서',      label:'문서 관리',  tab:'docs' },
    drafts:   { no:2, title:'초안',      label:'생성 시작',  tab:'generate' },
    pending:  { no:3, title:'검수 대기', label:'검수하기',   tab:'review' },
    approved: { no:4, title:'서비스 중', label:'QA 인덱스',  tab:'qa' },
    quality:  { no:5, title:'품질',      label:'다시 측정',  tab:'eval' },
    threshold:{ no:6, title:'임계값',    label:'설정',       tab:'settings' }
  };
  var FLOW_TODO_LABEL = {
    docs:'RAG 문서', review:'검수 화면 열기', apply:'QA 생성',
    generate:'QA 생성', quality:'품질 평가'
  };

  function flowValue(step){
    if(step.key === 'quality') return Number(step.value).toFixed(1) + '%';
    if(step.key === 'threshold') return Number(step.value).toFixed(2);
    return num(step.value);
  }

  function renderFlow(){
    $('#flowAt').text(FLOW_AT);
    var $w = $('#flowSteps').empty();
    $.each(FLOW_STEPS, function(_, s){
      var meta = FLOW_META[s.key] || { no:0, title:s.key, label:'이동', tab:'' };
      var $s = tpl('tpl_flow_step').children().attr('data-step', meta.no);
      var off = s.state === 'off';
      $s.toggleClass('is_off', off)
        .toggleClass('is_todo', s.state === 'todo')
        .toggleClass('is_warn', s.state === 'warn');
      $s.find('.admin_flow_no').text(meta.no);
      $s.find('.admin_flow_title_txt').text(meta.title);
      $s.find('.admin_flow_flag').text(s.state === 'todo' ? '★' : (s.state === 'warn' ? '⚠' : ''));
      $s.find('.admin_flow_value').text(flowValue(s));
      $s.find('.admin_flow_sub').text(s.note);
      /* 버튼 문구는 **서버가 준 것이 우선**입니다. 초안이 쌓여 있으면 '생성 시작'이 아니라
         '초안 N건 보기'가 와야 무엇을 하러 가는지 맞습니다(상태·병목과 같은 원칙). */
      $s.find('.admin_flow_go').text(s.action || meta.label)
        .attr('data-goto-tab', meta.tab)
        .prop('disabled', off)
        .attr('title', off ? '작업용 PC에서 가능합니다' : '');
      $w.append($s);
    });

    var $todo = $('#flowTodo').toggleClass('is_clear', !FLOW_TODO);
    $todo.find('.admin_flow_todo_txt').text(FLOW_TODO ? FLOW_TODO.message : '막힌 곳이 없습니다.');
    $todo.find('[data-flow-go]')
      .prop('hidden', !FLOW_TODO)
      .text(FLOW_TODO ? (FLOW_TODO_LABEL[FLOW_TODO.kind] || '이동') : '')
      .attr('data-goto-tab', FLOW_TODO ? FLOW_TODO.tab : '');

    renderFlowSummary();
    renderNavBadge(REVIEW_QUEUE.length);
  }

  /* 단계 사이에서 걸러져 나간 것. 근거없음이 많다는 것은 모델이 부실한 게 아니라
     그 주제를 다룬 **문서가 없다**는 뜻입니다. */
  function renderFlowSummary(){
    var g = FLOW_SUMMARY;
    $('#flowSummaryCard').prop('hidden', !g);
    if(!g) return;
    var drops = [
      { label:'근거없음', n:g.dropped_ungrounded },
      { label:'비한국어', n:g.dropped_language },
      { label:'4점미만', n:g.low_score }
    ].filter(function(d){ return d.n > 0; });

    var html = '<span class="admin_flow_sum_node">문서 <b>' + num(g.documents) + '</b></span>' +
      '<span class="admin_flow_sum_arrow">──' + num(g.questions_made) + '건 생성──▶</span>';
    if(drops.length){
      html += '<span class="admin_flow_sum_drop">' +
        drops.map(function(d){ return '<span>' + d.label + ' ' + num(d.n) + '</span>'; }).join(' · ') +
        ' 제외</span><span class="admin_flow_sum_arrow">──▶</span>';
    }
    html += '<span class="admin_flow_sum_node">대기 <b>' + num(g.pending) + '</b></span>' +
      '<span class="admin_flow_sum_arrow">──▶</span>' +
      '<span class="admin_flow_sum_node">반영 <b>' + num(g.approved) + '</b></span>';
    $('#flowSummary').html(html);
  }

  $('#flowRefresh').on('click', function(){
    loadFlow()
      .done(function(){ renderFlow(); refreshJobs(); toast('현황을 새로 읽었습니다', 'ok'); })
      .fail(function(xhr){ toast(apiError(xhr, '현황을 읽지 못했습니다'), 'err'); });
  });

  /* ============================================================
     작업 현황판 (퍼블 요청서 06 · 5번)

     렌더는 산출물 그대로입니다. 바꾼 것은 **상태를 어디서 얻는가** 하나뿐입니다 —
     산출물의 가짜 진행(`startJob`/`finishJob`/`tick`)을 걷어내고 `GET /api/admin/jobs`
     하나를 폴링합니다. 진행 상태는 서버가 들고 있으므로 새로고침해도 이어집니다.

     한 번에 하나만 돕니다(서버가 두 번째 요청을 409로 막습니다). 그래서 화면도
     실행 중 하나만 그립니다.
     ============================================================ */
  var JOBS = { running:null, recent:[] };
  var jobTimer = null, jobOffline = false;

  function jobElapsed(startedAt){
    var t = new Date(startedAt).getTime();
    if(isNaN(t)) return '';
    var min = Math.max(0, Math.round((Date.now() - t) / 60000));
    return min < 1 ? '방금 시작' : min + '분 경과';
  }
  function jobAt(iso){
    var d = new Date(iso);
    if(isNaN(d.getTime())) return '';
    return pad(d.getMonth()+1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
  }

  /* 실행 중 작업이 있는 항목에만 도는 점을 답니다 */
  function renderNavSpin(){
    var key = JOBS.running ? JOBS.running.key : '';
    var tab = JOBS.running ? (JOBS.running.tab || '') : '';
    $('[data-nav-spin]').each(function(){
      var k = $(this).data('nav-spin');
      $(this).prop('hidden', !(key && (k === key || k === tab)));
    });
  }

  var JOB_ICO = { done:['is_done','✓'], stopped:['is_stopped','⚠'], failed:['is_failed','✕'] };

  function renderJob(){
    var r = JOBS.running;
    var $j = $('#flowJob');
    if(!r){
      $j.prop('hidden', true).removeClass('is_stopping');
      renderNavSpin();
      renderJobHistory();
      return;
    }
    $j.prop('hidden', false).toggleClass('is_stopping', !!r.stopping);
    $j.find('.admin_job_title_txt').text((r.title || '작업') + ' 중');
    $j.find('.admin_job_meta').text([r.model, jobElapsed(r.started_at)].filter(Boolean).join(' · '));
    /* 단계 문구는 서버가 준 값을 그대로 출력합니다 */
    $j.find('.admin_job_stage').text(r.stage || '');
    progress($('#flowJobProgress'), {
      pct:r.percent,
      text:(r.total ? num(r.done) + ' / ' + num(r.total) : '')
    });
    $j.find('.admin_job_offline').prop('hidden', !jobOffline);
    $j.find('.admin_job_stopping').prop('hidden', !r.stopping);
    $('#flowJobStop').prop('disabled', !!r.stopping);
    $('#flowJobGo').text('작업 화면으로').attr('data-goto-tab', r.tab || 'flow');
    renderNavSpin();
    renderJobHistory();
  }

  function renderJobHistory(){
    var rows = JOBS.recent || [];
    $('#flowJobHistoryCard').prop('hidden', !rows.length);
    var $w = $('#flowJobHistory').empty();
    /* 지금 할 일 배너와 지시가 둘이면 안 됩니다 — 겹치면 배너가 우선입니다 */
    var bannerOn = !$('#flowTodo').hasClass('is_clear');
    $.each(rows, function(i, r){
      var $r = tpl('tpl_job_row').children().attr('data-job-key', r.key);
      var ico = JOB_ICO[r.status] || JOB_ICO.done;
      $r.toggleClass('is_failed', r.status === 'failed');
      $r.find('.admin_job_ico').addClass(ico[0]).text(ico[1]);
      $r.find('.admin_job_row_title').text(r.title || '작업');
      $r.find('.admin_job_row_at').text(jobAt(r.finished_at));
      $r.find('.admin_job_row_sum').text(r.summary || '');
      $r.find('.admin_job_row_elapsed').text(r.elapsed || '—');
      /* next 는 서버가 정합니다. 맨 윗줄에만, 배너가 없을 때만 */
      var showNext = i === 0 && !!r.next && !bannerOn;
      $r.toggleClass('has_next', showNext);
      if(showNext) $r.find('.admin_job_next').text(r.next.label).attr('data-goto-tab', r.next.tab);
      $w.append($r);
    });
  }

  function applyJobs(res, wasRunning){
    JOBS = { running:res.running || null, recent:res.recent || [] };
    jobOffline = false;
    renderJob();
    /* 배치가 방금 끝났으면 숫자가 달라져 있습니다 — 현황과 목록을 다시 읽습니다. */
    if(wasRunning && !JOBS.running){
      loadFlow().done(renderFlow);
      loadQa().done(renderQa);
    }
    if(JOBS.running) startJobPolling(); else stopJobPolling();
  }

  function refreshJobs(){
    var wasRunning = !!JOBS.running;
    return API.get('/api/admin/jobs')
      .done(function(res){ applyJobs(res, wasRunning); })
      .fail(function(xhr){
        if(xhr.status === 401) return;         /* 로그인 모달이 뜹니다 */
        /* 진행바는 그대로 두고 끊겼다는 것만 덧붙입니다 — 폴링은 계속합니다. */
        jobOffline = true;
        renderJob();
      });
  }

  function startJobPolling(){
    if(jobTimer) return;
    jobTimer = setInterval(refreshJobs, 2000);
  }
  function stopJobPolling(){
    if(!jobTimer) return;
    clearInterval(jobTimer); jobTimer = null;
  }

  /* 중지는 확인 모달 없이 바로 — 지금까지 만든 것은 남습니다 */
  $('#flowJobStop').on('click', function(){
    if(!JOBS.running) return;
    var key = JOBS.running.key;
    JOBS.running.stopping = true;      /* 응답을 기다리는 동안 버튼을 먼저 잠급니다 */
    renderJob();
    API.send('POST', '/api/admin/jobs/' + encodeURIComponent(key) + '/stop')
      .done(function(res){
        applyJobs(res, true);
        toast('중지를 요청했습니다. 진행 중인 항목까지 마칩니다', 'ok');
      })
      .fail(function(xhr){ toast(apiError(xhr, '중지하지 못했습니다'), 'err'); });
  });

  /* ---------- 납품처 프로필 (설정 → 납품처) ---------- */
  $('#subpanel_profile').on('input change', '.admin_input, .admin_select', function(){
    $('#subpanel_profile .admin_card').addClass('is_dirty');
    $('#profLogoPreview').text($('#profOrg').val().slice(0, 4));
  });
  $('#profSave').on('click', function(){
    saveState('prof', 'busy');
    API.send('PUT', '/api/admin/profile', {
      organization:$.trim($('#profOrg').val()),
      service_name:$.trim($('#profName').val()),
      service_desc:$.trim($('#profDesc').val()),
      domain_intro:$.trim($('#profDomain').val()),
      language:$('#profLang').val()
    })
      .done(function(p){
        BRAND = p;
        applyBrand();
        saveState('prof', 'ok');
        $('#subpanel_profile .admin_card').removeClass('is_dirty');
        toast('납품처 정보를 저장했습니다', 'ok');
      })
      .fail(function(xhr){
        saveState('prof', 'err');
        toast(apiError(xhr, '저장하지 못했습니다'), 'err');
      });
  });

  /* ============================================================
     ⑤ RAG 문서
     ============================================================ */
  function docRows(){
    var q = FILTER.doc.q.toLowerCase();
    return DOCS.filter(function(d){
      return !q || (d.title + d.doc_id + d.category_name).toLowerCase().indexOf(q) > -1;
    });
  }
  function renderDocs(){
    var rows = docRows(), studio = MODE === 'studio';
    $('[data-search="doc"]').toggleClass('is_noresult', !!FILTER.doc.q && !rows.length);
    $('#docBody').html(paged('doc', rows).map(function(d){
      return '<tr class="is_clickable" data-doc-id="' + d.doc_id + '">' +
        '<td class="admin_td_ellip" style="font-family:D2Coding,Consolas,monospace;">' + esc(d.doc_id) + '</td>' +
        '<td class="admin_td_ellip"><span class="admin_row_title">' + esc(d.title) + '</span></td>' +
        '<td class="admin_td_ellip">' + esc(d.category_name) + '</td>' +
        '<td>' + d.updated + '</td>' +
        '<td class="qr_num">' + num(d.chunks) + '</td>' +
        '<td class="qr_num">' + num(d.qa_count) + '</td>' +
        '<td>' + (studio
          ? '<button type="button" class="qr_pill qr_pill_outline qr_pill_sm" data-doc-edit>수정</button>'
          : '<button type="button" class="qr_pill qr_pill_outline qr_pill_sm" data-doc-view>보기</button>') + '</td></tr>';
    }).join(''));
    emptyState('doc', !rows.length);
    renderPager('doc', rows.length);
  }
  $('#docSearch').on('input', function(){ FILTER.doc.q = $(this).val(); PAGE.doc = 1; renderDocs(); });
  $('#docBody').on('click', 'tr', function(){ openDocModal($(this).data('doc-id')); });
  function openDocModal(id){
    var d = DOCS.filter(function(x){ return x.doc_id === id; })[0];
    if(!d) return;

    /* 목록에는 본문이 없다. 열 때 한 건만 받아온다(문서 18건 × 본문이면 목록이 무거워진다). */
    if(d.body == null){
      API.get('/api/admin/docs/' + encodeURIComponent(id))
        .done(function(full){ d.body = full.content || ''; renderDocModal(d); })
        .fail(function(xhr){ toast(apiError(xhr, '문서를 불러오지 못했습니다'), 'err'); });
      return;
    }
    renderDocModal(d);
  }

  function renderDocModal(d){
    currentDoc = d;
    var readonly = MODE !== 'studio';
    $('#docModalTitle').text(readonly ? '문서 보기 (읽기 전용)' : '문서 편집');
    $('#docId').val(d.doc_id).prop('readonly', true);
    $('#docTitle').val(d.title).prop('readonly', readonly);
    $('#docEditor').val(d.body).prop('readonly', readonly);
    $('#docModal').removeClass('is_dirty');
    openModal('docModal');
  }
  $('#docNewBtn').on('click', function(){
    currentDoc = null;
    $('#docModalTitle').text('새 문서');
    $('#docId').val('').prop('readonly', false).attr('placeholder','doc-00-name');
    $('#docTitle').val('').prop('readonly', false);
    $('#docEditor').val('').prop('readonly', false);
    $('#docModal').removeClass('is_dirty');
    openModal('docModal');
  });
  $('#docModal').on('input', '.admin_input, .admin_textarea', function(){ $('#docModal').addClass('is_dirty'); });
  $('#docSaveBtn').on('click', function(){
    var id = $.trim($('#docId').val());
    var content = $('#docEditor').val();
    if(!id){ toast('문서 ID를 입력해 주세요', 'err'); return; }

    saveState('doc', 'busy', '저장 후 색인 중…');
    /* 저장하면 서버가 그 문서만 다시 청킹·임베딩한다. 문서가 크면 몇 초 걸린다. */
    var request = currentDoc
      ? API.send('PUT', '/api/admin/docs/' + encodeURIComponent(id), { content:content })
      : API.send('POST', '/api/admin/docs', { doc_id:id, content:content });

    request
      .done(function(res){
        saveState('doc', 'ok');
        $('#docModal').removeClass('is_dirty');
        toast('문서를 저장했습니다 (청크 ' + res.chunks_created + '개)', 'ok');
        closeModal($('#docModal'));
        loadDocs().done(renderDocs); refreshFlow();
      })
      .fail(function(xhr){
        saveState('doc', 'err');
        toast(apiError(xhr, '저장하지 못했습니다'), 'err');
      });
  });

  $('#docDeleteBtn').on('click', function(){
    if(!currentDoc) return;
    var id = currentDoc.doc_id;
    askConfirm('이 문서를 삭제할까요?', '연결된 QA의 출처 표기가 사라집니다.', true, function(){
      API.send('DELETE', '/api/admin/docs/' + encodeURIComponent(id))
        .done(function(){
          closeModal($('#docModal'));
          toast('삭제했습니다', 'ok');
          loadDocs().done(renderDocs); refreshFlow();
        })
        .fail(function(xhr){ toast(apiError(xhr, '삭제하지 못했습니다'), 'err'); });
    });
  });

  /* ---------- 폴더 업로드 ----------------------------------------------------
     퍼블 산출물에 없는 화면입니다. ⑤ 탭에 버튼과 `#docUploadModal` 을 덧붙였고, 다음
     산출물을 받을 때 이 블록과 모달을 함께 옮기면 됩니다(그 외 렌더 코드는 손대지 않았습니다).

     폴더를 **한 요청에 통째로 보내지 않습니다.** 문서 한 건마다 청킹·임베딩이 돌아 몇 초가
     걸리는데, 40건을 한 번에 보내면 (1) 진행 상황을 보여줄 수 없고 (2) 프록시 타임아웃에
     걸린 뒤 무엇이 들어갔는지 알 수 없게 됩니다. 몇 건씩 나눠 보내고 결과를 이어 붙입니다.
     --------------------------------------------------------------------------- */
  var UPLOAD_BATCH = 4;                        /* 서버 상한(20)보다 작게 — 요청이 짧아야 진행률이 촘촘합니다 */
  var UPLOAD_EXT = /\.(md|markdown|txt)$/i;
  var DOC_UP_ST = {
    created:['is_done','등록'], updated:['is_applied','갱신'],
    skipped:['is_hold','건너뜀'], failed:['is_excluded','실패']
  };
  var uploadQueue = [], uploadPreSkipped = [], uploadBusy = false;

  function uploadPath(file){ return file.webkitRelativePath || file.name; }

  function addUploadRow(it){
    var st = DOC_UP_ST[it.status] || ['is_hold', it.status];
    $('#docUploadBody').append('<tr>' +
      '<td class="admin_td_ellip" title="' + esc(it.path) + '">' + esc(it.path) + '</td>' +
      '<td class="admin_td_ellip" style="font-family:D2Coding,Consolas,monospace;">' + esc(it.doc_id || '—') + '</td>' +
      '<td><span class="admin_st ' + st[0] + '">' + st[1] + '</span></td>' +
      '<td class="qr_num">' + (it.chunks ? num(it.chunks) : '—') + '</td>' +
      '<td class="admin_td_ellip" title="' + esc(it.reason) + '">' + esc(it.reason || '') + '</td></tr>');
  }

  /* 문서 작성 형식 안내. 내용은 마크업에 있는 고정 안내라 서버를 부르지 않습니다
     (길이 상한 숫자만 loadRuntimeModels 가 채웁니다). */
  $('#docGuideBtn').on('click', function(){ openModal('docGuideModal'); });

  $('#docUploadBtn').on('click', function(){
    /* 값을 비워야 같은 폴더를 다시 골랐을 때도 change 가 뜹니다. */
    $('#docUploadInput').val('').trigger('click');
  });

  $('#docUploadInput').on('change', function(){
    var picked = Array.prototype.slice.call(this.files || []);
    if(!picked.length) return;
    /* 등록이 도는 중에 폴더를 다시 고르면 보내는 중인 목록을 갈아엎게 됩니다.
       창을 닫아도 남은 묶음은 계속 올라갑니다 — 끝날 때까지 기다렸다 다시 고르게 합니다. */
    if(uploadBusy){ toast('앞의 등록이 끝난 뒤에 다시 골라 주세요', 'err'); return; }

    var files = picked.filter(function(f){ return UPLOAD_EXT.test(f.name); });
    if(!files.length){
      toast('폴더에 문서 파일(.md · .markdown · .txt)이 없습니다', 'err');
      return;
    }

    /* 하위 폴더가 달라도 파일 이름이 같으면 문서 ID가 겹칩니다. 서버는 요청 하나 안에서만
       이것을 볼 수 있으므로(묶음이 나뉩니다) 전체 목록을 쥐고 있는 화면이 먼저 걸러냅니다. */
    var seen = Object.create(null);
    uploadPreSkipped = [];
    uploadQueue = files.filter(function(f){
      var key = (f.name.normalize ? f.name.normalize('NFC') : f.name).toLowerCase();
      if(seen[key]){
        uploadPreSkipped.push({ path:uploadPath(f), status:'skipped',
          reason:'\'' + seen[key] + '\' 와 파일 이름이 같습니다' });
        return false;
      }
      seen[key] = uploadPath(f);
      return true;
    });

    $('#docUploadBody').empty();
    $('#docUploadProgress').removeClass('is_shown is_err');
    $('#docUploadStartBtn').prop('disabled', false).text('등록 시작');
    $('#docUploadSummary').text(
      '문서 ' + num(uploadQueue.length) + '건을 등록합니다' +
      (picked.length > files.length ? ' (문서가 아닌 파일 ' + num(picked.length - files.length) + '건은 제외)' : '') +
      (uploadPreSkipped.length ? ' · 이름이 겹치는 ' + num(uploadPreSkipped.length) + '건은 건너뜁니다' : '') + '.'
    );
    openModal('docUploadModal');
  });

  $('#docUploadStartBtn').on('click', function(){
    if(uploadBusy || !uploadQueue.length) return;
    uploadBusy = true;
    $('#docUploadStartBtn').prop('disabled', true).text('등록 중…');

    var counts = { created:0, updated:0, skipped:0, failed:0 };
    var overwrite = $('#docUploadOverwrite').prop('checked');
    var total = uploadQueue.length, done = 0;

    $.each(uploadPreSkipped, function(_, it){ counts.skipped++; addUploadRow(it); });
    uploadPreSkipped = [];

    function step(){
      if(!uploadQueue.length){ finish(); return; }
      progress($('#docUploadProgress'), { pct:done / total * 100, text:num(total) + '건 중 ' + num(done) + '건' });

      var batch = uploadQueue.splice(0, UPLOAD_BATCH);
      var form = new FormData();
      $.each(batch, function(_, f){
        form.append('files', f, f.name);
        /* 브라우저는 파일 이름에 폴더 경로를 넣어주지 않습니다. 결과 표에서 사람이 자기
           폴더의 파일을 찾을 수 있도록 상대 경로를 따로 보냅니다(순서가 files 와 같습니다). */
        form.append('paths', uploadPath(f));
      });
      form.append('overwrite', overwrite ? 'true' : 'false');

      API.upload('/api/admin/docs/upload', form)
        .done(function(res){
          $.each(res.items || [], function(_, it){
            counts[it.status] = (counts[it.status] || 0) + 1;
            addUploadRow(it);
          });
        })
        .fail(function(xhr){
          /* 묶음 하나가 실패해도 멈추지 않습니다 — 남은 문서까지 못 올리면 처음부터 다시 해야 합니다. */
          $.each(batch, function(_, f){
            counts.failed++;
            addUploadRow({ path:uploadPath(f), status:'failed', reason:apiError(xhr, '서버에 보내지 못했습니다') });
          });
        })
        .always(function(){ done += batch.length; step(); });
    }

    function finish(){
      uploadBusy = false;
      progress($('#docUploadProgress'), { pct:100, text:'완료', error:counts.failed > 0 });
      $('#docUploadStartBtn').prop('disabled', true).text('완료');
      $('#docUploadSummary').text(
        '등록 ' + num(counts.created) + ' · 갱신 ' + num(counts.updated) +
        ' · 건너뜀 ' + num(counts.skipped) + ' · 실패 ' + num(counts.failed) + '건.' +
        (counts.skipped ? ' 건너뛴 파일은 비고를 확인해 주세요.' : '')
      );
      toast('문서 ' + num(counts.created + counts.updated) + '건을 등록했습니다', counts.failed ? 'err' : 'ok');
      loadDocs().done(renderDocs); refreshFlow();   /* 목록의 청크 수까지 새로 받습니다 */
    }

    step();
  });

  /* ============================================================
     ⑥ QA 생성
     ============================================================ */
  /* 생성 대상 목록은 문서·묶음을 받아온 뒤 채운다. */
  function renderGenTargets(){
    $('#genDocSel').html(DOCS.map(function(d){
      return '<option value="' + d.doc_id + '">' + esc(d.title) + '</option>';
    }).join(''));
    $('#genUncoveredCount').text(CLUSTERS.filter(function(c){ return !c.has_qa; }).length);
  }

  /* 모델 목록은 서버가 Ollama 에 물어봅니다. 하드코딩하던 때에는 이 PC에 없는 모델이
     목록에 있고(고르면 배치가 통째로 실패) 있는 모델은 없어서 고를 수가 없었습니다.

     질문·변형과 답변을 따로 고르는 이유: 같은 문서로 재본 결과 큰 모델은 답변이 정확한 대신
     변형 질문의 표현 폭이 좁았습니다. 적중률은 변형 질문의 표현 폭이 사실상 결정합니다. */
  function loadGenModels(){
    if(MODE !== 'studio') return;
    API.get('/api/studio/generate/models').done(function(res){
      var models = res.models || [];
      if(!models.length){
        toast('Ollama 에서 모델 목록을 받지 못했습니다. 서버가 떠 있는지 확인해 주세요', 'err');
      }
      fillModelSel($('#genQuestionModel'), models, res.question_default);
      fillModelSel($('#genAnswerModel'), models, res.answer_default);
      /* 채점은 기본이 '안 함'입니다. 답변 모델로 자기 채점을 하느니 점수가 없는 편이 낫습니다 —
         있으나 마나 한 숫자가 붙으면 검수자가 그것을 믿습니다. */
      fillModelSel($('#genJudgeModel'), models, res.judge_default, '채점 안 함');
      GEN_MIN_SCORE = res.apply_min_score || 0;
      syncJudgeHint();
      /* 표가 이 값보다 먼저 그려질 수 있습니다(둘 다 비동기). 기준 점수를 받은 뒤 다시
         그려야 점수 미달 행의 체크가 풀립니다 — 안 그러면 '12개 선택'으로 보입니다. */
      if(GEN_DRAFTS.length) renderGenResult();
    });
  }
  var GEN_MIN_SCORE = 0;

  /* 답변 모델과 채점 모델이 같으면 자기 채점입니다. 막지는 않되 눈에 띄게 알립니다. */
  function syncJudgeHint(){
    var judge = $('#genJudgeModel').val();
    var same = judge && judge === $('#genAnswerModel').val();
    $('#genJudgeHint').toggleClass('is_warn', !!same).html(same
      ? '⚠ 답변 모델과 같은 모델입니다. 자기 답에 후한 점수를 주므로 다른 모델을 권합니다.'
      : '채점 모델은 답변 모델과 <b>다른 것</b>으로 고르세요. 같은 모델이 자기 답을 채점하면 점수가 후해집니다.');
  }
  $('#genJudgeModel, #genAnswerModel').on('change', syncJudgeHint);
  function fillModelSel($sel, models, chosen, emptyLabel){
    /* 기본값이 설치 목록에 없을 수도 있습니다(.env 에 적어두고 아직 안 받은 경우).
       그때도 고른 값이 보여야 무엇이 쓰이는지 알 수 있으므로 목록에 함께 넣습니다. */
    var all = models.slice();
    if(chosen && all.indexOf(chosen) === -1) all.unshift(chosen);
    var html = emptyLabel ? '<option value="">' + esc(emptyLabel) + '</option>' : '';
    $sel.html(html + all.map(function(m){
      return '<option value="' + esc(m) + '"' + (m === chosen ? ' selected' : '') + '>' + esc(m) + '</option>';
    }).join(''));
  }

  var GEN_DRAFTS = [];
  var genPollTimer = null;

  function genTarget(){
    var value = $('#genTargetRadio input[name=genTarget]:checked').val() || 'docs';
    if(value === 'category'){
      /* 팝오버는 고른 값을 트리거 버튼의 data-category-id 에 남긴다. */
      var picked = $('[data-cat-picker="gen"] [data-cat-trigger]').attr('data-category-id');
      if(!picked){ toast('카테고리를 선택해 주세요', 'err'); return null; }
      return { source:'category', category_id:picked };
    }
    if(value === 'uncovered'){
      /* 답이 없었던 묶음의 대표 질문을 그대로 문항으로 넘긴다 — 실제로 물어본 표현이다. */
      var questions = CLUSTERS.filter(function(c){ return !c.has_qa; }).map(function(c){ return c.question; });
      if(!questions.length){ toast('QA가 없는 묶음이 없습니다. 먼저 질문 분석을 실행하세요', 'err'); return null; }
      return { source:'questions', questions:questions };
    }
    return { source:'docs', doc_ids:$('#genDocSel').val() || [] };
  }

  function genBusy(running){
    $('#genRunBtn').prop('disabled', running);
    $('#genStopBtn').prop('disabled', !running);
  }

  function pollGeneration(){
    clearTimeout(genPollTimer);
    API.get('/api/studio/generate/progress').done(function(p){
      if(p.status === 'running'){
        progress($('#genProgress'), p.percent ? { pct:p.percent, text:p.stage } : { indeterminate:true, text:p.stage });
        genPollTimer = setTimeout(pollGeneration, 1500);
        return;
      }
      genBusy(false);
      if(p.status === 'failed'){
        progress($('#genProgress'), { pct:p.percent, text:'실패: ' + p.error, error:true });
        toast(p.error || '생성에 실패했습니다', 'err');
        return;
      }
      progress($('#genProgress'), {
        pct:100, text:p.status === 'stopped' ? '중지됨' : '완료', error:p.status === 'stopped'
      });
      loadGenResult(p.status === 'stopped');
    });
  }

  /* `silent` 는 화면을 열 때 씁니다. 초안은 파일에 남아 있어서 **이전에 만들어 둔 것도
     불러와야** 합니다 — 그러지 않으면 진행 현황에는 "초안 12건"이 뜨는데 이 표는 비어 있어
     "어디서 보나"를 한참 찾게 됩니다(실제로 겪음). 다만 그때 토스트까지 띄우면 페이지를
     열 때마다 "N건을 생성했습니다"가 떠서 방금 만든 것처럼 보입니다. */
  function loadGenResult(stopped, silent){
    return API.get('/api/studio/generate/result').done(function(drafts){
      GEN_DRAFTS = drafts || [];
      renderGenResult();
      if(silent) return;
      toast(stopped
        ? '중지했습니다. 그때까지 만든 ' + GEN_DRAFTS.length + '건은 남아 있습니다'
        : 'QA 후보 ' + GEN_DRAFTS.length + '건을 생성했습니다', stopped ? 'err' : 'ok');
    });
  }

  $('#genRunBtn').on('click', function(){
    var target = genTarget();
    if(!target) return;

    genBusy(true);
    progress($('#genProgress'), { indeterminate:true, text:'모델을 불러오는 중…' });
    API.send('POST', '/api/studio/generate', $.extend({
      question_model:$.trim($('#genQuestionModel').val()) || null,
      answer_model:$.trim($('#genAnswerModel').val()) || null,
      judge_model:$.trim($('#genJudgeModel').val()) || null,
      variant_count:Number($('#genVariants').val()) || 10
    }, target))
      .done(function(){ pollGeneration(); refreshJobs(); })
      .fail(function(xhr){
        genBusy(false);
        progress($('#genProgress'), { pct:0, text:'실패', error:true });
        toast(apiError(xhr, '생성을 시작하지 못했습니다'), 'err');
      });
  });

  $('#genStopBtn').on('click', function(){
    API.send('POST', '/api/studio/generate/stop')
      .done(function(){ toast('중지를 요청했습니다. 진행 중인 항목까지 마칩니다', 'ok'); });
  });

  function renderGenResult(){
    $('#genResultBody').html(GEN_DRAFTS.map(function(d){
      var applied = !!d.applied_qa_id;
      /* 점수 미달은 미리 체크를 풀어 둡니다. 서버도 반영에서 빼지만, 화면에서 먼저 보여야
         검수자가 '왜 안 들어갔지'를 결과 표에서 바로 확인합니다. */
      var low = GEN_MIN_SCORE && d.score && d.score < GEN_MIN_SCORE;
      return '<tr class="is_clickable' + (low ? ' is_muted' : '') + '" data-draft-id="' + d.draft_id + '">' +
        '<td class="admin_col_check"><input type="checkbox" data-check="gen"' +
          (applied ? ' disabled' : (low ? '' : ' checked')) + ' aria-label="선택"></td>' +
        '<td class="admin_td_ellip"><span class="admin_row_title">' + esc(d.question) + '</span>' +
          (applied ? ' <span class="admin_st is_done">반영됨</span>' : '') + '</td>' +
        '<td class="admin_td_ellip">' + esc(plain(d.answer).slice(0, 80)) + '</td>' +
        '<td class="admin_td_ellip">' + esc(catName(d.category_id) || '미분류') + '</td>' +
        '<td class="qr_num">' + (d.variants || []).length + '</td>' +
        '<td title="' + esc(d.judge_reason || '') + '">' + scoreBadge(d) + '</td></tr>';
    }).join(''));
    emptyState('gen', !GEN_DRAFTS.length);
    updateGenSel();
  }
  /* 0점은 '나쁨'이 아니라 '채점하지 않음'입니다. 숫자로 그리면 최하점으로 읽힙니다. */
  function scoreBadge(d){
    if(!d.score) return '<span class="admin_st is_unused">' + (d.judge_model ? '판정 실패' : '—') + '</span>';
    var cls = d.score >= 4 ? 'is_done' : (d.score === 3 ? 'is_wait' : 'is_excluded');
    return '<span class="admin_st ' + cls + '">' + d.score + '점</span>';
  }

  function updateGenSel(){
    var n = $('#genResultBody input:checked').length;
    $('#genSelCount').text(n + '개 선택');
    $('#genApplyBtn').prop('disabled', !n);
  }
  $('#genResultBody').on('change', 'input[type=checkbox]', updateGenSel);
  $('#genResultBody').on('click', 'tr', function(e){
    if($(e.target).is('input[type=checkbox]')) return;
    /* 초안은 아직 QA 인덱스에 없다. 검수 모달을 '읽기 전용'으로 열어 내용만 확인한다. */
    var draft = GEN_DRAFTS.filter(function(d){ return d.draft_id === $(this).data('draft-id'); }.bind(this))[0];
    if(!draft) return;
    currentQa = null;
    var $host = mountEditor('qa');
    $('#qaStatus').val('wait');
    fillEditor($host, {
      question:draft.question, answer:draft.answer, note:'',
      category_id:draft.category_id, category_name:catName(draft.category_id) || '미분류',
      variants:draft.variants || [],
      sources:(draft.source_doc_ids || []).map(function(id){
        var d = DOCS.filter(function(x){ return x.doc_id === id; })[0];
        return { doc_id:id, title:(d && d.title) || id };
      }),
      /* 초안의 채점을 여기서 보여줘야 반영할지 말지 판단할 수 있습니다. 0 은 '채점 없음'입니다. */
      score:draft.score ? draft.score : null,
      score_model:draft.judge_model || '', score_why:draft.judge_reason || ''
    });
    $('#qaModal').find('input, textarea, select').prop('disabled', true);
    $('#qaModal').find('#qaSaveBtn, #qaApproveBtn, #qaDiscardBtn').prop('hidden', true);
    $host.find('[data-ed="variantAdd"], [data-ed="variantGen"], [data-ed="sourceAdd"]').prop('hidden', true);
    $host.find('[data-row-remove], [data-tag-remove]').prop('hidden', true);
    $('#qaModalTitle').text('생성 결과 미리보기 (반영 전)');
    openModal('qaModal');
  });
  $('[data-check-all="gen"]').on('change', function(){
    $('#genResultBody input[type=checkbox]').prop('checked', $(this).is(':checked'));
    updateGenSel();
  });
  $('#genApplyBtn').on('click', function(){
    var ids = $('#genResultBody input:checked').map(function(){
      return $(this).closest('tr').data('draft-id');
    }).get();
    if(!ids.length){ toast('선택한 항목이 없습니다', 'err'); return; }

    askConfirm(ids.length + '건을 QA 인덱스에 추가할까요?',
      '추가된 항목은 검수대기 상태가 됩니다. 승인 전에는 사용자에게 나가지 않습니다.', false, function(){
      API.send('POST', '/api/studio/generate/apply', { draft_ids:ids })
        .done(function(res){
          /* 중복과 점수 미달을 나눠서 알립니다 — 중복은 정상이고, 점수 미달은 프롬프트나
             문서를 손봐야 한다는 신호라 검수자가 할 일이 다릅니다. */
          var except = [];
          if(res.skipped) except.push('중복 ' + res.skipped + '건');
          if(res.low_score) except.push(res.min_score + '점 미만 ' + res.low_score + '건');
          toast(res.saved + '건을 추가했습니다' + (except.length ? ' (' + except.join(' · ') + ' 제외)' : ''), 'ok');
          loadGenResult(false, true);
          /* 초안·검수 대기 숫자가 함께 움직입니다. 진행 현황까지 다시 읽지 않으면 그 화면으로
             넘어갔을 때 옛 숫자가 남아 있습니다(새로고침해야 바뀜). */
          refreshQaAndFlow();
        })
        .fail(function(xhr){ toast(apiError(xhr, '추가하지 못했습니다'), 'err'); });
    });
  });
  $('#genTargetRadio').on('change', 'input[type=radio]', function(){
    $('#genTargetRadio .admin_radio_row').removeClass('is_disabled');
  });

  /* ============================================================
     ⑦ 품질 평가
     ============================================================ */
  var evalPollTimer = null;

  $('#evalRunBtn').on('click', function(){
    $('#evalRunBtn').prop('disabled', true);
    progress($('#evalProgress'), { indeterminate:true, text:'평가 문항 준비 중…' });
    API.send('POST', '/api/studio/eval?limit=' + (Number($('#evalCount').val()) || 100))
      .done(function(){ pollEval(); refreshJobs(); })
      .fail(function(xhr){
        $('#evalRunBtn').prop('disabled', false);
        progress($('#evalProgress'), { pct:0, text:'실패', error:true });
        toast(apiError(xhr, '평가를 시작하지 못했습니다'), 'err');
      });
  });

  function pollEval(){
    clearTimeout(evalPollTimer);
    API.get('/api/studio/eval/progress').done(function(p){
      if(p.status === 'running'){
        progress($('#evalProgress'), { pct:p.percent, text:p.stage });
        evalPollTimer = setTimeout(pollEval, 1000);
        return;
      }
      $('#evalRunBtn').prop('disabled', false);
      if(p.status === 'failed'){
        progress($('#evalProgress'), { pct:0, text:'실패: ' + p.error, error:true });
        toast(p.error || '평가에 실패했습니다', 'err');
        return;
      }
      progress($('#evalProgress'), { pct:100, text:'완료' });
      API.get('/api/studio/eval/result').done(function(report){
        renderEval(report);
        toast('평가를 완료했습니다 (' + report.total + '문항)', 'ok');
        setTimeout(function(){ $('#evalProgress').removeClass('is_shown'); }, 900);
      });
    });
  }

  function renderEval(report){
    var tiles = [
      { label:'적중률 (Top-1)', value:report.top1.toFixed(1) + '%' },
      { label:'적중률 (Top-3)', value:report.top3.toFixed(1) + '%' },
      { label:'오매칭률', value:report.mismatch_rate.toFixed(1) + '%' },
      { label:'평가 문항 수', value:num(report.total) }
    ];
    $('#evalSummary').prop('hidden', false).html(tiles.map(function(t){
      return '<div class="admin_sum" style="cursor:default;"><p class="admin_sum_label">' + t.label + '</p>' +
        '<p class="admin_sum_value">' + t.value + '</p></div>';
    }).join(''));

    var VD = { hit:['is_done','적중'], mismatch:['is_wait','오매칭'], miss:['is_hold','미검색'] };
    $('#evalBody').html((report.items || []).map(function(r){
      var vd = VD[r.verdict] || VD.miss;
      return '<tr><td class="admin_td_ellip">' + esc(r.question) + '</td>' +
        '<td class="admin_td_ellip">' + esc(r.expected_question) + '</td>' +
        '<td class="admin_td_ellip">' + esc(r.matched_question || '—') + '</td>' +
        '<td class="qr_num">' + (r.similarity ? r.similarity.toFixed(2) : '—') + '</td>' +
        '<td><span class="admin_st ' + vd[0] + '">' + vd[1] + '</span></td></tr>';
    }).join(''));
    emptyState('eval', !(report.items || []).length);

    /* 임계값을 바꾸면 어떻게 달라지는지 — 탭 ⑧에서 값을 정할 때 쓰는 근거다. */
    if(report.threshold_sweep && report.threshold_sweep.length){
      var rows = report.threshold_sweep.map(function(s){
        return '<tr' + (Math.abs(s.threshold - report.threshold) < 0.001 ? ' style="font-weight:600;"' : '') + '>' +
          '<td class="qr_num">' + s.threshold.toFixed(2) + '</td>' +
          '<td class="qr_num">' + s.answer_rate.toFixed(1) + '%</td>' +
          '<td class="qr_num">' + s.hit_rate.toFixed(1) + '%</td>' +
          '<td class="qr_num">' + s.mismatch_rate.toFixed(1) + '%</td></tr>';
      }).join('');
      $('#evalSweep').remove();
      $('#evalTable').closest('.admin_card').append(
        '<div id="evalSweep" class="admin_card_body">' +
        '<p class="admin_card_desc">임계값별 예상 — 굵은 줄이 현재 설정(' + report.threshold.toFixed(2) + ')입니다. ' +
        '오매칭은 사용자가 틀린 답을 맞는 줄 아는 경우라 미검색보다 나쁩니다.</p>' +
        '<table class="admin_table"><thead><tr><th>임계값</th><th>답변 비율</th><th>적중</th><th>오매칭</th></tr></thead>' +
        '<tbody>' + rows + '</tbody></table></div>');
    }
  }

  /* ============================================================
     ⑧ 설정
     ============================================================ */
  function renderZone(){
    var m = Number($('#thMatch').val()), r = Number($('#thRelated').val());
    var invalid = r >= m;
    $('#thCard').toggleClass('is_zone_invalid', invalid);
    $('#thSave').prop('disabled', invalid);
    $('#thMatchVal').val(m.toFixed(2));
    $('#thRelatedVal').val(r.toFixed(2));
    $('#thZoneA').text(r.toFixed(2));
    $('#thZoneB').text(m.toFixed(2));
    var a = Math.max(0, r) * 100, b = Math.max(a, m * 100);
    $('#thZoneBar .admin_zone_seg[data-zone=unresolved]').css('flex', '0 0 ' + a + '%');
    $('#thZoneBar .admin_zone_seg[data-zone=related]').css('flex', '0 0 ' + (b - a) + '%');
    $('#thZoneBar .admin_zone_seg[data-zone=answer]').css('flex', '0 0 ' + (100 - b) + '%');
  }
  $('#thMatch, #thRelated').on('input', function(){ renderZone(); $('#thCard').addClass('is_dirty'); });
  $('#thMatchVal').on('change', function(){ $('#thMatch').val($(this).val()); renderZone(); $('#thCard').addClass('is_dirty'); });
  $('#thRelatedVal').on('change', function(){ $('#thRelated').val($(this).val()); renderZone(); $('#thCard').addClass('is_dirty'); });
  $('#thRelatedCount').on('input', function(){ $('#thCard').addClass('is_dirty'); });
  $('#thSave').on('click', function(){
    saveState('th', 'busy');
    /* 서버도 '관련 문서 하한 < 답변 임계값'을 강제한다(400). 화면 잠금과 이중으로 막는 이유는
       API를 직접 부르는 경로가 있기 때문이다. */
    API.send('PUT', '/api/admin/settings', {
      qa_match_threshold:Number($('#thMatch').val()),
      related_docs_floor:Number($('#thRelated').val()),
      related_docs_count:Number($('#thRelatedCount').val()) || 3,
      qa_top_k:10, doc_top_k:10
    })
      .done(function(){
        saveState('th', 'ok');
        $('#thCard').removeClass('is_dirty');
        toast('매칭 설정을 저장했습니다. 다음 질문부터 바로 반영됩니다', 'ok');
      })
      .fail(function(xhr){
        saveState('th', 'err');
        toast(apiError(xhr, '저장하지 못했습니다'), 'err');
      });
  });

  $('#thResetBtn').on('click', function(){
    API.send('POST', '/api/admin/settings/reset')
      .done(function(s){
        $('#thMatch').val(s.qa_match_threshold);
        $('#thRelated').val(s.related_docs_floor);
        $('#thRelatedCount').val(s.related_docs_count);
        renderZone();
        $('#thCard').removeClass('is_dirty');
        toast('기본값으로 되돌렸습니다', 'ok');
      })
      .fail(function(xhr){ toast(apiError(xhr, '되돌리지 못했습니다'), 'err'); });
  });

  /* ---------- 전체 선택 ---------- */
  $(document).on('change', '[data-check-all]', function(){
    var key = $(this).data('check-all');
    $(this).closest('table').find('[data-check="' + key + '"]').prop('checked', $(this).is(':checked'));
  });

  /* ============================================================
     드래그 정렬 — DOM 이동 없이 이벤트만 발생
     ============================================================ */
  var dragSrc = null;
  $(document).on('dragstart', '[draggable="true"]', function(e){
    dragSrc = this;
    $(this).addClass('is_dragging');
    if(e.originalEvent.dataTransfer) e.originalEvent.dataTransfer.effectAllowed = 'move';
  });
  $(document).on('dragend', '[draggable="true"]', function(){
    $(this).removeClass('is_dragging');
    $('[data-drop-position]').removeAttr('data-drop-position');
    dragSrc = null;
  });
  $(document).on('dragover', '[draggable="true"]', function(e){
    if(!dragSrc || dragSrc === this) return;
    e.preventDefault();
    var r = this.getBoundingClientRect();
    var horizontal = $(this).hasClass('admin_tag');
    var before = horizontal
      ? (e.originalEvent.clientX - r.left) < r.width / 2
      : (e.originalEvent.clientY - r.top) < r.height / 2;
    $('[data-drop-position]').not(this).removeAttr('data-drop-position');
    $(this).attr('data-drop-position', before ? 'before' : 'after');
  });
  $(document).on('drop', '[draggable="true"]', function(e){
    if(!dragSrc || dragSrc === this) return;
    e.preventDefault();
    var $t = $(this), position = $t.attr('data-drop-position') || 'after';
    var $s = $(dragSrc);
    var kind = $t.closest('[data-reorder-kind]').data('reorder-kind')
      || ($t.hasClass('admin_tag') ? 'quick' : ($t.hasClass('admin_tree_item') ? 'category' : 'group'));
    var fromId = $s.attr('data-category-id') || $s.attr('data-group-id') || $s.index();
    var toId   = $t.attr('data-category-id') || $t.attr('data-group-id') || $t.index();
    $('[data-drop-position]').removeAttr('data-drop-position');
    /* 화면 DOM은 이동하지 않습니다 (저장 실패 시 되돌리기 쉽도록) */
    $(document).trigger('admin:reorder', [{ kind:kind, fromId:fromId, toId:toId, position:position }]);
  });
  /* 순서 변경 — 화면은 DOM을 옮기지 않고 이벤트만 준다. 배열을 고쳐 저장한 뒤 다시 그린다.
     저장이 실패하면 서버 값 그대로 다시 그려지므로 되돌릴 필요가 없다. */
  $(document).on('admin:reorder', function(e, d){
    function move(list, fromId, toId, key){
      var from = -1, to = -1;
      $.each(list, function(i, x){
        if((key ? x[key] : x) === fromId) from = i;
        if((key ? x[key] : x) === toId) to = i;
      });
      if(from < 0 || to < 0 || from === to) return false;
      var moved = list.splice(from, 1)[0];
      var at = list.indexOf(list[to]) ;
      at = to > from ? (d.position === 'before' ? to - 1 : to) : (d.position === 'before' ? to : to + 1);
      list.splice(at, 0, moved);
      return true;
    }

    if(d.kind === 'quick'){
      if(!move(QUICK, d.fromId, d.toId)) return;
      QUICK_CATEGORY_IDS = QUICK.slice();
      renderQuick();
      $('#quickCard').addClass('is_dirty');   /* 저장 버튼을 눌러야 반영된다 */
      return;
    }

    if(d.kind === 'group'){
      if(!move(CATEGORY_GROUPS, d.fromId, d.toId, 'group_id')) return;
      rebuildCats();
      saveCategories('cat', null, '대분류 순서를 저장했습니다');
      return;
    }

    if(d.kind === 'category'){
      var changed = false;
      $.each(CATEGORY_GROUPS, function(_, g){
        if(move(g.categories, d.fromId, d.toId, 'category_id')) changed = true;
      });
      if(!changed) return;
      rebuildCats();
      saveCategories('cat', null, '카테고리 순서를 저장했습니다');
    }
  });

  /* ============================================================
     로그인 모달 (요청서 03) — login.html 대체
     아이디·비밀번호는 화면 어디에도 저장하지 않습니다(localStorage 포함).
     인증 판단은 서버가 합니다. 아래 submit 핸들러의 setTimeout 이 교체 지점입니다.
     ============================================================ */
  var AUTH_MAX_TRY = 5, AUTH_LOCK_SEC = 30;
  var authFail = 0, authLockTimer = null, authLastFocus = null;
  var $authModal = $('#authModal'), $authForm = $('#authForm');
  var $authId = $('#authId'), $authPw = $('#authPw');

  function authMsg(txt){ $('#authMsg').find('.admin_auth_msg_txt').text(txt || ''); }
  function authState(state){
    $authForm.removeClass('is_busy is_error is_locked');
    if(state) $authForm.addClass('is_' + state);
    var busy = state === 'busy', locked = state === 'locked';
    $authId.add($authPw).prop('disabled', busy || locked);
    $('#authSubmit').prop('disabled', busy || locked);
    $('#authPwToggle').prop('disabled', busy || locked);
    $('#authSubmit').find('.admin_auth_submit_txt').text(busy ? '확인 중…' : '로그인');
  }
  /* 입력 중: 두 칸이 모두 채워졌을 때만 제출 버튼이 살아납니다 */
  function authTyping(){
    $authForm.toggleClass('is_typing', !!$.trim($authId.val()) && !!$authPw.val());
  }

  function openAuth(reason){
    /* reason: 'initial' | 'expired' — 만료 시 배경 내용은 지우지 않습니다 */
    authLastFocus = document.activeElement;
    $authModal.attr('data-auth-reason', reason || 'initial').addClass('is_open');
    authState(null); authMsg(''); $authForm.removeClass('is_caps is_typing');
    $authPw.val('');
    setTimeout(function(){ ($.trim($authId.val()) ? $authPw : $authId).trigger('focus'); }, 0);
  }
  function closeAuth(){
    $authModal.removeClass('is_open');
    /* 입력값은 남기지 않습니다 */
    $authId.val(''); $authPw.val('');
    authFail = 0; clearInterval(authLockTimer);
    authState(null); authMsg(''); $authForm.removeClass('is_caps is_typing');
    if(authLastFocus && authLastFocus.focus) authLastFocus.focus();
  }

  function authLock(){
    var left = AUTH_LOCK_SEC;
    authState('locked');
    authMsg('비밀번호를 ' + AUTH_MAX_TRY + '회 잘못 입력했습니다. ' + left + '초 후 다시 시도해 주세요.');
    clearInterval(authLockTimer);
    authLockTimer = setInterval(function(){
      left--;
      if(left <= 0){
        clearInterval(authLockTimer);
        authFail = 0;
        authState(null); authMsg(''); authTyping();
        $authPw.trigger('focus');
        return;
      }
      authMsg('비밀번호를 ' + AUTH_MAX_TRY + '회 잘못 입력했습니다. ' + left + '초 후 다시 시도해 주세요.');
    }, 1000);
  }

  $authId.add($authPw).on('input', function(){
    if($authForm.hasClass('is_locked')) return;
    $authForm.removeClass('is_error'); authMsg('');
    authTyping();
  });

  /* Caps Lock 안내 */
  $authId.add($authPw).on('keydown keyup', function(e){
    if(!e.originalEvent || !e.originalEvent.getModifierState) return;
    $authForm.toggleClass('is_caps', e.originalEvent.getModifierState('CapsLock'));
  });
  $authPw.on('blur', function(){ $authForm.removeClass('is_caps'); });

  /* 비밀번호 표시 토글 */
  $('#authPwToggle').on('click', function(){
    var show = $authPw.attr('type') === 'password';
    $authPw.attr('type', show ? 'text' : 'password');
    $(this).attr('aria-pressed', show ? 'true' : 'false').text(show ? '숨기기' : '보기');
    $authPw.trigger('focus');
  });

  /* 포커스 순환 — 모달 밖으로 나가지 않습니다 */
  $authModal.on('keydown', function(e){
    if(e.key !== 'Tab') return;
    var $f = $authModal.find('input, button').filter(':visible:not(:disabled)');
    if(!$f.length) return;
    var first = $f[0], last = $f[$f.length - 1];
    if(e.shiftKey && document.activeElement === first){ e.preventDefault(); last.focus(); }
    else if(!e.shiftKey && document.activeElement === last){ e.preventDefault(); first.focus(); }
  });

  $authForm.on('submit', function(e){
    e.preventDefault();
    if($authForm.hasClass('is_locked') || $authForm.hasClass('is_busy')) return;
    if(!$authForm.hasClass('is_typing')) return;
    authState('busy'); authMsg('');

    /* 인증 판단은 서버가 한다. 아이디·비밀번호는 여기서만 읽고 어디에도 저장하지 않는다. */
    API.send('POST', '/api/admin/login', { username:$.trim($authId.val()), password:$authPw.val() })
      .done(function(){
        var expired = $authModal.attr('data-auth-reason') === 'expired';
        authFail = 0;
        closeAuth();
        toast(expired ? '다시 로그인했습니다. 이어서 작업하세요' : '로그인했습니다', 'ok');
        /* 만료로 다시 로그인한 경우에도 최신 데이터로 맞춘다 — 그 사이 다른 사람이 고쳤을 수 있다. */
        reloadAll();
      })
      .fail(function(xhr){
        authFail++;
        /* 아이디는 남기고 비밀번호만 지웁니다 */
        $authPw.val('').attr('type','password');
        $('#authPwToggle').attr('aria-pressed','false').text('보기');
        $authForm.removeClass('is_typing');

        /* 서버도 5회에서 잠근다(429). 화면 잠금과 값을 맞춰 두었다. */
        if(xhr.status === 429 || authFail >= AUTH_MAX_TRY){ authLock(); return; }
        /* 어떤 아이디가 존재하는지 알려주지 않도록 문구는 항상 하나입니다 */
        authState('error');
        authMsg(apiError(xhr, '아이디 또는 비밀번호가 올바르지 않습니다.'));
        $authPw.trigger('focus');
      });
  });

  /* ---------- 로그아웃 ---------- */
  $('#adminLogout').on('click', function(){
    var dirty = $('.is_dirty').length > 0;
    askConfirm(
      '로그아웃할까요?',
      dirty ? '저장하지 않은 변경이 있습니다. 저장하지 않고 나가면 사라집니다.' : '',
      dirty,
      function(){
        API.send('POST', '/api/admin/logout').always(function(){
          /* 화면에 남은 데이터를 지운다 — 로그아웃했는데 목록이 그대로 보이면 안 된다. */
          QA_ITEMS = []; HISTORY = []; CLUSTERS = []; DOCS = [];
          renderAll();
          openAuth('initial');
        });
      }
    );
  });

  /* ============================================================
     초기 렌더
     ============================================================ */
  var RENDER = { hist:renderHist, an:renderAn, qa:renderQa, doc:renderDocs };

  function renderAll(){
    QUICK = QUICK_CATEGORY_IDS.slice();
    applyBrand();
    renderHist(); renderKpis(); renderCharts(); renderAn();
    renderQuick(); renderTree($('#catSearch').val() || ''); renderQa(); renderDocs(); renderZone();
    renderGenTargets();
    renderReview(); renderFlow();
    /* 모델 목록은 Ollama 에 물어보는 별도 호출이라 loadAll() 에 넣지 않습니다 —
       Ollama 가 꺼져 있어도 나머지 탭은 그대로 떠야 합니다. */
    loadGenModels();
    /* 초안도 서버(파일)에 남아 있습니다. 지난번에 만들어 둔 것을 화면이 다시 읽어야
       "진행 현황엔 12건인데 표는 비어 있는" 상태가 안 생깁니다. */
    if(MODE === 'studio') loadGenResult(false, true);
    /* 진행 상태는 서버가 들고 있습니다. 새로고침하거나 다른 사람이 켠 배치도 여기서 보입니다. */
    refreshJobs();
  }

  /* 로그인 상태를 먼저 확인한다.
     로그인 전에 데이터를 부르면 401이 여섯 번 나면서 로그인 모달이 여러 번 떠 보인다. */
  function boot(){
    /* 편집기는 두 화면이 같은 템플릿을 심어 씁니다. 먼저 심어 두어야 렌더가 붙습니다. */
    mountEditor('qa'); mountEditor('rev');
    selectSubtab('matching');
    applyMode(MODE);
    applyBrand();
    selectTab('flow');
    API.get('/api/admin/session').done(function(s){
      if(!s.authenticated){ openAuth('initial'); return; }
      reloadAll();
    }).fail(function(){ openAuth('initial'); });

    if(location.hash){
      var k = location.hash.slice(1);
      if($('.admin_nav_item[data-tab="' + k + '"]').length) selectTab(k);
    }
  }

  function reloadAll(){
    return loadAll()
      .done(renderAll)
      .fail(function(xhr){
        if(xhr.status === 401) return;   /* 로그인 모달이 뜬다 */
        toast(apiError(xhr, '데이터를 불러오지 못했습니다'), 'err');
      });
  }

  /* 세션이 끊겼을 때 — 하던 화면은 그대로 두고 모달만 덮는다. */
  $(document).on('admin:unauthorized', function(){
    if($('#authModal').is(':visible')) return;
    openAuth('expired');
  });

  boot();

});