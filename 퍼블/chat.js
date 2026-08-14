/* ==========================================================================
   openapi-chat — API Manager 도우미 (퍼블 목업 스크립트, jQuery)
   실제 POST /ask 연동은 개발 쪽에서 처리합니다.
   → askApi() 안의 setTimeout 더미 응답 부분만 $.ajax 로 교체하면 됩니다.
   ========================================================================== */
(function ($) {
  'use strict';

  /* ==========================================================================
     카테고리 데이터 (2단계: 대분류 group → 카테고리 category)
     개발 단계에서 이 상수를 서버 API 응답으로 교체합니다.
     { group_id, group_label, categories: [{ id, label, questions: [] }] }
     ※ 아래는 개수 부하 확인용 더미(총 48개). 문구는 목업용 임의값입니다.
     ========================================================================== */
  var CATEGORY_GROUPS = [
    {
      group_id: 'api', group_label: 'API 등록', categories: [
        { id: 'api_reg_flow', label: 'API 등록 절차', questions: ['API 등록은 어떻게 하나요?', 'API 등록 전에 그룹을 먼저 만들어야 하나요?', '등록 후 반영까지 얼마나 걸리나요?'] },
        { id: 'api_reg_field', label: 'API 등록 항목 설명', questions: ['권한그룹은 무엇을 선택해야 하나요?', 'Path와 Method는 어떻게 입력하나요?', '필수 입력 항목은 무엇인가요?', '서비스와 그룹의 차이는 무엇인가요?'] },
        { id: 'api_reg_err', label: 'API 등록 오류', questions: ['등록한 API가 목록에 안 보여요', '저장 시 중복 경로 오류가 납니다'] },
        { id: 'api_quick', label: '빠른 API 등록', questions: ['빠른 등록과 일반 등록의 차이는?', '빠른 등록에서 인증 설정을 바꿀 수 있나요?'] },
        { id: 'api_edit', label: 'API 수정·삭제', questions: ['등록한 API를 수정·삭제하려면?', '운영 중인 API를 수정하면 바로 반영되나요?'] },
        { id: 'api_deploy', label: 'API 배포', questions: ['배포 버튼이 활성화되지 않습니다', '배포 이력은 어디서 보나요?'] },
        { id: 'api_endpoint', label: '엔드포인트 설정', questions: ['Base URL은 어떤 형식으로 입력하나요?', '포트가 다른 서버도 등록할 수 있나요?'] },
        { id: 'api_auth', label: '인증 방식 설정', questions: ['API Key와 OAuth 2.0 중 무엇을 쓰나요?', 'OAuth 스코프는 어디서 정의하나요?'] },
        { id: 'api_param', label: '파라미터 정의', questions: ['Query와 Path 파라미터를 함께 쓸 수 있나요?', '필수 파라미터 표시는 어떻게 하나요?'] },
        { id: 'api_header', label: '헤더 / CORS', questions: ['커스텀 헤더를 추가할 수 있나요?', 'CORS 허용 도메인은 어디서 설정하나요?'] },
        { id: 'api_version', label: '버전 관리', questions: ['v1, v2를 동시에 운영할 수 있나요?', '구버전은 어떻게 폐기하나요?'] },
        { id: 'api_status', label: '상태 / 승인', questions: ['\'작성중\' 상태는 무슨 의미인가요?', '승인 요청은 누가 처리하나요?'] },
        { id: 'api_test', label: '테스트 호출', questions: ['등록 화면에서 바로 호출 테스트가 되나요?', '테스트 결과 401이 반환됩니다'] },
        { id: 'api_limit', label: '트래픽 / 쿼터', questions: ['호출 한도는 어디서 설정하나요?', '한도를 초과하면 어떻게 되나요?'] }
      ]
    },
    {
      group_id: 'spc', group_label: 'API 그룹(스펙)', categories: [
        { id: 'spc_concept', label: 'API 그룹(스펙) 개념', questions: ['API 그룹(스펙)은 무엇인가요?', '그룹 없이 API만 등록해도 되나요?'] },
        { id: 'spc_create', label: '그룹 생성 절차', questions: ['그룹 등록 시 필수 항목은?', '그룹 ID 규칙이 있나요?'] },
        { id: 'spc_oas', label: 'OAS / Swagger 일괄 등록', questions: ['Swagger YAML로 한 번에 등록할 수 있나요?', 'OAS 3.0만 지원하나요?'] },
        { id: 'spc_import_err', label: '일괄 등록 오류', questions: ['YAML 파싱 오류가 납니다', '일부 API만 등록되고 나머지가 누락됩니다'] },
        { id: 'spc_delete', label: '그룹 삭제', questions: ['그룹을 삭제하면 하위 API는 어떻게 되나요?', '삭제한 그룹을 복구할 수 있나요?'] },
        { id: 'spc_move', label: 'API 소속 변경', questions: ['다른 그룹으로 API를 옮길 수 있나요?'] },
        { id: 'spc_doc', label: '포털 문서 노출', questions: ['그룹 문서가 포털에 안 보입니다', '문서 설명 문구는 어디서 수정하나요?'] },
        { id: 'spc_perm', label: '그룹 권한', questions: ['그룹별로 접근 권한을 나눌 수 있나요?'] },
        { id: 'spc_tag', label: '태그 / 분류', questions: ['태그는 몇 개까지 붙일 수 있나요?'] },
        { id: 'spc_server', label: '서버 정보(servers)', questions: ['운영·개발 서버를 함께 표기할 수 있나요?'] },
        { id: 'spc_schema', label: '스키마 / 모델', questions: ['공통 모델을 재사용할 수 있나요?'] },
        { id: 'spc_export', label: '스펙 내보내기', questions: ['등록된 그룹을 YAML로 내려받을 수 있나요?'] }
      ]
    },
    {
      group_id: 'tmplt', group_label: '템플릿 관리', categories: [
        { id: 'tmplt_concept', label: '템플릿 개념', questions: ['템플릿은 어디서 만드나요?', '템플릿과 그룹은 어떻게 다른가요?'] },
        { id: 'tmplt_create', label: '템플릿 등록', questions: ['템플릿 등록 시 필수 항목은?'] },
        { id: 'tmplt_edit', label: '템플릿 수정', questions: ['템플릿을 수정하려면?', '수정하면 기존 API에도 반영되나요?'] },
        { id: 'tmplt_apply', label: '템플릿으로 API 등록', questions: ['템플릿으로 API를 등록하는 방법은?', '템플릿 값 일부만 바꿔 등록할 수 있나요?'] },
        { id: 'tmplt_load', label: '템플릿 불러오기', questions: ['불러오기 목록에 템플릿이 안 보입니다'] },
        { id: 'tmplt_share', label: '템플릿 공유', questions: ['다른 부서와 템플릿을 공유할 수 있나요?'] },
        { id: 'tmplt_delete', label: '템플릿 삭제', questions: ['사용 중인 템플릿을 삭제할 수 있나요?'] },
        { id: 'tmplt_var', label: '치환 변수', questions: ['템플릿에 변수를 넣을 수 있나요?'] },
        { id: 'tmplt_ver', label: '템플릿 버전', questions: ['이전 버전 템플릿으로 되돌릴 수 있나요?'] },
        { id: 'tmplt_default', label: '기본 템플릿 지정', questions: ['부서 기본 템플릿을 지정할 수 있나요?'] },
        { id: 'tmplt_err', label: '템플릿 적용 오류', questions: ['템플릿 적용 후 저장이 실패합니다'] }
      ]
    },
    {
      group_id: 'auth', group_label: '권한 / 계정', categories: [
        { id: 'auth_group', label: '권한그룹 설정', questions: ['권한그룹은 무엇을 선택해야 하나요?', '권한그룹을 새로 만들 수 있나요?'] },
        { id: 'auth_role', label: '역할(Role) 구분', questions: ['관리자와 등록자의 차이는?'] },
        { id: 'auth_apply', label: '권한 신청', questions: ['등록 권한은 어디서 신청하나요?'] },
        { id: 'auth_key', label: 'API Key 발급', questions: ['API Key는 어디서 발급하나요?', '발급한 Key를 재발급할 수 있나요?'] },
        { id: 'auth_expire', label: '만료 / 회수', questions: ['Key 만료 기간을 늘릴 수 있나요?'] },
        { id: 'auth_ip', label: 'IP 접근 제어', questions: ['특정 IP만 허용할 수 있나요?'] },
        { id: 'auth_sso', label: 'SSO 로그인', questions: ['SSO 로그인이 실패합니다'] },
        { id: 'auth_dept', label: '부서 / 조직 정보', questions: ['소속 부서가 잘못 표시됩니다'] }
      ]
    },
    {
      group_id: 'etc', group_label: '기타', categories: [
        { id: 'etc_free', label: '기타 / 직접 입력', questions: [] },
        { id: 'etc_portal', label: '포털 사용 일반', questions: ['포털 공지사항은 어디서 보나요?'] },
        { id: 'etc_contact', label: '담당자 문의', questions: ['담당자에게 직접 문의하려면?'] }
      ]
    }
  ];

  /* 인트로 '자주 찾는 주제' 칩 — 최대 6개, 개발에서 주입 */
  var QUICK_CATEGORY_IDS = ['api_reg_flow', 'api_reg_field', 'spc_create', 'tmplt_edit', 'api_reg_err', 'auth_group'];

  var $list = $('#chatList');
  var $inner = $('#chatListInner');
  var $compose = $('#chatCompose');
  var $input = $('#chatInput');
  var $send = $('#chatSend');
  var $trigger = $('#chatCatTrigger');
  var $triggerMain = $trigger.find('.chat_cat_trigger_main');
  var $popover = $('#chatCatPopover');
  var $search = $('#chatCatSearch');
  var $groups = $('#chatCatGroups');
  var $qbtn = $('#chatCatQBtn');
  var $questions = $('#chatCatQuestions');
  var $quickChips = $('#chatCatQuickChips');

  var waiting = false;
  var lastQuestion = '';
  var selectedId = '';
  var focusIndex = -1;

  /* ---------- 더미 응답 (개발 연동 시 삭제) ---------- */
  var DUMMY = {
    rag: {
      answered_by: 'rag',
      confidence: 0.87,
      answer: "'API 등록' 화면에서 등록합니다.\n\n1. 좌측 메뉴 > API Manager > API 등록 진입\n2. 서비스명·API명·엔드포인트(Base URL)를 입력\n3. 인증 방식(API Key / OAuth 2.0)을 선택\n4. [저장] 후 상단 [배포] 버튼으로 게이트웨이에 반영\n\n배포 전까지는 목록에서 '작성중' 상태로 표시됩니다.",
      source_docs: [
        { title: 'API 등록 가이드', url_or_ref: 'quickApiReg.html' },
        { title: '빠른 API 등록 화면 설명', url_or_ref: 'quickApiReg.html#step2' }
      ]
    },
    cache: {
      answered_by: 'cache',
      confidence: 0.94,
      answer: 'API 그룹(스펙)은 여러 개의 API를 하나의 스펙 문서(Swagger/OpenAPI)로 묶어 관리하는 단위입니다. 그룹을 먼저 등록한 뒤 개별 API를 그룹에 소속시키면, 포털에서 하나의 문서로 노출됩니다.',
      source_docs: [
        { title: 'API 그룹(스펙) 등록', url_or_ref: null },
        { title: '용어 정리', url_or_ref: null }
      ]
    },
    fallback: {
      answered_by: 'fallback',
      message: '문의가 담당자에게 접수되었습니다. 확인 후 순차적으로 답변드리겠습니다.',
      ticket_id: 'TCK-20260813-0142'
    }
  };

  /* ---------- 유틸 ---------- */
  function tpl(id) { return $($('#' + id).html().trim()); }

  function findCategory(id) {
    var found = null;
    $.each(CATEGORY_GROUPS, function (i, g) {
      $.each(g.categories, function (j, c) {
        if (c.id === id) { found = { cat: c, group: g }; return false; }
      });
      return found ? false : true;
    });
    return found;
  }

  function scrollToEnd() {
    $list.stop().animate({ scrollTop: $list[0].scrollHeight }, 240);
  }

  function append($el) { $inner.append($el); scrollToEnd(); return $el; }

  function setWaiting(on) {
    waiting = on;
    $compose.toggleClass('is_waiting', on);
    $input.prop('disabled', on);
    $send.prop('disabled', on);
    $triggerMain.prop('disabled', on);
    $trigger.find('.chat_cat_clear').prop('disabled', on);
    $qbtn.prop('disabled', on);
    $questions.find('.chat_q_item').prop('disabled', on);
    $quickChips.find('.chat_cat_quick_chip').prop('disabled', on);
    if (on) { closePopover(); }
    if (!on) { $input.trigger('focus'); }
  }

  /* ==========================================================================
     팝오버 렌더 / 검색 / 아코디언
     ========================================================================== */
  function renderGroups() {
    $groups.empty();
    $.each(CATEGORY_GROUPS, function (i, g) {
      var $g = tpl('tpl_cat_group');
      $g.attr('data-group-id', g.group_id);
      $g.find('.chat_cat_group_head').attr('data-group-id', g.group_id);
      $g.find('[data-bind="group_label"]').text(g.group_label);
      $g.find('[data-bind="count"]').text('(' + g.categories.length + ')');
      var $ul = $g.find('.chat_cat_list');
      $.each(g.categories, function (j, c) {
        var $it = tpl('tpl_cat_item');
        $it.attr({ 'data-category-id': c.id, 'data-category-label': c.label, 'data-group-id': g.group_id });
        $it.find('[data-bind="label"]').text(c.label);
        $ul.append($it);
      });
      $groups.append($g);
    });
    markSelectedItem();
  }

  function markSelectedItem() {
    $groups.find('.chat_cat_item')
      .removeClass('is_selected').attr('aria-selected', 'false')
      .filter('[data-category-id="' + selectedId + '"]')
      .addClass('is_selected').attr('aria-selected', 'true');
  }

  function setGroupOpen($head, open) {
    $head.toggleClass('is_open', open).attr('aria-expanded', open ? 'true' : 'false');
    $head.siblings('.chat_cat_list').toggleClass('is_open', open);
  }

  function collapseAll() {
    $groups.find('.chat_cat_group_head').each(function () { setGroupOpen($(this), false); });
  }

  function highlight($item, term) {
    var label = $item.attr('data-category-label') || '';
    var $t = $item.find('.chat_cat_item_label');
    if (!term) { $t.text(label); return; }
    var at = label.toLowerCase().indexOf(term.toLowerCase());
    if (at < 0) { $t.text(label); return; }
    $t.empty()
      .append(document.createTextNode(label.slice(0, at)))
      .append($('<mark></mark>').text(label.slice(at, at + term.length)))
      .append(document.createTextNode(label.slice(at + term.length)));
  }

  function filterList(term) {
    term = $.trim(term);
    var total = 0;
    $groups.find('.chat_cat_group').each(function () {
      var $g = $(this);
      var shown = 0;
      $g.find('.chat_cat_item').each(function () {
        var $it = $(this);
        var hit = !term || ($it.attr('data-category-label') || '').toLowerCase().indexOf(term.toLowerCase()) > -1;
        $it.toggle(hit);
        highlight($it, hit ? term : '');
        if (hit) { shown++; }
      });
      total += shown;
      $g.toggle(shown > 0);
      if (term) { setGroupOpen($g.find('.chat_cat_group_head'), shown > 0); }
    });
    $popover.toggleClass('is_empty', total === 0);
    focusIndex = -1;
    $groups.find('.chat_cat_item').removeClass('is_focus');
  }

  function openPopover() {
    if (waiting) { return; }
    $popover.addClass('is_open').attr('aria-hidden', 'false');
    $triggerMain.attr('aria-expanded', 'true');
    $search.val('');
    filterList('');
    collapseAll();
    if (selectedId) {
      var $sel = $groups.find('.chat_cat_item[data-category-id="' + selectedId + '"]');
      setGroupOpen($sel.closest('.chat_cat_group').find('.chat_cat_group_head'), true);
      var body = $('#chatCatGroups')[0];
      if ($sel.length) { body.scrollTop = Math.max(0, $sel.position().top - 60); }
    }
    $search.trigger('focus');
  }

  function closePopover() {
    $popover.removeClass('is_open').attr('aria-hidden', 'true');
    $triggerMain.attr('aria-expanded', 'false');
  }

  /* ==========================================================================
     선택 상태 / 추천 질문
     ========================================================================== */
  function renderQuestions(cat) {
    $questions.empty();
    $.each(cat.questions, function (i, q) {
      var $q = tpl('tpl_cat_question');
      $q.attr('data-question', q);
      $q.find('[data-bind="question"]').text(q);
      $q.prop('disabled', waiting);
      $questions.append($q);
    });
  }

  /* 펼침/접힘: scrollHeight 측정 후 inline max-height 지정 (전환 180ms) */
  function setQuestionsOpen(open) {
    $questions.toggleClass('is_open', open).attr('aria-hidden', open ? 'false' : 'true');
    $qbtn.toggleClass('is_open', open).attr('aria-expanded', open ? 'true' : 'false');
    if (open) {
      var h = Math.min(160, $questions[0].scrollHeight);
      $questions.css({ maxHeight: h + 'px', opacity: 1 });
    } else {
      $questions.css({ maxHeight: 0, opacity: 0 });
    }
  }

  function selectCategory(id) {
    var hit = findCategory(id);
    if (!hit) { return; }
    var cat = hit.cat;
    selectedId = id;

    $trigger.addClass('is_active').attr({ 'data-category-id': cat.id, 'data-category-label': cat.label });
    $trigger.find('.chat_cat_trigger_label').text(cat.label).attr('title', cat.label);
    $popover.attr('data-selected-category', cat.id);
    markSelectedItem();

    $quickChips.find('.chat_cat_quick_chip')
      .removeClass('is_selected')
      .filter('[data-category-id="' + id + '"]').addClass('is_selected');

    var n = cat.questions.length;
    renderQuestions(cat);
    setQuestionsOpen(false);
    $qbtn.toggleClass('is_visible', n > 0).attr('data-question-count', n).find('.chat_cat_qbtn_num').text(n);
    $input.attr('placeholder', n > 0 ? '질문을 입력하세요' : cat.label + '에 대해 궁금한 점을 입력하세요');
  }

  function clearCategory() {
    selectedId = '';
    $trigger.removeClass('is_active').attr({ 'data-category-id': '', 'data-category-label': '' });
    $trigger.find('.chat_cat_trigger_label').text('주제 선택').removeAttr('title');
    $popover.attr('data-selected-category', '');
    $quickChips.find('.chat_cat_quick_chip').removeClass('is_selected');
    markSelectedItem();
    setQuestionsOpen(false);
    $questions.empty();
    $qbtn.removeClass('is_visible').attr('data-question-count', 0);
    $input.attr('placeholder', '질문을 입력하세요');
  }

  /* 인트로 빠른 선택 칩 */
  function renderQuickChips() {
    $quickChips.empty();
    $.each(QUICK_CATEGORY_IDS.slice(0, 6), function (i, id) {
      var hit = findCategory(id);
      if (!hit) { return; }
      var $c = tpl('tpl_cat_quick_chip');
      $c.attr({ 'data-category-id': hit.cat.id, 'data-category-label': hit.cat.label, title: hit.cat.label });
      $c.find('[data-bind="label"]').text(hit.cat.label);
      $quickChips.append($c);
    });
  }

  /* ==========================================================================
     메시지 렌더
     ========================================================================== */
  function renderUser(text, categoryLabel) {
    var $m = tpl('tpl_user');
    $m.find('[data-bind="question"]').text(text);
    var $cat = $m.find('.chat_msg_cat');
    if (categoryLabel) { $cat.text(categoryLabel); } else { $cat.remove(); }
    return append($m);
  }

  function renderSources($wrap, docs) {
    if (!docs || !docs.length) { $wrap.remove(); return; }
    $.each(docs, function (i, doc) {
      var $b = tpl('tpl_src');
      $b.find('.chat_src_title').text(doc.title);
      if (doc.url_or_ref) {
        $b.attr('href', doc.url_or_ref).attr('data-ref', doc.url_or_ref);
      } else {
        $b = $('<span class="chat_src chat_src_plain"></span>').append($b.contents());
      }
      $b.attr('data-title', doc.title);
      $wrap.append($b);
    });
  }

  function renderBot(res) {
    var $m = tpl('tpl_bot');
    $m.attr('data-answered-by', res.answered_by).attr('data-confidence', res.confidence);
    $m.find('[data-bind="answer"]').text(res.answer);
    renderSources($m.find('[data-bind="source_docs"]'), res.source_docs);
    return append($m);
  }

  function renderFallback(res) {
    var $m = tpl('tpl_fallback');
    $m.find('[data-bind="message"]').text(res.message);
    $m.find('[data-bind="ticket_id"]').text('접수번호 ' + res.ticket_id);
    return append($m);
  }

  function renderTyping() { return append(tpl('tpl_typing')); }

  function renderError(question) {
    var $m = tpl('tpl_error');
    $m.find('[data-retry]').attr('data-question', question);
    return append($m);
  }

  /* ---------- 전송 ---------- */
  function ask(text) {
    if (waiting) { return; }
    text = $.trim(text);
    if (!text) { return; }

    var hit = findCategory(selectedId);
    lastQuestion = text;
    $input.val('');
    closePopover();
    setQuestionsOpen(false);
    $('#chatIntro').hide();
    renderUser(text, hit ? hit.cat.label : '');
    setWaiting(true);

    var $typing = renderTyping();
    askApi(text, selectedId, function (res) {
      $typing.remove();
      if (!res) { renderError(text); }
      else if (res.answered_by === 'fallback') { renderFallback(res); }
      else { renderBot(res); }
      setWaiting(false);            /* 카테고리 선택은 유지 */
    });
  }

  /* 개발 연동 지점 ------------------------------------------------------- */
  function askApi(question, categoryId, done) {
    // 실제 구현 예시:
    // $.ajax({ url: '/ask', type: 'POST', contentType: 'application/json',
    //   data: JSON.stringify({ question: question, category_id: categoryId || null }) })
    //   .done(function (res) { done(res); })
    //   .fail(function () { done(null); });
    var pick = /안 보여|안보여|오류|실패/.test(question) ? 'fallback'
             : /그룹|스펙/.test(question) ? 'cache' : 'rag';
    setTimeout(function () { done(DUMMY[pick]); }, 1600);
  }
  /* --------------------------------------------------------------------- */

  /* ==========================================================================
     이벤트
     ========================================================================== */
  $('#chatForm').on('submit', function (e) {
    e.preventDefault();
    ask($input.val());
  });

  $triggerMain.on('click', function () {
    if ($popover.hasClass('is_open')) { closePopover(); } else { openPopover(); }
  });

  $trigger.on('click', '[data-category-clear]', function (e) {
    e.stopPropagation();            /* 트리거 열림과 분리 */
    if (waiting) { return; }
    clearCategory();
  });

  $('.chat_cat_more').on('click', function () { openPopover(); });

  $popover.on('click', '[data-popover-close]', closePopover);

  $groups.on('click', '.chat_cat_group_head', function () {
    var $h = $(this);
    setGroupOpen($h, !$h.hasClass('is_open'));
  });

  $groups.on('click', '.chat_cat_item', function () {
    selectCategory($(this).attr('data-category-id'));
    closePopover();
    $input.trigger('focus');
  });

  $search.on('input', function () { filterList($(this).val()); });

  /* 키보드: ↓로 목록 진입, ↑/↓ 이동, Enter 선택, ESC 닫기 */
  $popover.on('keydown', function (e) {
    var $items = $groups.find('.chat_cat_item:visible');
    if (e.key === 'Escape') { closePopover(); $triggerMain.trigger('focus'); return; }
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp' && e.key !== 'Enter') { return; }
    if (e.key === 'Enter') {
      if (focusIndex > -1 && $items.eq(focusIndex).length) {
        e.preventDefault();
        $items.eq(focusIndex).trigger('click');
      }
      return;
    }
    e.preventDefault();
    if (!$items.length) { return; }
    focusIndex = e.key === 'ArrowDown'
      ? Math.min(focusIndex + 1, $items.length - 1)
      : Math.max(focusIndex - 1, 0);
    $items.removeClass('is_focus');
    var $t = $items.eq(focusIndex).addClass('is_focus');
    var body = $('#chatCatGroups')[0];
    var top = $t.position().top;
    if (top < 0) { body.scrollTop += top - 8; }
    else if (top + $t.outerHeight() > body.clientHeight) { body.scrollTop += top + $t.outerHeight() - body.clientHeight + 8; }
  });

  $qbtn.on('click', function () {
    setQuestionsOpen(!$questions.hasClass('is_open'));
  });

  $questions.on('click', '.chat_q_item', function () {
    ask($(this).attr('data-question'));
  });

  $quickChips.on('click', '.chat_cat_quick_chip', function () {
    if (waiting) { return; }
    selectCategory($(this).attr('data-category-id'));
  });

  /* 팝오버 바깥 클릭 / 입력창 클릭 시 닫힘 */
  $(document).on('mousedown', function (e) {
    if (!$popover.hasClass('is_open')) { return; }
    if ($(e.target).closest('#chatCatPopover, .chat_cat_trigger, .chat_cat_more').length) { return; }
    closePopover();
  });
  $input.on('focus', closePopover);

  $inner.on('click', '[data-retry]', function () {
    var q = $(this).attr('data-question') || lastQuestion;
    $(this).closest('.chat_msg').remove();
    if (!q) { return; }
    setWaiting(true);
    var $typing = renderTyping();
    askApi(q, selectedId, function (res) {
      $typing.remove();
      if (!res) { renderError(q); } else if (res.answered_by === 'fallback') { renderFallback(res); } else { renderBot(res); }
      setWaiting(false);
    });
  });

  /* 출처 배지 → 모달 */
  $inner.on('click', '.chat_src', function (e) {
    e.preventDefault();
    var $b = $(this);
    var ref = $b.attr('data-ref') || '';
    var $modal = $('#srcModal');
    $modal.find('[data-bind="source_docs[].title"]').text($b.attr('data-title') || '출처 문서');
    $modal.find('[data-bind="source_docs[].url_or_ref"]').text(ref || '참조 경로 없음');
    $modal.find('[data-bind="answered_by"]').text($b.closest('.chat_msg').attr('data-answered-by') || '—');
    $('#srcModalGo').attr('href', ref || '#').toggle(!!ref);
    $modal.addClass('is_open');
  });

  $('#srcModal').on('click', function (e) {
    if (e.target === this || $(e.target).closest('[data-modal-close]').length) {
      $(this).removeClass('is_open');
    }
  });
  $(document).on('keydown', function (e) {
    if (e.key === 'Escape') { $('#srcModal').removeClass('is_open'); }
  });

  $('#btnReset').on('click', function () {
    $inner.find('.chat_msg').remove();
    clearCategory();
    closePopover();
    $('#chatIntro').show();
    setWaiting(false);
  });

  /* ---------- 퍼블 확인용 상태 목업 바 (개발 이식 시 삭제) ---------- */
  $('[data-dev-only]').on('click', '[data-mock]', function () {
    var kind = $(this).attr('data-mock');
    if (kind === 'disabled') { setWaiting(!waiting); return; }
    if (kind === 'category') {
      if (selectedId) { clearCategory(); } else { selectCategory('api_reg_flow'); }
      return;
    }
    if (kind === 'popover') {
      if ($popover.hasClass('is_open')) { closePopover(); } else { openPopover(); }
      return;
    }
    if (kind === 'search_none') {
      openPopover();
      $search.val('없는주제zz');
      filterList('없는주제zz');
      return;
    }
    if (kind === 'typing') { renderTyping(); return; }
    if (kind === 'error') { renderError('API 등록은 어떻게 하나요?'); return; }
    $('#chatIntro').hide();
    if (kind === 'fallback') {
      renderUser('사내망에서만 되는 API도 등록할 수 있나요?', '기타 / 직접 입력');
      renderFallback(DUMMY.fallback);
      return;
    }
    if (kind === 'cache') {
      renderUser('API 그룹(스펙)은 무엇인가요?', 'API 그룹(스펙) 개념');
      renderBot(DUMMY.cache);
    } else {
      renderUser('API 등록은 어떻게 하나요?', 'API 등록 절차');
      renderBot(DUMMY.rag);
    }
  });

  /* ---------- 초기화 ---------- */
  renderGroups();
  renderQuickChips();
  $input.trigger('focus');

})(jQuery);
