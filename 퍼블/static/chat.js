window.__chatLoaded = true;
/* ============================================================
   API Manager 도우미 — 사용자 챗봇 화면 (jQuery)
   개발 이식 시: CATEGORY_GROUPS / QUICK_CATEGORY_IDS 는 서버 응답으로 교체
   ============================================================ */

/* ---------- 카테고리 더미 데이터 (대분류 5 / 카테고리 48) ---------- */
var CATEGORY_GROUPS = [
  { group_id:'g_reg', group_name:'API 등록', categories:[
    { category_id:'c_reg_flow',   name:'API 등록 절차', questions:[
      'API를 처음 등록하려면 무엇부터 해야 하나요?',
      'API 등록 후 바로 호출할 수 있나요?',
      'API 등록에 승인 절차가 있나요?' ] },
    { category_id:'c_reg_fields', name:'API 등록 항목 설명', questions:[
      '권한그룹은 무엇을 뜻하나요?',
      '서비스 URI와 운영 URI의 차이가 무엇인가요?',
      'API 등록 화면의 필수 입력 항목만 알려주세요.' ] },
    { category_id:'c_reg_error',  name:'API 등록 오류', questions:[
      'API 등록 시 중복 오류가 뜹니다.',
      '저장 버튼을 눌러도 반응이 없습니다.' ] },
    { category_id:'c_reg_quick',  name:'퀵 API 등록' },
    { category_id:'c_reg_bulk',   name:'API 일괄 등록(엑셀)' },
    { category_id:'c_reg_modify', name:'등록한 API 수정' },
    { category_id:'c_reg_delete', name:'API 삭제 · 비활성화' },
    { category_id:'c_reg_version',name:'API 버전 관리' },
    { category_id:'c_reg_copy',   name:'API 복제 등록' },
    { category_id:'c_reg_swagger',name:'Swagger 파일로 등록' },
    { category_id:'c_reg_test',   name:'등록 API 테스트 호출' },
    { category_id:'c_reg_publish',name:'API 공개 범위 설정' }
  ]},
  { group_id:'g_spc', group_name:'API 그룹(스펙)', categories:[
    { category_id:'c_spc_create', name:'API 그룹(SPC) 등록', questions:[
      'API 그룹은 어떻게 만드나요?',
      'SPC 코드 규칙이 있나요?' ] },
    { category_id:'c_spc_fields', name:'API 그룹 항목 설명' },
    { category_id:'c_spc_modify', name:'API 그룹 수정' },
    { category_id:'c_spc_delete', name:'API 그룹 삭제' },
    { category_id:'c_spc_mapping',name:'API ↔ 그룹 매핑' },
    { category_id:'c_spc_owner',  name:'그룹 담당자 지정' },
    { category_id:'c_spc_search', name:'그룹 검색 · 필터' },
    { category_id:'c_spc_export', name:'그룹 목록 내려받기' },
    { category_id:'c_spc_error',  name:'그룹 등록 오류' }
  ]},
  { group_id:'g_tpl', group_name:'템플릿 관리', categories:[
    { category_id:'c_tpl_create', name:'템플릿 등록' },
    { category_id:'c_tpl_modify', name:'템플릿 수정', questions:[
      '템플릿을 수정하면 기존 API에도 반영되나요?',
      '템플릿 수정 권한은 누가 갖나요?' ] },
    { category_id:'c_tpl_delete', name:'템플릿 삭제' },
    { category_id:'c_tpl_var',    name:'템플릿 변수 사용법' },
    { category_id:'c_tpl_header', name:'요청 헤더 템플릿' },
    { category_id:'c_tpl_body',   name:'요청 본문 템플릿' },
    { category_id:'c_tpl_resp',   name:'응답 템플릿' },
    { category_id:'c_tpl_err',    name:'오류 응답 템플릿' },
    { category_id:'c_tpl_apply',  name:'템플릿 API 적용' },
    { category_id:'c_tpl_copy',   name:'템플릿 복제' },
    { category_id:'c_tpl_history',name:'템플릿 변경 이력' }
  ]},
  { group_id:'g_auth', group_name:'인증 · 권한', categories:[
    { category_id:'c_auth_key',   name:'API Key 발급', questions:[
      'API Key는 어디서 발급받나요?',
      'API Key를 재발급하면 기존 키는 어떻게 되나요?' ] },
    { category_id:'c_auth_token', name:'액세스 토큰 발급' },
    { category_id:'c_auth_group', name:'권한그룹 관리' },
    { category_id:'c_auth_role',  name:'사용자 역할(Role)' },
    { category_id:'c_auth_ip',    name:'IP 허용 목록' },
    { category_id:'c_auth_scope', name:'스코프(Scope) 설정' },
    { category_id:'c_auth_expire',name:'인증 정보 만료 · 갱신' },
    { category_id:'c_auth_error', name:'401 · 403 오류 대응' }
  ]},
  { group_id:'g_ops', group_name:'운영 · 모니터링', categories:[
    { category_id:'c_ops_stat',   name:'호출 통계 조회' },
    { category_id:'c_ops_log',    name:'호출 로그 조회' },
    { category_id:'c_ops_limit',  name:'호출량 제한(Quota)' },
    { category_id:'c_ops_alarm',  name:'장애 알림 설정' },
    { category_id:'c_ops_deploy', name:'운영 반영(배포)' },
    { category_id:'c_ops_env',    name:'개발 · 운영 환경 분리' },
    { category_id:'c_ops_sla',    name:'응답 지연 · 타임아웃' },
    { category_id:'c_ops_contact',name:'담당자 문의 · 지원' }
  ]}
];

var CATEGORY_GROUPS_BACKUP = JSON.parse(JSON.stringify(CATEGORY_GROUPS));

var QUICK_CATEGORY_IDS = ['c_reg_flow','c_reg_fields','c_spc_create','c_tpl_modify','c_auth_key','c_ops_stat'];

/* ---------- 문서 더미 (출처 · 관련 문서 모달용) ---------- */
var DOC_FIXTURES = {
  d_reg: {
    doc_id:'d_reg', title:'API 등록', section:'2.1 등록 준비',
    ref:'/portal/guide/api-register',
    excerpt:'API 그룹(SPC)이 먼저 만들어져 있어야 합니다. API Manager > API 등록 화면에서 그룹을 선택한 뒤 서비스 정보와 호출 정보를 입력합니다.\n\n권한그룹을 지정하지 않으면 내부 관리자만 호출할 수 있는 상태로 저장됩니다. 저장 이후에도 운영 반영 전까지는 개발 환경에서만 호출됩니다.'
  },
  d_fields: {
    doc_id:'d_fields', title:'API 등록 - 입력 항목 상세 설명', section:'2.2 입력 항목',
    ref:'/portal/guide/api-register-fields',
    excerpt:'권한그룹 · 이 API를 호출할 수 있는 사용자 묶음입니다. 사전에 인증·권한 메뉴에서 만들어 둔 권한그룹만 선택할 수 있습니다.\n\n서비스 URI · 포털에 노출되는 외부 경로입니다.\n운영 URI · 실제 백엔드로 전달되는 내부 경로입니다.\n타임아웃 · 기본 5초이며 최대 30초까지 늘릴 수 있습니다.'
  },
  d_spc: {
    doc_id:'d_spc', title:'API 그룹(SPC) 등록', section:'3.1 그룹 생성',
    ref:'',
    excerpt:'API 그룹은 동일한 인증 정책과 호출 도메인을 공유하는 API의 묶음입니다. 그룹 코드는 영문 대문자와 숫자, 최대 12자까지 사용할 수 있으며 등록 후에는 변경할 수 없습니다.'
  },
  d_tpl: {
    doc_id:'d_tpl', title:'템플릿 관리', section:'4.3 템플릿 수정',
    ref:'/portal/guide/template',
    excerpt:'템플릿을 수정하면 해당 템플릿을 참조하는 모든 API의 다음 호출부터 반영됩니다. 이미 진행 중인 호출에는 영향을 주지 않습니다.\n\n변경 이력은 템플릿 상세 화면의 이력 탭에서 확인할 수 있습니다.'
  }
};

var MOCK_ANSWER = '**API 그룹(SPC)** 을 먼저 만든 뒤 \'API 등록\' 화면에서 등록을 진행합니다.\n\n1. API Manager > **API 그룹** 메뉴에서 그룹을 등록합니다.\n2. `API 등록` 화면에서 방금 만든 그룹을 선택합니다.\n3. 서비스 URI · 운영 URI · 권한그룹을 입력하고 저장합니다.\n\n- 권한그룹을 비워두면 내부 관리자만 호출할 수 있습니다.\n- 저장 후 **운영 반영**을 해야 운영 환경에서 호출됩니다.';

/* ============================================================ */
$(function(){

  var $block   = $('#chatBlock');
  var $list    = $('#chatList');
  var $inner   = $('#chatListInner');
  var $intro   = $('#chatIntro');
  var $compose = $('#chatCompose');
  var $input   = $('#chatInput');
  var $send    = $('#chatSend');

  var $trigWrap = $('.chat_cat_trigger_wrap');
  var $trigger  = $('#chatCatTrigger');
  var $trigLabel= $trigger.find('.chat_cat_trigger_label');
  var $clear    = $('.chat_cat_clear');
  var $pop      = $('#chatCatPopover');
  var $popList  = $('#chatCatList');
  var $search   = $('#chatCatSearch');
  /* 인트로 펼침 — 아래 팝오버와 같은 마크업을 그 자리에서 씁니다 */
  var $more      = $('#chatCatMore');
  var $introCats = $('#chatIntroCats');
  var $introList = $('#chatIntroCatList');
  var $introSearch = $('#chatIntroCatSearch');
  var $qBtn     = $('#chatCatQBtn');
  var $qList    = $('#chatCatQuestions');
  var $modal    = $('#chatDocModal');
  var $reset    = $('#chatReset');
  var $toBottom = $('#chatToBottom');
  var $live     = $('#chatLive');

  var BOTTOM_GAP = 160;   /* 이 거리 이상 떨어졌을 때만 [맨 아래로] 노출 */

  var selected = null;   /* {category_id, name} */
  var waiting  = false;

  /* ---------- 유틸 ---------- */
  function esc(s){
    return String(s == null ? '' : s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }
  function tpl(id){ return $($('#'+id).prop('content').cloneNode(true)); }
  function findCategory(id){
    var found = null;
    $.each(CATEGORY_GROUPS, function(_, g){
      $.each(g.categories, function(_, c){ if(c.category_id === id){ found = c; return false; } });
      return found ? false : true;
    });
    return found;
  }
  function scrollBottom(){ $list.stop().animate({ scrollTop: $list[0].scrollHeight }, 180); }

  /* ---------- 상태 갱신 (새 대화 / 맨 아래로) ---------- */
  function hasMessages(){ return $inner.find('.chat_msg').length > 0; }
  function updateReset(){ $reset.prop('disabled', waiting || !hasMessages()); }
  function atBottom(){
    var el = $list[0];
    return el.scrollHeight - el.scrollTop - el.clientHeight <= BOTTOM_GAP;
  }
  function updateToBottom(){
    var show = hasMessages() && !atBottom();
    $toBottom.toggleClass('is_shown', show);
    if(!show) $toBottom.removeClass('is_new');
  }

  /* ---------- 마크다운 렌더 (번호목록/불릿/굵게/코드/문단) ---------- */
  function inline(text){
    return esc(text)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  }
  function renderMarkdown(src){
    var blocks = String(src || '').replace(/\r\n/g,'\n').split(/\n{2,}/);
    var html = '';
    $.each(blocks, function(_, block){
      var lines = block.split('\n').filter(function(l){ return l.trim() !== ''; });
      if(!lines.length) return;
      if(/^\s*\d+\.\s/.test(lines[0])){
        html += '<ol>' + lines.map(function(l){
          return '<li>' + inline(l.replace(/^\s*\d+\.\s/,'')) + '</li>';
        }).join('') + '</ol>';
      } else if(/^\s*[-*]\s/.test(lines[0])){
        html += '<ul>' + lines.map(function(l){
          return '<li>' + inline(l.replace(/^\s*[-*]\s/,'')) + '</li>';
        }).join('') + '</ul>';
      } else {
        html += '<p>' + lines.map(inline).join('<br>') + '</p>';
      }
    });
    return html;
  }

  /* ---------- 인트로 칩 ---------- */
  /* 주제가 하나도 없는 설치처가 있습니다 — 그때는 칩·소제목·[전체 주제 보기]가 함께 숨습니다 */
  function updateCatVisibility(){
    var total = 0;
    $.each(CATEGORY_GROUPS, function(_, g){ total += (g.categories || []).length; });
    var none = total === 0;
    if(none) closeIntroCats();
    $('.chat_intro_sub, #chatCatQuick, #chatCatMore').prop('hidden', none);
    $('.chat_cat_trigger_wrap').prop('hidden', none);
  }

  function buildQuick(){
    var $wrap = $('#chatCatQuick').empty();
    $.each(QUICK_CATEGORY_IDS.slice(0,6), function(_, id){
      var c = findCategory(id);
      if(!c) return;
      $('<button type="button" class="chat_cat_quick_chip"></button>')
        .attr('data-category-id', c.category_id).text(c.name).appendTo($wrap);
    });
    updateCatVisibility();
  }

  /* ---------- 주제 목록 (아래 팝오버 · 인트로 펼침 공용) ----------
     서버 응답(/api/categories)으로 매번 다시 그립니다. 개수도 여기서 채웁니다. */
  function buildCatList($list, query){
    var q = $.trim(query || '').toLowerCase();
    $list.empty();
    var hit = 0;

    $.each(CATEGORY_GROUPS, function(_, g){
      var cats = g.categories.filter(function(c){
        return !q || c.name.toLowerCase().indexOf(q) > -1;
      });
      if(q && !cats.length) return;
      hit += cats.length;

      var $g = $('<div class="chat_cat_group"></div>').attr('data-group-id', g.group_id);
      $('<button type="button" class="chat_cat_group_head"></button>')
        .attr('data-group-id', g.group_id)
        .attr('aria-expanded', q ? 'true' : 'false')
        .append('<span class="chat_cat_group_arrow" aria-hidden="true">▸</span>')
        .append($('<span class="chat_cat_group_name"></span>').text(g.group_name))
        .append($('<span class="chat_cat_group_count"></span>').text('(' + g.categories.length + ')'))
        .appendTo($g);

      var $items = $('<div class="chat_cat_items"></div>').appendTo($g);
      $.each(cats, function(_, c){
        var label = esc(c.name);
        if(q){
          var i = c.name.toLowerCase().indexOf(q);
          label = esc(c.name.slice(0,i)) + '<mark>' + esc(c.name.slice(i, i+q.length)) + '</mark>' + esc(c.name.slice(i+q.length));
        }
        $('<button type="button" class="chat_cat_item" role="option"></button>')
          .attr('data-category-id', c.category_id)
          .attr('aria-selected', selected && selected.category_id === c.category_id ? 'true' : 'false')
          .attr('title', c.name)
          .html(label)
          .appendTo($items);
      });

      if(q) $g.addClass('is_open');
      $g.appendTo($list);
    });

    /* 검색어가 없으면 첫 대분류만 펼칩니다 — 5줄만 보이면 "목록이 비었다"로 읽힙니다 */
    if(!q){
      var $first = $list.children('.chat_cat_group').first().addClass('is_open');
      $first.find('.chat_cat_group_head').attr('aria-expanded','true');
    }
    $list.parent().toggleClass('is_empty', hit === 0);
    return hit;
  }
  function buildPopover(query){ buildCatList($popList, query); }

  function openPopover(){
    closeQuestions();
    buildPopover($search.val());
    $pop.addClass('is_open');
    $trigger.attr('aria-expanded','true');
    $pop.attr('data-selected-category', selected ? selected.category_id : '');
    setTimeout(function(){ $search.trigger('focus'); }, 0);
  }
  function closePopover(){
    $pop.removeClass('is_open');
    $trigger.attr('aria-expanded','false');
    $popList.find('.is_focus').removeClass('is_focus');
  }
  function togglePopover(){ $pop.hasClass('is_open') ? closePopover() : openPopover(); }

  /* ---------- 인트로 펼침 (요청서 09 A안) ---------- */
  function openIntroCats(){
    closePopover(); closeQuestions();
    buildCatList($introList, $introSearch.val());
    $introCats.addClass('is_open');
    $more.attr('aria-expanded','true');
    setTimeout(function(){ $introSearch.trigger('focus'); }, 0);
  }
  function closeIntroCats(){
    $introCats.removeClass('is_open');
    $more.attr('aria-expanded','false');
    $introList.find('.is_focus').removeClass('is_focus');
  }
  function toggleIntroCats(){ $introCats.hasClass('is_open') ? closeIntroCats() : openIntroCats(); }

  /* ---------- 선택 상태 ---------- */
  function setCategory(id){
    var c = findCategory(id);
    if(!c) return;
    selected = { category_id:c.category_id, name:c.name };
    $trigWrap.addClass('is_active');
    $trigger.addClass('is_active')
      .attr('data-category-id', c.category_id)
      .attr('data-category-label', c.name)
      .attr('title', c.name);
    $trigLabel.text(c.name);
    $pop.attr('data-selected-category', c.category_id);
    buildQuestions(c);
  }
  function clearCategory(){
    selected = null;
    $trigWrap.removeClass('is_active');
    $trigger.removeClass('is_active')
      .removeAttr('data-category-id').removeAttr('data-category-label').removeAttr('title');
    $trigLabel.text('주제 선택');
    $pop.attr('data-selected-category','');
    $popList.find('.chat_cat_item').attr('aria-selected','false');
    $introList.find('.chat_cat_item').attr('aria-selected','false');
    buildQuestions(null);
  }

  /* ---------- 추천 질문 ---------- */
  function buildQuestions(cat){
    closeQuestions();
    $qList.empty();
    var qs = (cat && cat.questions) || [];
    if(!qs.length){ $qBtn.prop('hidden', true); return; }
    $qBtn.prop('hidden', false).find('.chat_q_btn_count').text(qs.length);
    $.each(qs, function(_, q){
      $('<button type="button" class="chat_q_item" role="option"></button>')
        .attr('data-question', q).text(q).appendTo($qList);
    });
  }
  function openQuestions(){ closePopover(); $qList.addClass('is_open'); $qBtn.attr('aria-expanded','true'); }
  function closeQuestions(){ $qList.removeClass('is_open'); $qBtn.attr('aria-expanded','false'); }

  /* ---------- 대기 상태 ---------- */
  function setWaiting(on){
    waiting = !!on;
    $compose.toggleClass('is_waiting', waiting);
    $input.prop('disabled', waiting);
    $send.prop('disabled', waiting);
    $trigger.prop('disabled', waiting);
    $qBtn.prop('disabled', waiting);
    if(waiting){ closePopover(); closeQuestions(); }
    updateReset();
  }

  /* ---------- 메시지 렌더 ---------- */
  function hideIntro(){ closeIntroCats(); $intro.hide(); }

  /* 새 말풍선이 붙은 뒤 — 하단에 있을 때만 따라갑니다 */
  function afterAppend(isBotAnswer){
    var wasBottom = atBottom();
    updateReset();
    if(wasBottom){ scrollBottom(); }
    else if(isBotAnswer){ $toBottom.addClass('is_new'); }
    updateToBottom();
  }

  function pushUser(question, category){
    hideIntro();
    var $m = tpl('tpl_user');
    if(category){ $m.find('.chat_msg_cat').text('＃ ' + category.name); }
    else { $m.find('.chat_msg_cat').remove(); }   /* 미선택 시 배지 제거 */
    $m.find('[data-bind=question]').text(question);
    $inner.append($m);
    afterAppend(false);
  }

  function srcBadges(docs){
    var $frag = $(document.createDocumentFragment());
    $.each(docs || [], function(_, d){
      var $s = tpl('tpl_src');
      var $btn = $s.find('.chat_src_item');
      $btn.find('.chat_src_title').text(d.title);
      $btn.attr('data-doc-id', d.doc_id);
      if(d.ref){ $btn.attr('data-ref', d.ref); } else { $btn.addClass('is_plain'); }
      $frag.append($s);
    });
    return $frag;
  }

  function pushAnswer(data){
    hideIntro();
    var $m = tpl('tpl_answer');
    $m.find('[data-bind=answer]').html(renderMarkdown(data.answer));
    if(data.source_docs && data.source_docs.length){
      $m.find('[data-bind=source_docs]').append(srcBadges(data.source_docs));
    } else {
      $m.find('.chat_src').remove();
    }
    $inner.append($m);
    afterAppend(true);
  }

  function pushRelated(docs){
    hideIntro();
    var $m = tpl('tpl_related');
    var $wrap = $m.find('[data-bind=related_docs]');
    $.each((docs || []).slice(0,3), function(_, d){
      var $c = tpl('tpl_related_item');
      $c.find('.chat_rel_title_txt').text(d.title);
      $c.find('.chat_rel_section').text(d.section);
      $c.find('.chat_rel_excerpt').text(d.excerpt);
      $c.find('[data-doc-open]').attr('data-doc-id', d.doc_id);
      if(d.ref) $c.find('[data-doc-open]').attr('data-ref', d.ref);
      $wrap.append($c);
    });
    $inner.append($m);
    afterAppend(true);
  }

  function pushUnresolved(message, ticketId){
    hideIntro();
    var $m = tpl('tpl_unresolved');
    $m.find('[data-bind=message]').text(message || '문의가 담당자에게 접수되었습니다.');
    $m.find('[data-bind=ticket_id]').text(ticketId || newTicketId());
    $inner.append($m);
    afterAppend(true);
  }

  function pushError(question){
    hideIntro();
    var $m = tpl('tpl_error');
    $m.find('[data-retry]').attr('data-question', question || '');
    $inner.append($m);
    afterAppend(true);
  }

  function pushLoading(){
    hideIntro();
    $inner.append(tpl('tpl_loading'));
    afterAppend(false);
    setWaiting(true);
  }
  function popLoading(){
    $inner.find('.chat_msg_loading').remove();
    setWaiting(false);
  }

  /* ---------- 새 대화 (#chatReset) ---------- */
  function doReset(){
    setWaiting(false);
    $inner.find('.chat_msg').remove();
    $intro.show();
    clearCategory();
    closePopover(); closeQuestions();
    $list.scrollTop(0);
    $toBottom.removeClass('is_shown is_new');
    updateReset();
  }
  $reset.on('click', function(){
    if($reset.prop('disabled')) return;
    /* 접수번호는 다시 볼 수 없어 이 경우에만 확인합니다 */
    if($inner.find('.chat_ticket').length){ $('#chatResetModal').addClass('is_open'); return; }
    doReset();
  });
  $('#chatResetOk').on('click', function(){ $('#chatResetModal').removeClass('is_open'); doReset(); });
  $(document).on('click', '[data-reset-cancel]', function(){ $('#chatResetModal').removeClass('is_open'); });
  $('#chatResetModal').on('click', function(e){ if(e.target === this) $(this).removeClass('is_open'); });

  /* ---------- 답변 복사 (.chat_msg_copy) ---------- */
  function copyText(txt){
    var ta = document.createElement('textarea');
    ta.value = txt;
    ta.setAttribute('readonly','');
    ta.style.cssText = 'position:absolute;left:-9999px;top:0;';
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try{ ok = document.execCommand('copy'); }catch(err){ ok = false; }
    document.body.removeChild(ta);
    return ok;
  }
  function flashCopy($btn, ok){
    if(!ok){ $live.text('복사하지 못했습니다'); return; }
    var label = $btn.data('label') || $btn.text();
    $btn.data('label', label).addClass('is_done').text('복사됨');
    $live.text('복사됨');
    clearTimeout($btn.data('timer'));
    $btn.data('timer', setTimeout(function(){ $btn.removeClass('is_done').text(label); }, 1500));
  }
  /* 화면에 보이는 글자 그대로 — 마크다운 기호·출처·검수 문구 제외 */
  function bubbleText($md){
    var out = [];
    $md.children().each(function(){
      var $el = $(this), tag = this.tagName.toLowerCase();
      if(tag === 'ol' || tag === 'ul'){
        $el.children('li').each(function(i){
          out.push((tag === 'ol' ? (i+1) + '. ' : '- ') + $.trim($(this).text()));
        });
      } else {
        out.push($.trim($el.text()));
      }
      out.push('');
    });
    return $.trim(out.join('\n')).replace(/\n{3,}/g, '\n\n');
  }
  /* ============================================================
     답변 피드백 (요청서 10 A)
     저장은 자동입니다. 실패해도 화면은 멈추지 않고 조용히 되돌립니다.
     개발 교체 지점: sendFeedback() 안을 POST /api/feedback 으로.
     ============================================================ */
  var FB_FAIL_NEXT = false;   /* 목업 바가 켜는 1회용 실패 플래그 */

  function sendFeedback(payload, ok, fail){
    setTimeout(function(){
      if(FB_FAIL_NEXT){ FB_FAIL_NEXT = false; fail(); return; }
      ok();
    }, 260);
  }
  function fbDone($bubble, msg){
    var $d = $bubble.find('.chat_fb_done').text(msg || '의견 감사합니다').addClass('is_shown');
    clearTimeout($d.data('t'));
    $d.data('t', setTimeout(function(){ $d.removeClass('is_shown'); }, 2000));
  }
  function fbReset($bubble){
    $bubble.find('.chat_fb_btn').removeClass('is_on').attr('aria-pressed','false');
    $bubble.find('.chat_fb_reasons').removeClass('is_open');
  }

  $(document).on('click', '.chat_fb_btn', function(){
    var $btn = $(this);
    var $bubble = $btn.closest('.chat_bubble');
    var kind = $btn.attr('data-fb');
    var wasOn = $btn.hasClass('is_on');
    var prev = $bubble.find('.chat_fb_btn.is_on').attr('data-fb') || '';

    fbReset($bubble);
    $bubble.find('.chat_fb_done').removeClass('is_shown');
    /* 다시 누르면 취소, 👍↔👎 도 바꿀 수 있습니다 — 마지막에 고른 것만 유효 */
    var next = wasOn ? '' : kind;
    if(next){ $btn.addClass('is_on').attr('aria-pressed','true'); }

    sendFeedback({ vote:next }, function(){
      if(!next) return;
      if(next === 'down') $bubble.find('.chat_fb_reasons').addClass('is_open');
      else fbDone($bubble, '감사합니다');   /* 👍는 이유를 묻지 않습니다 */
    }, function(){
      fbReset($bubble);
      if(prev) $bubble.find('.chat_fb_btn[data-fb="' + prev + '"]').addClass('is_on').attr('aria-pressed','true');
    });
  });

  /* 이유를 안 골라도 👎는 이미 기록돼 있습니다 */
  $(document).on('click', '.chat_fb_reason', function(){
    var $bubble = $(this).closest('.chat_bubble');
    var reason = $(this).attr('data-reason');
    $bubble.find('.chat_fb_reasons').removeClass('is_open');
    sendFeedback({ reason:reason }, function(){ fbDone($bubble); }, function(){ fbDone($bubble); });
  });
  $(document).on('click', '.chat_fb_skip', function(){
    $(this).closest('.chat_bubble').find('.chat_fb_reasons').removeClass('is_open');
  });

  $(document).on('click', '[data-copy]', function(){
    var $btn = $(this);
    flashCopy($btn, copyText(bubbleText($btn.closest('.chat_bubble').find('.chat_md'))));
  });

  function newTicketId(){
    var d = new Date(), p = function(n){ return (n<10?'0':'') + n; };
    var rnd = Math.random().toString(16).slice(2,7).toUpperCase();
    return 'TCK-' + d.getFullYear() + p(d.getMonth()+1) + p(d.getDate()) + '-' + rnd;
  }

  /* ---------- 전송 (더미 응답 — 개발에서 API 호출로 교체) ---------- */
  function submit(text){
    var q = $.trim(text != null ? text : $input.val());
    if(!q || waiting) return;
    pushUser(q, selected);
    $input.val('');
    closePopover(); closeQuestions();
    pushLoading();

    setTimeout(function(){
      popLoading();
      /* 더미 분기: '문서'/'모르' 포함 시 related_docs, '오류테스트' 시 error */
      if(q.indexOf('오류테스트') > -1){ pushError(q); return; }
      if(q.indexOf('문서') > -1 || q.indexOf('모르') > -1){
        pushRelated([DOC_FIXTURES.d_fields, DOC_FIXTURES.d_reg]);
        return;
      }
      pushAnswer({ answer: MOCK_ANSWER, source_docs:[DOC_FIXTURES.d_reg, DOC_FIXTURES.d_fields] });
    }, 900);
  }

  /* ---------- 문서 모달 ---------- */
  function openDoc(docId){
    var d = DOC_FIXTURES[docId] || DOC_FIXTURES.d_reg;
    $modal.find('[data-bind=doc_title]').text(d.title);
    $modal.find('[data-bind=doc_section]').text(d.section);
    $modal.find('[data-bind=doc_excerpt]').text(d.excerpt);
    var $link = $modal.find('[data-bind=doc_ref]');
    if(d.ref){ $link.removeClass('is_hidden').attr('href', d.ref); } else { $link.addClass('is_hidden'); }
    $modal.addClass('is_open');
    $modal.find('.chat_doc_close').trigger('focus');
  }
  function closeDoc(){ $modal.removeClass('is_open'); }

  /* ---------- 이벤트 ---------- */
  $send.on('click', function(){ submit(); });
  $input.on('keydown', function(e){ if(e.key === 'Enter'){ e.preventDefault(); submit(); } });
  $input.on('focus click', function(){ closePopover(); closeQuestions(); });

  $trigger.on('click', function(e){ e.stopPropagation(); togglePopover(); });
  $clear.on('click', function(e){ e.stopPropagation(); clearCategory(); })
        .on('keydown', function(e){
          if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); e.stopPropagation(); clearCategory(); }
        });
  $pop.find('.chat_cat_pop_close').on('click', closePopover);
  $pop.on('click', function(e){ e.stopPropagation(); });
  $qList.on('click', function(e){ e.stopPropagation(); });

  buildQuick();

  $more.on('click', function(e){ e.stopPropagation(); toggleIntroCats(); });
  $introCats.on('click', function(e){ e.stopPropagation(); });
  $(document).on('click', '.chat_cat_quick_chip', function(){
    setCategory($(this).data('category-id'));
  });

  /* 인트로 목록 — 아래 팝오버와 같은 조작입니다 */
  $introList.on('click', '.chat_cat_group_head', function(){
    var $g = $(this).closest('.chat_cat_group').toggleClass('is_open');
    $(this).attr('aria-expanded', $g.hasClass('is_open') ? 'true' : 'false');
  });
  $introList.on('click', '.chat_cat_item', function(){
    setCategory($(this).attr('data-category-id'));   /* 아래 트리거도 함께 선택 상태가 됩니다 */
    closeIntroCats();
    $input.trigger('focus');
  });
  $introSearch.on('input', function(){ buildCatList($introList, $(this).val()); });
  $introSearch.on('keydown', function(e){
    if(e.key === 'ArrowDown'){
      e.preventDefault();
      var $first = $introList.find('.chat_cat_group.is_open .chat_cat_item').first();
      if(!$first.length){
        $introList.find('.chat_cat_group').first().addClass('is_open');
        $first = $introList.find('.chat_cat_item').first();
      }
      $first.addClass('is_focus').trigger('focus');
    } else if(e.key === 'Escape'){ closeIntroCats(); $more.trigger('focus'); }
  });
  $introList.on('keydown', '.chat_cat_item', function(e){
    var $items = $introList.find('.chat_cat_group.is_open .chat_cat_item');
    var i = $items.index(this);
    if(e.key === 'ArrowDown'){ e.preventDefault(); moveFocus($items, i+1); }
    else if(e.key === 'ArrowUp'){
      e.preventDefault();
      if(i === 0){ $introSearch.trigger('focus'); $items.removeClass('is_focus'); }
      else moveFocus($items, i-1);
    }
    else if(e.key === 'Enter'){ e.preventDefault(); $(this).trigger('click'); }
    else if(e.key === 'Escape'){ closeIntroCats(); $more.trigger('focus'); }
  });

  $popList.on('click', '.chat_cat_group_head', function(){
    var $g = $(this).closest('.chat_cat_group').toggleClass('is_open');
    $(this).attr('aria-expanded', $g.hasClass('is_open') ? 'true' : 'false');
  });
  $popList.on('click', '.chat_cat_item', function(){
    setCategory($(this).attr('data-category-id'));
    closePopover();
    $input.trigger('focus');
  });

  $search.on('input', function(){ buildPopover($(this).val()); });
  $search.on('keydown', function(e){
    if(e.key === 'ArrowDown'){
      e.preventDefault();
      var $first = $popList.find('.chat_cat_group.is_open .chat_cat_item').first();
      if(!$first.length){ $popList.find('.chat_cat_group').first().addClass('is_open'); $first = $popList.find('.chat_cat_item').first(); }
      $first.addClass('is_focus').trigger('focus');
    } else if(e.key === 'Escape'){ closePopover(); $trigger.trigger('focus'); }
  });
  $popList.on('keydown', '.chat_cat_item', function(e){
    var $items = $popList.find('.chat_cat_group.is_open .chat_cat_item');
    var i = $items.index(this);
    if(e.key === 'ArrowDown'){ e.preventDefault(); moveFocus($items, i+1); }
    else if(e.key === 'ArrowUp'){
      e.preventDefault();
      if(i <= 0){ $popList.find('.is_focus').removeClass('is_focus'); $search.trigger('focus'); }
      else moveFocus($items, i-1);
    }
    else if(e.key === 'Enter'){ e.preventDefault(); $(this).trigger('click'); }
    else if(e.key === 'Escape'){ closePopover(); $trigger.trigger('focus'); }
  });
  function moveFocus($items, i){
    if(i < 0 || i >= $items.length) return;
    $popList.find('.is_focus').removeClass('is_focus');
    $items.eq(i).addClass('is_focus').trigger('focus');
  }

  $qBtn.on('click', function(e){
    e.stopPropagation();
    $qList.hasClass('is_open') ? closeQuestions() : openQuestions();
  });
  $qList.on('click', '.chat_q_item', function(){
    var q = $(this).attr('data-question');
    closeQuestions();
    submit(q);
  });

  $(document).on('click', '[data-doc-open]', function(){ openDoc($(this).attr('data-doc-id')); });
  $(document).on('click', '[data-ask-support]', function(){
    pushUnresolved('문의가 담당자에게 접수되었습니다.', newTicketId());
  });
  $(document).on('click', '[data-retry]', function(){
    var q = $(this).attr('data-question');
    $(this).closest('.chat_msg').remove();
    if(q) { $inner.append(tpl('tpl_loading')); setWaiting(true);
      setTimeout(function(){ popLoading(); pushAnswer({ answer: MOCK_ANSWER, source_docs:[DOC_FIXTURES.d_reg] }); }, 900); }
  });
  $(document).on('click', '.chat_ticket_copy', function(){
    var $btn = $(this);
    flashCopy($btn, copyText($btn.closest('.chat_ticket').find('.chat_ticket_id').text()));
  });

  $modal.on('click', function(e){ if(e.target === this) closeDoc(); });
  $modal.find('.chat_doc_close').on('click', closeDoc);

  /* ---------- 맨 아래로 (#chatToBottom) ---------- */
  $list.on('scroll', updateToBottom);
  $toBottom.on('click', function(){
    $toBottom.removeClass('is_new');
    scrollBottom();
    setTimeout(updateToBottom, 220);
  });

  $(document).on('click', function(){ closePopover(); closeQuestions(); closeIntroCats(); });
  $(document).on('keydown', function(e){
    if(e.key !== 'Escape') return;
    if($modal.hasClass('is_open')) closeDoc();
    else if($introCats.hasClass('is_open')){ closeIntroCats(); $more.trigger('focus'); }
    else if($pop.hasClass('is_open')) closePopover();
    else if($qList.hasClass('is_open')) closeQuestions();
  });

  buildPopover('');
  updateReset(); updateToBottom();

  /* ============================================================
     [DEV ONLY] 확인용 상태 목업 — 개발 이식 시 이 블록 전체 삭제
     ============================================================ */
  $('[data-dev-only]').on('click', 'button', function(e){
    e.stopPropagation();
    var k = $(this).data('dev');
    if(k === 'answer'){ popLoading(); pushUser('API 등록은 어떻게 하나요?', selected); pushAnswer({ answer:MOCK_ANSWER, source_docs:[DOC_FIXTURES.d_reg, DOC_FIXTURES.d_fields] }); }
    if(k === 'related'){ popLoading(); pushUser('권한그룹 값을 어디서 확인하나요?', selected); pushRelated([DOC_FIXTURES.d_fields, DOC_FIXTURES.d_reg, DOC_FIXTURES.d_spc]); }
    if(k === 'unresolved'){ popLoading(); pushUnresolved('문의가 담당자에게 접수되었습니다.', 'TCK-20260814-A3F91'); }
    if(k === 'loading'){ pushLoading(); }
    if(k === 'error'){ popLoading(); pushError('API 등록은 어떻게 하나요?'); }
    if(k === 'cat-none'){ clearCategory(); }
    if(k === 'cat-set'){ setCategory('c_reg_fields'); }
    if(k === 'pop-open'){ $search.val(''); openPopover(); }
    if(k === 'pop-empty'){ openPopover(); $search.val('zzzz').trigger('input'); }
    if(k === 'q-open'){ if(!selected || !$qBtn.is(':visible')) setCategory('c_reg_flow'); openQuestions(); }
    if(k === 'waiting'){ setWaiting(!waiting); }
    if(k === 'newchat-on'){ if(!hasMessages()){ popLoading(); pushUser('API 등록은 어떻게 하나요?', selected); pushAnswer({ answer:MOCK_ANSWER, source_docs:[DOC_FIXTURES.d_reg] }); } updateReset(); }
    if(k === 'newchat-off'){ doReset(); }
    if(k === 'ticket-chat'){ popLoading(); pushUser('결재선은 어디서 확인하죠?', selected); pushUnresolved('문의가 담당자에게 접수되었습니다.', 'TCK-20260815-A3F91'); }
    if(k === 'copy-done'){
      if(!$inner.find('[data-copy]').length){ popLoading(); pushAnswer({ answer:MOCK_ANSWER, source_docs:[DOC_FIXTURES.d_reg] }); }
      flashCopy($inner.find('[data-copy]').last(), true);
    }
    if(k === 'bottom-show'){
      while($inner.find('.chat_msg').length < 8){ pushAnswer({ answer:MOCK_ANSWER, source_docs:[DOC_FIXTURES.d_reg] }); }
      $list.scrollTop(0); updateToBottom();
    }
    if(k === 'bottom-new'){
      while($inner.find('.chat_msg').length < 8){ pushAnswer({ answer:MOCK_ANSWER, source_docs:[DOC_FIXTURES.d_reg] }); }
      $list.scrollTop(0); updateToBottom(); $toBottom.addClass('is_shown is_new');
    }
    if(k === 'bottom-hide'){ scrollBottom(); setTimeout(updateToBottom, 220); }
    if(k === 'intro-cats-open'){ openIntroCats(); }
    if(k === 'intro-cats-close'){ closeIntroCats(); }
    if(k === 'cat-empty'){
      CATEGORY_GROUPS = [];
      clearCategory(); buildQuick(); buildPopover('');
    }
    if(k === 'intro-pick'){
      openIntroCats();
      var $first = $introList.find('.chat_cat_item').first();
      if($first.length) $first.trigger('click');
    }
    /* ---- 답변 피드백 ---- */
    if(k.indexOf('fb-') === 0){
      if(!$inner.find('.chat_fb').length){
        popLoading(); pushUser('API 등록은 어떻게 하나요?', selected);
        pushAnswer({ answer:MOCK_ANSWER, source_docs:[DOC_FIXTURES.d_reg] });
      }
      var $b = $inner.find('.chat_bubble_bot').last();
      fbReset($b); $b.find('.chat_fb_done').removeClass('is_shown');
      if(k === 'fb-up'){ $b.find('.chat_fb_up').trigger('click'); }
      if(k === 'fb-down'){ $b.find('.chat_fb_down').trigger('click'); }
      if(k === 'fb-reason'){
        $b.find('.chat_fb_down').trigger('click');
        setTimeout(function(){ $b.find('.chat_fb_reason[data-reason="wrong"]').trigger('click'); }, 320);
      }
      if(k === 'fb-fail'){
        $b.find('.chat_fb_up').addClass('is_on').attr('aria-pressed','true');
        FB_FAIL_NEXT = true;
        setTimeout(function(){ $b.find('.chat_fb_down').trigger('click'); }, 120);
      }
    }
    if(k === 'reset'){
      CATEGORY_GROUPS = CATEGORY_GROUPS_BACKUP.map(function(g){ return JSON.parse(JSON.stringify(g)); });
      buildQuick(); buildPopover(''); closeIntroCats();
      doReset(); $('#chatResetModal').removeClass('is_open');
    }
  });
  /* ==================== [DEV ONLY] end ==================== */

});
