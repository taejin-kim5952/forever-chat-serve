/* ==========================================================================
   openapi-chat 관리자 화면 (퍼블 목업 스크립트, jQuery)
   실제 API 연동은 개발 쪽에서 처리합니다.
   → api() 헬퍼의 setTimeout 더미 응답만 $.ajax 로 교체하면 됩니다.
   ========================================================================== */
(function ($) {
  'use strict';

  /* ==========================================================================
     더미 데이터 (개발 단계에서 API 응답으로 교체)
     ========================================================================== */
  var DOCS = [
    { doc_id: 'api-등록.md', title: 'API 등록 가이드', category: 'API 등록', url: '/portal/guide/api-reg', updated_at: '2026-08-11', chunks: 24 },
    { doc_id: 'api-등록-필드설명.md', title: 'API 등록 항목 설명', category: 'API 등록', url: '/portal/guide/api-reg-field', updated_at: '2026-08-11', chunks: 31 },
    { doc_id: 'api-등록-오류.md', title: 'API 등록 오류 대응', category: 'API 등록', url: '/portal/guide/api-reg-error', updated_at: '2026-08-04', chunks: 12 },
    { doc_id: 'api-빠른등록.md', title: '빠른 API 등록', category: 'API 등록', url: '/portal/guide/quick-api-reg', updated_at: '2026-07-29', chunks: 9 },
    { doc_id: 'api-배포.md', title: 'API 배포와 반영', category: 'API 등록', url: '/portal/guide/api-deploy', updated_at: '2026-07-22', chunks: 14 },
    { doc_id: 'spc-등록.md', title: 'API 그룹(스펙) 등록', category: 'API 그룹(스펙)', url: '/portal/guide/spc-reg', updated_at: '2026-08-08', chunks: 27 },
    { doc_id: 'spc-oas일괄등록.md', title: 'OAS/Swagger 일괄 등록', category: 'API 그룹(스펙)', url: '/portal/guide/spc-oas', updated_at: '2026-08-01', chunks: 18 },
    { doc_id: 'spc-문서노출.md', title: '포털 문서 노출 설정', category: 'API 그룹(스펙)', url: '/portal/guide/spc-doc', updated_at: '2026-07-18', chunks: 11 },
    { doc_id: '템플릿-관리.md', title: '템플릿 관리', category: '템플릿 관리', url: '/portal/guide/template', updated_at: '2026-08-09', chunks: 22 },
    { doc_id: '템플릿-변수.md', title: '템플릿 치환 변수', category: '템플릿 관리', url: '/portal/guide/template-var', updated_at: '2026-07-30', chunks: 8 },
    { doc_id: '권한-그룹.md', title: '권한그룹과 역할', category: '권한 / 계정', url: '/portal/guide/auth-group', updated_at: '2026-08-06', chunks: 16 },
    { doc_id: 'apikey-발급.md', title: 'API Key 발급·회수', category: '권한 / 계정', url: '/portal/guide/api-key', updated_at: '2026-08-02', chunks: 13 },
    { doc_id: '포털-일반.md', title: '포털 사용 일반', category: '기타', url: '/portal/guide/common', updated_at: '2026-06-27', chunks: 7 },
    { doc_id: '용어-정리.md', title: '용어 정리', category: '기타', url: '/portal/guide/glossary', updated_at: '2026-06-27', chunks: 6 }
  ];

  /* 카테고리: 2단계(대분류 group → 카테고리). 관리자용 필드 포함
     { id, label, group_id, doc_ids: [], enabled, sort, questions: [] }
     ※ 개수 부하 확인용 더미 — 5 대분류 / 48 카테고리 */
  var CATEGORY_GROUPS = [
    { group_id: 'api', group_label: 'API 등록', enabled: true, sort: 0, categories: [
      { id: 'api_reg_flow', label: 'API 등록 절차', doc_ids: ['api-등록.md'], enabled: true, sort: 0, questions: ['API 등록은 어떻게 하나요?', 'API 등록 전에 그룹을 먼저 만들어야 하나요?', '등록 후 반영까지 얼마나 걸리나요?'] },
      { id: 'api_reg_field', label: 'API 등록 항목 설명', doc_ids: ['api-등록-필드설명.md'], enabled: true, sort: 1, questions: ['권한그룹은 무엇을 선택해야 하나요?', 'Path와 Method는 어떻게 입력하나요?', '필수 입력 항목은 무엇인가요?', '서비스와 그룹의 차이는 무엇인가요?'] },
      { id: 'api_reg_err', label: 'API 등록 오류', doc_ids: ['api-등록-오류.md'], enabled: true, sort: 2, questions: ['등록한 API가 목록에 안 보여요', '저장 시 중복 경로 오류가 납니다'] },
      { id: 'api_quick', label: '빠른 API 등록', doc_ids: ['api-빠른등록.md'], enabled: true, sort: 3, questions: ['빠른 등록과 일반 등록의 차이는?', '빠른 등록에서 인증 설정을 바꿀 수 있나요?'] },
      { id: 'api_edit', label: 'API 수정·삭제', doc_ids: ['api-등록.md'], enabled: true, sort: 4, questions: ['등록한 API를 수정·삭제하려면?', '운영 중인 API를 수정하면 바로 반영되나요?'] },
      { id: 'api_deploy', label: 'API 배포', doc_ids: ['api-배포.md'], enabled: true, sort: 5, questions: ['배포 버튼이 활성화되지 않습니다', '배포 이력은 어디서 보나요?'] },
      { id: 'api_endpoint', label: '엔드포인트 설정', doc_ids: ['api-등록-필드설명.md'], enabled: true, sort: 6, questions: ['Base URL은 어떤 형식으로 입력하나요?', '포트가 다른 서버도 등록할 수 있나요?'] },
      { id: 'api_auth', label: '인증 방식 설정', doc_ids: ['api-등록-필드설명.md', 'apikey-발급.md'], enabled: true, sort: 7, questions: ['API Key와 OAuth 2.0 중 무엇을 쓰나요?', 'OAuth 스코프는 어디서 정의하나요?'] },
      { id: 'api_param', label: '파라미터 정의', doc_ids: ['api-등록-필드설명.md'], enabled: true, sort: 8, questions: ['Query와 Path 파라미터를 함께 쓸 수 있나요?'] },
      { id: 'api_header', label: '헤더 / CORS', doc_ids: ['api-등록-필드설명.md'], enabled: false, sort: 9, questions: ['커스텀 헤더를 추가할 수 있나요?', 'CORS 허용 도메인은 어디서 설정하나요?'] },
      { id: 'api_version', label: '버전 관리', doc_ids: ['api-등록.md'], enabled: true, sort: 10, questions: ['v1, v2를 동시에 운영할 수 있나요?'] },
      { id: 'api_status', label: '상태 / 승인', doc_ids: ['api-배포.md'], enabled: true, sort: 11, questions: ["'작성중' 상태는 무슨 의미인가요?", '승인 요청은 누가 처리하나요?'] },
      { id: 'api_test', label: '테스트 호출', doc_ids: ['api-등록.md'], enabled: true, sort: 12, questions: ['등록 화면에서 바로 호출 테스트가 되나요?'] },
      { id: 'api_limit', label: '트래픽 / 쿼터', doc_ids: [], enabled: false, sort: 13, questions: [] }
    ]},
    { group_id: 'spc', group_label: 'API 그룹(스펙)', enabled: true, sort: 1, categories: [
      { id: 'spc_concept', label: 'API 그룹(스펙) 개념', doc_ids: ['spc-등록.md', '용어-정리.md'], enabled: true, sort: 0, questions: ['API 그룹(스펙)은 무엇인가요?', '그룹 없이 API만 등록해도 되나요?'] },
      { id: 'spc_create', label: '그룹 생성 절차', doc_ids: ['spc-등록.md'], enabled: true, sort: 1, questions: ['그룹 등록 시 필수 항목은?', '그룹 ID 규칙이 있나요?'] },
      { id: 'spc_oas', label: 'OAS / Swagger 일괄 등록', doc_ids: ['spc-oas일괄등록.md'], enabled: true, sort: 2, questions: ['Swagger YAML로 한 번에 등록할 수 있나요?', 'OAS 3.0만 지원하나요?'] },
      { id: 'spc_import_err', label: '일괄 등록 오류', doc_ids: ['spc-oas일괄등록.md'], enabled: true, sort: 3, questions: ['YAML 파싱 오류가 납니다', '일부 API만 등록되고 나머지가 누락됩니다'] },
      { id: 'spc_delete', label: '그룹 삭제', doc_ids: ['spc-등록.md'], enabled: true, sort: 4, questions: ['그룹을 삭제하면 하위 API는 어떻게 되나요?'] },
      { id: 'spc_move', label: 'API 소속 변경', doc_ids: ['spc-등록.md'], enabled: true, sort: 5, questions: ['다른 그룹으로 API를 옮길 수 있나요?'] },
      { id: 'spc_doc', label: '포털 문서 노출', doc_ids: ['spc-문서노출.md'], enabled: true, sort: 6, questions: ['그룹 문서가 포털에 안 보입니다', '문서 설명 문구는 어디서 수정하나요?'] },
      { id: 'spc_perm', label: '그룹 권한', doc_ids: ['권한-그룹.md'], enabled: true, sort: 7, questions: ['그룹별로 접근 권한을 나눌 수 있나요?'] },
      { id: 'spc_tag', label: '태그 / 분류', doc_ids: ['spc-등록.md'], enabled: false, sort: 8, questions: [] },
      { id: 'spc_server', label: '서버 정보(servers)', doc_ids: ['spc-oas일괄등록.md'], enabled: true, sort: 9, questions: ['운영·개발 서버를 함께 표기할 수 있나요?'] },
      { id: 'spc_schema', label: '스키마 / 모델', doc_ids: ['spc-oas일괄등록.md'], enabled: true, sort: 10, questions: ['공통 모델을 재사용할 수 있나요?'] },
      { id: 'spc_export', label: '스펙 내보내기', doc_ids: ['spc-문서노출.md'], enabled: true, sort: 11, questions: ['등록된 그룹을 YAML로 내려받을 수 있나요?'] }
    ]},
    { group_id: 'tmplt', group_label: '템플릿 관리', enabled: true, sort: 2, categories: [
      { id: 'tmplt_concept', label: '템플릿 개념', doc_ids: ['템플릿-관리.md'], enabled: true, sort: 0, questions: ['템플릿은 어디서 만드나요?', '템플릿과 그룹은 어떻게 다른가요?'] },
      { id: 'tmplt_create', label: '템플릿 등록', doc_ids: ['템플릿-관리.md'], enabled: true, sort: 1, questions: ['템플릿 등록 시 필수 항목은?'] },
      { id: 'tmplt_edit', label: '템플릿 수정', doc_ids: ['템플릿-관리.md'], enabled: true, sort: 2, questions: ['템플릿을 수정하려면?', '수정하면 기존 API에도 반영되나요?'] },
      { id: 'tmplt_apply', label: '템플릿으로 API 등록', doc_ids: ['템플릿-관리.md', 'api-등록.md'], enabled: true, sort: 3, questions: ['템플릿으로 API를 등록하는 방법은?', '템플릿 값 일부만 바꿔 등록할 수 있나요?'] },
      { id: 'tmplt_load', label: '템플릿 불러오기', doc_ids: ['템플릿-관리.md'], enabled: true, sort: 4, questions: ['불러오기 목록에 템플릿이 안 보입니다'] },
      { id: 'tmplt_share', label: '템플릿 공유', doc_ids: ['템플릿-관리.md'], enabled: true, sort: 5, questions: ['다른 부서와 템플릿을 공유할 수 있나요?'] },
      { id: 'tmplt_delete', label: '템플릿 삭제', doc_ids: ['템플릿-관리.md'], enabled: true, sort: 6, questions: ['사용 중인 템플릿을 삭제할 수 있나요?'] },
      { id: 'tmplt_var', label: '치환 변수', doc_ids: ['템플릿-변수.md'], enabled: true, sort: 7, questions: ['템플릿에 변수를 넣을 수 있나요?'] },
      { id: 'tmplt_ver', label: '템플릿 버전', doc_ids: ['템플릿-관리.md'], enabled: false, sort: 8, questions: ['이전 버전 템플릿으로 되돌릴 수 있나요?'] },
      { id: 'tmplt_default', label: '기본 템플릿 지정', doc_ids: ['템플릿-관리.md'], enabled: true, sort: 9, questions: ['부서 기본 템플릿을 지정할 수 있나요?'] },
      { id: 'tmplt_err', label: '템플릿 적용 오류', doc_ids: ['템플릿-관리.md'], enabled: true, sort: 10, questions: ['템플릿 적용 후 저장이 실패합니다'] }
    ]},
    { group_id: 'auth', group_label: '권한 / 계정', enabled: true, sort: 3, categories: [
      { id: 'auth_group', label: '권한그룹 설정', doc_ids: ['권한-그룹.md'], enabled: true, sort: 0, questions: ['권한그룹은 무엇을 선택해야 하나요?', '권한그룹을 새로 만들 수 있나요?'] },
      { id: 'auth_role', label: '역할(Role) 구분', doc_ids: ['권한-그룹.md'], enabled: true, sort: 1, questions: ['관리자와 등록자의 차이는?'] },
      { id: 'auth_apply', label: '권한 신청', doc_ids: ['권한-그룹.md'], enabled: true, sort: 2, questions: ['등록 권한은 어디서 신청하나요?'] },
      { id: 'auth_key', label: 'API Key 발급', doc_ids: ['apikey-발급.md'], enabled: true, sort: 3, questions: ['API Key는 어디서 발급하나요?', '발급한 Key를 재발급할 수 있나요?'] },
      { id: 'auth_expire', label: '만료 / 회수', doc_ids: ['apikey-발급.md'], enabled: true, sort: 4, questions: ['Key 만료 기간을 늘릴 수 있나요?'] },
      { id: 'auth_ip', label: 'IP 접근 제어', doc_ids: [], enabled: false, sort: 5, questions: [] },
      { id: 'auth_sso', label: 'SSO 로그인', doc_ids: ['포털-일반.md'], enabled: true, sort: 6, questions: ['SSO 로그인이 실패합니다'] },
      { id: 'auth_dept', label: '부서 / 조직 정보', doc_ids: ['포털-일반.md'], enabled: true, sort: 7, questions: ['소속 부서가 잘못 표시됩니다'] }
    ]},
    { group_id: 'etc', group_label: '기타', enabled: true, sort: 4, categories: [
      { id: 'etc_free', label: '기타 / 직접 입력', doc_ids: [], enabled: true, sort: 0, questions: [] },
      { id: 'etc_portal', label: '포털 사용 일반', doc_ids: ['포털-일반.md'], enabled: true, sort: 1, questions: ['포털 공지사항은 어디서 보나요?'] },
      { id: 'etc_contact', label: '담당자 문의', doc_ids: ['포털-일반.md'], enabled: true, sort: 2, questions: ['담당자에게 직접 문의하려면?'] }
    ]}
  ];

  var DEFAULT_THRESHOLDS = { thFloor: 0.35, thSoftFloor: 0.20, thCache: 0.95, thIntent: 0.60, thTopK: 5 };
  var DEFAULT_GEN = { thNumCtx: 8192, thNumPredict: 1024 };
  /* 챗봇 인트로 '자주 찾는 주제' — 서버의 quick_category_ids */
  var quickCategoryIds = ['api_reg_flow', 'api_reg_field', 'spc_create', 'tmplt_edit'];
  var QUICK_MAX = 6;

  /* ==========================================================================
     유틸
     ========================================================================== */
  function tpl(id) { return $($('#' + id).html().trim()); }

  /* 개발 연동 지점: 실제로는 $.ajax 로 교체 */
  function api(action, payload, done) {
    setTimeout(function () { done({ ok: true, action: action, payload: payload }); }, 700);
  }

  function setState($el, kind, text) {
    $el.removeClass('is_busy is_ok is_err').empty();
    if (!kind) { return; }
    $el.addClass('is_' + kind);
    if (kind === 'busy') { $el.append('<span class="admin_spinner"></span>'); }
    else if (kind === 'ok') { $el.append('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>'); }
    else { $el.append('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg>'); }
    $el.append($('<span></span>').text(text || ''));
  }

  function toast(kind, message) {
    var $t = tpl('tpl_toast').addClass('is_' + kind);
    if (kind === 'err') {
      $t.find('svg').replaceWith('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/><path d="M12 9v4M12 17h.01"/></svg>');
    }
    $t.find('[data-bind="message"]').text(message);
    $('#adminToasts').append($t);
    setTimeout(function () {
      $t.addClass('is_out');
      setTimeout(function () { $t.remove(); }, 220);
    }, 3000);
  }

  function openModal(id) { $('#' + id).addClass('is_open'); }
  function closeModal($m) { $m.removeClass('is_open'); }

  /* 확인 모달 — confirm() 대체 */
  var confirmAction = null;
  function askConfirm(opt, onOk) {
    $('#confirmTitle').text(opt.title || '삭제할까요?');
    $('#confirmMsg').text(opt.message || '');
    $('#confirmDesc').text(opt.desc || '');
    $('#confirmOkBtn').text(opt.okLabel || '삭제');
    confirmAction = onOk;
    openModal('confirmModal');
  }

  function highlight($el, label, term) {
    if (!term) { $el.text(label); return; }
    var at = label.toLowerCase().indexOf(term.toLowerCase());
    if (at < 0) { $el.text(label); return; }
    $el.empty()
      .append(document.createTextNode(label.slice(0, at)))
      .append($('<mark></mark>').text(label.slice(at, at + term.length)))
      .append(document.createTextNode(label.slice(at + term.length)));
  }

  /* ==========================================================================
     탭
     ========================================================================== */
  $('.admin_tab').on('click', function () {
    var tab = $(this).attr('data-tab');
    $('.admin_tab').removeClass('is_active').attr('aria-selected', 'false');
    $(this).addClass('is_active').attr('aria-selected', 'true');
    $('.admin_panel').removeClass('is_active');
    $('#panel_' + tab).addClass('is_active');
  });

  /* ==========================================================================
     탭 ① 시스템 프롬프트
     ========================================================================== */
  $('#spPrompt').on('input', function () { $('#spCard').addClass('is_dirty'); });

  $('#spSave').on('click', function () {
    setState($('#spState'), 'busy', '저장 중…');
    api('savePrompt', { prompt: $('#spPrompt').val() }, function () {
      setState($('#spState'), 'ok', '저장되었습니다');
      $('#spCard').removeClass('is_dirty');
      toast('ok', '시스템 프롬프트를 저장했습니다.');
    });
  });

  /* ==========================================================================
     탭 ② RAG 문서 관리
     ========================================================================== */
  function renderDocs(term) {
    term = $.trim(term || '');
    var $tb = $('#docTableBody').empty();
    var shown = 0;
    $.each(DOCS, function (i, d) {
      if (term) {
        var hay = (d.title + ' ' + d.doc_id).toLowerCase();
        if (hay.indexOf(term.toLowerCase()) < 0) { return; }
      }
      var $r = tpl('tpl_doc_row');
      $r.attr('data-doc-id', d.doc_id);
      $r.find('[data-bind="doc_id"]').text(d.doc_id);
      $r.find('[data-bind="title"]').text(d.title);
      $r.find('[data-bind="category"]').text(d.category);
      $r.find('[data-bind="url"]').text(d.url).attr('href', d.url);
      $r.find('[data-bind="updated_at"]').text(d.updated_at);
      $r.find('[data-bind="chunks"]').text(d.chunks);
      $tb.append($r);
      shown++;
    });
    $('#docTableWrap').toggle(shown > 0);
    $('#docEmpty').prop('hidden', shown > 0);
    if (shown === 0 && term) {
      $('#docEmpty').find('b').text('검색 결과가 없습니다');
      $('#docEmpty').find('span').last().text('다른 제목이나 문서 ID로 검색해 보세요.');
    } else {
      $('#docEmpty').find('b').text('등록된 문서가 없습니다');
      $('#docEmpty').find('span').last().text('[새 문서] 버튼으로 첫 문서를 등록해 주세요.');
    }
    $('#docSearchWrap').toggleClass('is_noresult', shown === 0 && !!term);
  }

  function openDocEditor(docId) {
    var isNew = !docId;
    $('#docEditorTitle').text(isNew ? '새 문서' : '문서 수정');
    $('#docId').val(docId || '').prop('readonly', !isNew);
    $('#docContent').val(isNew ? '' : '# ' + docId + '\n\n(문서 본문 더미 — 실제 내용은 서버에서 로드합니다.)\n\n## 등록 절차\n1. 좌측 메뉴 > API Manager > API 등록\n2. 필수 항목 입력 후 저장\n3. 상단 [배포]로 게이트웨이 반영');
    setState($('#docState'), null);
    openModal('docEditor');
    $('#docContent').trigger('focus');
  }

  $('#docNewBtn').on('click', function () { openDocEditor(null); });
  $('#docCancelBtn').on('click', function () { closeModal($('#docEditor')); });

  $('#docSaveBtn').on('click', function () {
    if (!$.trim($('#docId').val())) {
      setState($('#docState'), 'err', '문서 ID를 입력해 주세요');
      return;
    }
    setState($('#docState'), 'busy', '저장 및 재색인 중…');
    api('saveDoc', { doc_id: $('#docId').val() }, function () {
      setState($('#docState'), 'ok', '저장되었습니다');
      toast('ok', '문서를 저장하고 재색인했습니다.');
      setTimeout(function () { closeModal($('#docEditor')); }, 500);
    });
  });

  $('#docTableBody').on('click', '[data-doc-edit]', function () {
    openDocEditor($(this).closest('tr').attr('data-doc-id'));
  });

  $('#docTableBody').on('click', '[data-doc-delete]', function () {
    var id = $(this).closest('tr').attr('data-doc-id');
    askConfirm({
      title: '문서를 삭제할까요?',
      message: id,
      desc: '삭제한 문서는 복구할 수 없고, 색인에서도 즉시 제거됩니다.'
    }, function () {
      DOCS = $.grep(DOCS, function (d) { return d.doc_id !== id; });
      renderDocs($('#docSearch').val());
      toast('ok', '문서를 삭제했습니다.');
    });
  });

  $('#docSearch').on('input', function () {
    $('#docSearchWrap').toggleClass('is_filled', !!$(this).val());
    renderDocs($(this).val());
  });

  /* ==========================================================================
     탭 ③ 질문 카테고리
     ========================================================================== */
  var selectedCatId = '';

  function findCat(id) {
    var found = null;
    $.each(CATEGORY_GROUPS, function (i, g) {
      $.each(g.categories, function (j, c) {
        if (c.id === id) { found = { cat: c, group: g }; return false; }
      });
      return found ? false : true;
    });
    return found;
  }

  function renderTree(term) {
    term = $.trim(term || '');
    var $tree = $('#catTree').empty();
    var total = 0;
    $.each(CATEGORY_GROUPS, function (i, g) {
      var $g = tpl('tpl_cat_group').attr('data-group-id', g.group_id);
      $g.find('[data-bind="group_label"]').text(g.group_label);
      $g.find('[data-bind="count"]').text('(' + g.categories.length + ')');
      var $list = $g.find('.admin_cat_list');
      var shown = 0;
      $.each(g.categories, function (j, c) {
        if (term && c.label.toLowerCase().indexOf(term.toLowerCase()) < 0) { return; }
        var $it = tpl('tpl_cat_item');
        $it.find('.admin_cat_item').attr({ 'data-category-id': c.id, 'data-group-id': g.group_id })
          .toggleClass('is_off', !c.enabled)
          .toggleClass('is_selected', c.id === selectedCatId);
        highlight($it.find('[data-bind="label"]'), c.label, term);
        $it.find('[data-bind="enabled"]').prop('hidden', c.enabled);
        $list.append($it);
        shown++;
      });
      if (term && shown === 0) { return; }
      var open = !!term || (selectedCatId && findCat(selectedCatId) && findCat(selectedCatId).group.group_id === g.group_id);
      $g.toggleClass('is_open', !!open);
      $g.find('.admin_cat_group_head').attr('aria-expanded', open ? 'true' : 'false');
      total += shown;
      $tree.append($g);
    });
    $('#catTree').toggle(total > 0);
    $('#catTreeEmpty').prop('hidden', total > 0);
  }

  function renderDocSelect() {
    var $sel = $('#catDocs').empty().append('<option value="">문서를 선택해 추가</option>');
    $.each(DOCS, function (i, d) {
      $sel.append($('<option></option>').val(d.doc_id).text(d.doc_id + ' — ' + d.title));
    });
  }

  function renderDocTags(docIds) {
    var $wrap = $('#catDocTags').empty();
    $.each(docIds, function (i, id) {
      var $t = tpl('tpl_doc_tag').attr('data-doc-id', id);
      $t.find('[data-bind="doc_id"]').text(id);
      $wrap.append($t);
    });
  }

  function renderQuestions(questions) {
    var $wrap = $('#catQuestions').empty();
    if (!questions.length) {
      $wrap.append('<p class="admin_q_empty">추천 질문이 없습니다. 사용자는 직접 입력하게 됩니다.</p>');
    } else {
      $.each(questions, function (i, q) {
        var $r = tpl('tpl_cat_q').attr('data-index', i);
        $r.find('[data-bind="question"]').val(q);
        $wrap.append($r);
      });
    }
    $('#catQCount').text('(' + questions.length + ')');
  }

  function renderGroupSelect(groupId) {
    var $sel = $('#catGroupSel').empty();
    $.each(CATEGORY_GROUPS, function (i, g) {
      $sel.append($('<option></option>').val(g.group_id).text(g.group_label));
    });
    $sel.val(groupId);
  }

  function selectCategory(id) {
    var hit = findCat(id);
    if (!hit) { return; }
    selectedCatId = id;
    var c = hit.cat;

    $('#catDetail').attr('data-category-id', c.id);
    $('#catDetailEmpty').prop('hidden', true);
    $('#catDetailForm').prop('hidden', false);
    $('#catDetailFoot').prop('hidden', false);

    renderGroupSelect(hit.group.group_id);
    $('#catLabel').val(c.label);
    $('#catId').val(c.id).prop('readonly', true);
    $('#catEnabled').prop('checked', c.enabled)
      .siblings('.admin_switch_text').text(c.enabled ? '사용' : '미사용');
    renderDocSelect();
    renderDocTags(c.doc_ids);
    renderQuestions(c.questions);
    setState($('#catState'), null);

    $('#catTree').find('.admin_cat_item').removeClass('is_selected')
      .filter('[data-category-id="' + id + '"]').addClass('is_selected');
    var $g = $('#catTree').find('.admin_cat_group[data-group-id="' + hit.group.group_id + '"]');
    $g.addClass('is_open').find('.admin_cat_group_head').attr('aria-expanded', 'true');
  }

  function clearDetail() {
    selectedCatId = '';
    $('#catDetail').attr('data-category-id', '');
    $('#catDetailEmpty').prop('hidden', false);
    $('#catDetailForm').prop('hidden', true);
    $('#catDetailFoot').prop('hidden', true);
    $('#catTree').find('.admin_cat_item').removeClass('is_selected');
  }

  $('#catTree').on('click', '.admin_cat_group_head', function () {
    var $g = $(this).closest('.admin_cat_group');
    var open = !$g.hasClass('is_open');
    $g.toggleClass('is_open', open);
    $(this).attr('aria-expanded', open ? 'true' : 'false');
  });

  $('#catTree').on('click', '.admin_cat_item', function () {
    selectCategory($(this).attr('data-category-id'));
  });

  $('#catSearch').on('input', function () {
    $('#catSearchWrap').toggleClass('is_filled', !!$(this).val());
    renderTree($(this).val());
  });

  $('#catEnabled').on('change', function () {
    $(this).siblings('.admin_switch_text').text(this.checked ? '사용' : '미사용');
  });

  $('#catDocs').on('change', function () {
    var id = $(this).val();
    if (!id) { return; }
    if (!$('#catDocTags').find('[data-doc-id="' + id + '"]').length) {
      var $t = tpl('tpl_doc_tag').attr('data-doc-id', id);
      $t.find('[data-bind="doc_id"]').text(id);
      $('#catDocTags').append($t);
    }
    $(this).val('');
  });

  $('#catDocTags').on('click', '[data-tag-remove]', function () {
    $(this).closest('.admin_tag').remove();
  });

  $('#catQAddBtn').on('click', function () {
    $('#catQuestions').find('.admin_q_empty').remove();
    var i = $('#catQuestions').find('.admin_cat_q').length;
    var $r = tpl('tpl_cat_q').attr('data-index', i);
    $('#catQuestions').append($r);
    $('#catQCount').text('(' + (i + 1) + ')');
    $r.find('input').trigger('focus');
  });

  $('#catQuestions').on('click', '[data-q-delete]', function () {
    $(this).closest('.admin_cat_q').remove();
    var rows = $('#catQuestions').find('.admin_cat_q');
    rows.each(function (i) { $(this).attr('data-index', i); });
    $('#catQCount').text('(' + rows.length + ')');
    if (!rows.length) {
      $('#catQuestions').append('<p class="admin_q_empty">추천 질문이 없습니다. 사용자는 직접 입력하게 됩니다.</p>');
    }
  });

  $('#catSaveBtn').on('click', function () {
    setState($('#catState'), 'busy', '저장 중…');
    var payload = {
      id: $('#catId').val(),
      label: $('#catLabel').val(),
      group_id: $('#catGroupSel').val(),
      doc_ids: $('#catDocTags').find('.admin_tag').map(function () { return $(this).attr('data-doc-id'); }).get(),
      enabled: $('#catEnabled').prop('checked'),
      questions: $('#catQuestions').find('.admin_cat_q input').map(function () { return $(this).val(); }).get()
    };
    api('saveCategory', payload, function () {
      var hit = findCat(payload.id);
      if (hit) {
        hit.cat.label = payload.label;
        hit.cat.doc_ids = payload.doc_ids;
        hit.cat.enabled = payload.enabled;
        hit.cat.questions = payload.questions;
      }
      setState($('#catState'), 'ok', '저장되었습니다');
      renderTree($('#catSearch').val());
      toast('ok', '카테고리를 저장했습니다.');
    });
  });

  $('#catCancelBtn').on('click', function () {
    if (selectedCatId) { selectCategory(selectedCatId); } else { clearDetail(); }
  });

  $('#catDeleteBtn').on('click', function () {
    var id = selectedCatId;
    var hit = findCat(id);
    if (!hit) { return; }
    askConfirm({
      title: '카테고리를 삭제할까요?',
      message: hit.cat.label,
      desc: '삭제하면 사용자 챗봇의 주제 목록에서 즉시 사라집니다. 추천 질문도 함께 삭제되고, 자주 찾는 주제에 포함되어 있으면 함께 제거됩니다.'
    }, function () {
      hit.group.categories = $.grep(hit.group.categories, function (c) { return c.id !== id; });
      quickDropCategory(id);
      clearDetail();
      renderTree($('#catSearch').val());
      toast('ok', '카테고리를 삭제했습니다.');
    });
  });

  /* 카테고리 신규 추가 — ID 입력 가능 상태 */
  $('#catAddBtn').on('click', function () {
    selectedCatId = '';
    $('#catDetailEmpty').prop('hidden', true);
    $('#catDetailForm').prop('hidden', false);
    $('#catDetailFoot').prop('hidden', false);
    $('#catDetail').attr('data-category-id', '');
    renderGroupSelect(CATEGORY_GROUPS[0].group_id);
    $('#catLabel').val('');
    $('#catId').val('').prop('readonly', false);
    $('#catEnabled').prop('checked', true).siblings('.admin_switch_text').text('사용');
    renderDocSelect();
    renderDocTags([]);
    renderQuestions([]);
    setState($('#catState'), null);
    $('#catTree').find('.admin_cat_item').removeClass('is_selected');
    $('#catLabel').trigger('focus');
  });

  /* 대분류 모달 */
  function openGroupModal(groupId) {
    var g = null;
    $.each(CATEGORY_GROUPS, function (i, x) { if (x.group_id === groupId) { g = x; return false; } });
    $('#catGroupModalTitle').text(g ? '대분류 수정' : '대분류 추가');
    $('#catGroupLabel').val(g ? g.group_label : '');
    $('#catGroupId').val(g ? g.group_id : '').prop('readonly', !!g);
    $('#catGroupEnabled').prop('checked', g ? g.enabled !== false : true);
    $('#catGroupDeleteBtn').prop('hidden', !g);
    $('#catGroupWarn').prop('hidden', !g);
    if (g) {
      $('#catGroupWarnText').html('이 대분류를 삭제하면 하위 카테고리 <b>' + g.categories.length + '개</b>도 함께 삭제됩니다. 하위 카테고리를 먼저 다른 대분류로 옮겨주세요.');
    }
    openModal('catGroupModal');
  }

  $('#catGroupAddBtn').on('click', function () { openGroupModal(null); });
  $('#catTree').on('click', '[data-group-edit]', function () {
    openGroupModal($(this).closest('.admin_cat_group').attr('data-group-id'));
  });
  $('#catGroupSaveBtn').on('click', function () {
    closeModal($('#catGroupModal'));
    toast('ok', '대분류를 저장했습니다.');
  });
  $('#catGroupDeleteBtn').on('click', function () {
    var gid = $('#catGroupId').val();
    closeModal($('#catGroupModal'));
    askConfirm({
      title: '대분류를 삭제할까요?',
      message: $('#catGroupLabel').val(),
      desc: '하위 카테고리도 함께 삭제됩니다. 이 작업은 되돌릴 수 없습니다.'
    }, function () {
      CATEGORY_GROUPS = $.grep(CATEGORY_GROUPS, function (g) { return g.group_id !== gid; });
      clearDetail();
      renderTree('');
      toast('ok', '대분류를 삭제했습니다.');
    });
  });

  /* 드래그 정렬 — 드롭 위치(before/after)까지 남기고 admin:reorder 를 1회 발생.
     배열 재정렬·저장은 개발 처리(화면 DOM 이동은 하지 않음 — 저장 실패 시 되돌리기가 쉬움) */
  var DRAG_SEL = '.admin_cat_group, .admin_cat_row, .admin_cat_q, .admin_quick_chip';
  var dragSrc = null;

  function dragKindOf($el) {
    if ($el.hasClass('admin_quick_chip')) { return 'quick'; }
    if ($el.hasClass('admin_cat_q')) { return 'question'; }
    if ($el.hasClass('admin_cat_row')) { return 'category'; }
    return 'group';
  }
  function dragIdOf($el) {
    var kind = dragKindOf($el);
    if (kind === 'quick') { return $el.attr('data-category-id'); }
    if (kind === 'question') { return $el.attr('data-index'); }
    if (kind === 'category') { return $el.find('.admin_cat_item').attr('data-category-id'); }
    return $el.attr('data-group-id');
  }

  $(document).on('dragstart', '.admin_drag', function (e) {
    dragSrc = $(this).closest(DRAG_SEL).addClass('is_dragging');
    if (e.originalEvent && e.originalEvent.dataTransfer) {
      e.originalEvent.dataTransfer.effectAllowed = 'move';
      e.originalEvent.dataTransfer.setData('text/plain', dragIdOf(dragSrc) || '');
    }
  });
  $(document).on('dragend', '.admin_drag', function () {
    $('.is_dragging').removeClass('is_dragging');
    $('.drop_target').removeClass('drop_target').removeAttr('data-drop-position');
    dragSrc = null;
  });
  $(document).on('dragover', DRAG_SEL, function (e) {
    e.preventDefault();
    e.stopPropagation();
    var $t = $(this);
    if (dragSrc && $t.is(dragSrc)) { return; }
    var rect = this.getBoundingClientRect();
    var y = (e.originalEvent ? e.originalEvent.clientY : 0) - rect.top;
    var pos = y < rect.height / 2 ? 'before' : 'after';
    $('.drop_target').not($t).removeClass('drop_target').removeAttr('data-drop-position');
    $t.addClass('drop_target').attr('data-drop-position', pos);
  });
  $(document).on('drop', DRAG_SEL, function (e) {
    e.preventDefault();
    e.stopPropagation();
    var $t = $(this);
    if (!dragSrc || $t.is(dragSrc)) { return; }
    var payload = {
      kind: dragKindOf(dragSrc),
      fromId: dragIdOf(dragSrc),
      toId: dragIdOf($t),
      position: $t.attr('data-drop-position') || 'after'
    };
    $('.drop_target').removeClass('drop_target').removeAttr('data-drop-position');
    $('.is_dragging').removeClass('is_dragging');
    dragSrc = null;
    $(document).trigger('admin:reorder', [payload]);
  });
  /* 목업 확인용 — 개발 이식 시 삭제 */
  $(document).on('admin:reorder', function (e, d) {
    toast('ok', 'admin:reorder — ' + d.kind + ' ' + d.fromId + ' → ' + d.toId + ' (' + d.position + ')');
  });

  /* ==========================================================================
     탭 ④ 임계값
     ========================================================================== */
  /* 검색 유사도 3구간 미리보기 + 역전 검증 (약한 근거 하한 < 검색 임계값) */
  function renderZones() {
    var floor = parseFloat($('#thFloor').val()) || 0;
    var soft = parseFloat($('#thSoftFloor').val()) || 0;
    var invalid = soft >= floor;
    $('#zoneFallback').css('width', (Math.min(soft, 1) * 100) + '%');
    $('#zoneSoft').css('width', (Math.max(0, Math.min(floor, 1) - Math.min(soft, 1)) * 100) + '%');
    $('#zoneOk').css('width', (Math.max(0, 1 - Math.max(floor, soft)) * 100) + '%');
    $('#zoneMarkSoft').text('약한 근거 하한 ' + soft.toFixed(2));
    $('#zoneMarkFloor').text('검색 임계값 ' + floor.toFixed(2));
    $('#thZoneBar').toggleClass('is_invalid', invalid);
    if (invalid) {
      setState($('#thZoneErr'), 'err', '약한 근거 하한은 검색 임계값보다 작아야 합니다');
    } else {
      setState($('#thZoneErr'), null);
    }
    $('#thSave').prop('disabled', invalid);
  }

  $('#panel_thresholds').on('input', '.admin_range', function () {
    $('#' + $(this).attr('data-range-for')).val($(this).val());
    $('#thCard, #panel_thresholds .admin_card').first().addClass('is_dirty');
    $(this).closest('.admin_card').addClass('is_dirty');
    renderZones();
  });
  $('#thFloor, #thSoftFloor, #thCache, #thIntent').on('input', function () {
    $('.admin_range[data-range-for="' + this.id + '"]').val($(this).val());
    $(this).closest('.admin_card').addClass('is_dirty');
    renderZones();
  });
  $('#thTopK').on('input', function () { $(this).closest('.admin_card').addClass('is_dirty'); });
  $('#thNumCtx, #thNumPredict').on('input', function () { $('#genCard').addClass('is_dirty'); });

  /* LLM 생성 설정 — 저장 버튼만 분리(리소스는 임계값과 동일) */
  $('#genSave').on('click', function () {
    var ctx = parseInt($('#thNumCtx').val(), 10);
    var pred = parseInt($('#thNumPredict').val(), 10);
    if (!(ctx >= 2048 && ctx <= 131072) || !(pred >= 128 && pred <= 8192)) {
      setState($('#genState'), 'err', '허용 범위를 벗어났습니다 (422)');
      toast('err', '입력값이 허용 범위를 벗어났습니다.');
      return;
    }
    setState($('#genState'), 'busy', '저장 중…');
    api('saveGeneration', { num_ctx: ctx, num_predict: pred }, function () {
      setState($('#genState'), 'ok', '저장되었습니다');
      $('#genCard').removeClass('is_dirty');
      toast('ok', 'LLM 생성 설정을 저장했습니다.');
    });
  });

  $('#thSave').on('click', function () {
    setState($('#thState'), 'busy', '저장 중…');
    api('saveThresholds', {
      floor: $('#thFloor').val(), soft_floor: $('#thSoftFloor').val(), cache: $('#thCache').val(),
      intent: $('#thIntent').val(), top_k: $('#thTopK').val()
    }, function () {
      setState($('#thState'), 'ok', '저장되었습니다');
      $('#panel_thresholds').find('.admin_card').removeClass('is_dirty');
      toast('ok', '임계값을 저장했습니다.');
    });
  });

  $('#thResetBtn').on('click', function () {
    renderZones();
    $.each(DEFAULT_THRESHOLDS, function (id, v) {
      $('#' + id).val(v);
      $('.admin_range[data-range-for="' + id + '"]').val(v);
    });
    setState($('#thState'), null);
    renderZones();
    $('#panel_thresholds').find('.admin_card').addClass('is_dirty');
    toast('ok', '기본값으로 되돌렸습니다. 저장을 눌러 적용하세요.');
  });

  /* ==========================================================================
     모달 공통 (배경 클릭 / ✕ / ESC)
     ========================================================================== */
  $('.qr_modal_backdrop').on('click', function (e) {
    if (e.target === this || $(e.target).closest('[data-modal-close]').length) { closeModal($(this)); }
  });
  $(document).on('keydown', function (e) {
    if (e.key === 'Escape') { $('.qr_modal_backdrop.is_open').removeClass('is_open'); }
  });
  $('#confirmOkBtn').on('click', function () {
    closeModal($('#confirmModal'));
    if (typeof confirmAction === 'function') { confirmAction(); }
    confirmAction = null;
  });

  /* 검색 클리어 버튼 */
  $(document).on('click', '[data-search-clear]', function () {
    var $wrap = $(this).closest('.admin_search');
    $wrap.removeClass('is_filled is_noresult').find('input').val('').trigger('input').trigger('focus');
  });

  /* ==========================================================================
     퍼블 확인용 상태 목업 바 (개발 이식 시 삭제)
     ========================================================================== */
  $('[data-dev-only]').on('click', '[data-mock]', function () {
    var kind = $(this).attr('data-mock');
    var $state = $('.admin_panel.is_active').find('.admin_save_state').first();
    if (!$state.length) { $state = $('#spState'); }
    if (kind === 'state_busy') { setState($state, 'busy', '저장 중…'); }
    if (kind === 'state_ok') { setState($state, 'ok', '저장되었습니다'); }
    if (kind === 'state_err') { setState($state, 'err', '저장에 실패했습니다 (500)'); }
    if (kind === 'dirty') { $('.admin_panel.is_active').find('.admin_card').first().toggleClass('is_dirty'); }
    if (kind === 'toast_ok') { toast('ok', '저장되었습니다.'); }
    if (kind === 'toast_err') { toast('err', '서버와 통신할 수 없습니다.'); }
    if (kind === 'doc_empty') {
      $('#docSearch').val('없는문서zz').trigger('input');
    }
    if (kind === 'doc_loading') {
      $('#docLoading').addClass('is_on');
      $('#docTableWrap').hide();
      setTimeout(function () { $('#docLoading').removeClass('is_on'); $('#docTableWrap').show(); }, 1800);
    }
    if (kind === 'cat_none') { clearDetail(); }
    if (kind === 'quick_full') {
      $('.admin_tab[data-tab="categories"]').trigger('click');
      quickCategoryIds = ['api_reg_flow', 'api_reg_field', 'spc_create', 'tmplt_edit', 'api_header', 'auth_key'];
      renderQuick();
    }
    if (kind === 'quick_empty') {
      $('.admin_tab[data-tab="categories"]').trigger('click');
      quickCategoryIds = [];
      renderQuick();
    }
    if (kind === 'quick_err') {
      $('.admin_tab[data-tab="categories"]').trigger('click');
      setState($('#quickState'), 'err', '저장에 실패했습니다 (422 · 최대 6개, 존재하는 카테고리만)');
      toast('err', '자주 찾는 주제 저장에 실패했습니다.');
    }
    if (kind === 'an_run') {
      $('.admin_tab[data-tab="analytics"]').trigger('click');
      runAnalysis();
    }
    if (kind === 'an_draft_err') {
      $('.admin_tab[data-tab="analytics"]').trigger('click');
      $('#anDraftTags').empty().append('<span class="admin_tag" data-doc-id="clu_1000">권한그룹은 무엇을 선택해야 하나요?</span>');
      $('#anDraftBase').text('1건');
      openModal('anDraftModal');
      draftStage('error');
    }
  });

  /* ==========================================================================
     탭 ④ 질문 분석 / 개선
     ========================================================================== */
  /* 분석 요약 (개발 단계에서 GET /admin/analytics 응답으로 교체) */
  var ANALYTICS = {
    last_run_at: '2026-08-14 09:12',
    log_count: 3182,
    kpi: { total: 3182, unique: 62, unresolved_rate: 18.6, no_doc: 14, avg_latency: 3.4 },
    routes: [
      { key: 'cache', label: 'cache', count: 700, rate: 22.0 },
      { key: 'intent', label: 'intent', count: 541, rate: 17.0 },
      { key: 'rag', label: 'rag', count: 1349, rate: 42.4 },
      { key: 'fallback', label: 'fallback', count: 592, rate: 18.6 }
    ],
    trend: [
      { d: '07-16', total: 88, unresolved: 21 }, { d: '07-20', total: 96, unresolved: 19 },
      { d: '07-24', total: 104, unresolved: 24 }, { d: '07-28', total: 92, unresolved: 15 },
      { d: '08-01', total: 128, unresolved: 31 }, { d: '08-05', total: 141, unresolved: 26 },
      { d: '08-09', total: 133, unresolved: 29 }, { d: '08-13', total: 156, unresolved: 34 }
    ],
    top_unresolved: [
      { label: 'API 등록 항목 설명', rate: 34.2 },
      { label: '권한 / 계정', rate: 29.8 },
      { label: 'OAS / Swagger 일괄 등록', rate: 24.1 },
      { label: '템플릿 적용 오류', rate: 19.6 },
      { label: 'API 배포', rate: 15.3 }
    ]
  };

  /* 클러스터 더미 — status / coverage / trend 전 조합이 섞이도록 구성 (62건) */
  var CLUSTERS = (function () {
    var seeds = [
      ['권한그룹은 무엇을 선택해야 하나요?', 'API 등록 시 권한그룹 선택 기준을 묻는 질문 묶음입니다. 부서 기본값 안내가 문서에 없습니다.', 'api_reg_field'],
      ['Path와 Method를 어떻게 입력하나요?', '경로 변수 표기와 다중 Method 등록 방법을 묻습니다.', 'api_reg_field'],
      ['등록한 API가 목록에 안 보여요', '배포 전 \'작성중\' 상태를 모르는 사용자가 많습니다.', 'api_reg_err'],
      ['API 등록은 어떻게 하나요?', '전체 절차를 묻는 기본 질문입니다. 문서가 충분합니다.', 'api_reg_flow'],
      ['그룹을 먼저 만들어야 하나요?', '그룹과 API 등록 선후 관계를 확인하는 질문입니다.', 'api_reg_flow'],
      ['Swagger YAML로 한 번에 등록할 수 있나요?', 'OAS 일괄 등록 가능 여부와 지원 버전을 묻습니다.', 'spc_oas'],
      ['YAML 파싱 오류가 납니다', '들여쓰기·인코딩 원인 안내가 문서에 없습니다.', 'spc_import_err'],
      ['그룹을 삭제하면 하위 API는?', '삭제 영향 범위를 확인하는 질문입니다.', 'spc_delete'],
      ['템플릿을 수정하려면?', '수정 경로와 기존 API 반영 여부를 함께 묻습니다.', 'tmplt_edit'],
      ['템플릿 적용 후 저장이 실패합니다', '필수 항목 누락 시 메시지가 불명확하다는 문의입니다.', 'tmplt_err'],
      ['API Key는 어디서 발급하나요?', '발급 경로와 재발급 가능 여부를 묻습니다.', 'auth_key'],
      ['SSO 로그인이 실패합니다', '사내 계정 동기화 지연 사례로 보입니다.', 'auth_sso'],
      ['배포 버튼이 활성화되지 않습니다', '승인 대기 상태와의 관계를 모르는 경우입니다.', 'api_deploy'],
      ['호출 한도는 어디서 설정하나요?', '쿼터 설정 화면이 문서화되어 있지 않습니다.', 'api_limit'],
      ['CORS 허용 도메인은 어디서 설정하나요?', '헤더/CORS 설정 위치를 묻는 질문입니다.', 'api_header'],
      ['운영 중인 API를 수정하면 바로 반영되나요?', '재배포 필요 여부를 확인하는 질문입니다.', 'api_edit'],
      ['서비스와 그룹의 차이는?', '용어 혼동에서 오는 반복 질문입니다.', 'api_reg_field'],
      ['등록 후 반영까지 얼마나 걸리나요?', '게이트웨이 반영 지연 시간을 묻습니다.', 'api_reg_flow'],
      ['v1, v2를 동시에 운영할 수 있나요?', '버전 병행 운영 정책 질문입니다.', 'api_version'],
      ['공통 모델을 재사용할 수 있나요?', '스키마 참조 방법을 묻습니다.', 'spc_schema'],
      ['부서 기본 템플릿을 지정할 수 있나요?', '기본 템플릿 지정 권한을 묻습니다.', 'tmplt_default']
    ];
    var statuses = ['new', 'reviewed', 'drafted', 'applied', 'excluded'];
    var routes = ['fallback', 'rag', 'cache', 'intent'];
    var out = [];
    for (var i = 0; i < 62; i++) {
      var s = seeds[i % seeds.length];
      var n = i < seeds.length ? 0 : Math.floor(i / seeds.length);
      var count = 148 - i * 2 - (i % 5) * 3;
      var status = statuses[i % 5];
      var route = routes[i % 4];
      /* 미해결률은 답변 경로와 맞물려야 목업이 모순 없이 읽힙니다 */
      var rate = route === 'fallback' ? 32 + ((i * 7) % 56)
               : route === 'rag' ? 4 + ((i * 11) % 22)
               : ((i * 5) % 14);
      var trendVal = ((i * 13) % 41) - 18;
      var raws = [];
      var rawSeeds = [s[0], s[0].replace('?', '') + ' 알려주세요', 'ㅇㅇ ' + s[0], s[0].slice(0, Math.max(6, s[0].length - 6)) + '...', s[0] + ' (재문의)'];
      for (var k = 0; k < 31 + (i % 9); k++) {
        raws.push({
          id: 'r' + i + '_' + k,
          text: rawSeeds[k % rawSeeds.length] + (k > 4 ? ' #' + (k + 1) : ''),
          answered_by: k % 3 === 0 ? route : routes[(i + k) % 4],
          asked_at: '2026-08-' + (13 - (k % 12) < 10 ? '0' : '') + (13 - (k % 12)) + ' 1' + (k % 9) + ':0' + (k % 6)
        });
      }
      out.push({
        id: 'clu_' + (1000 + i),
        question: n ? s[0] + (n === 1 ? ' (변형 표현)' : ' (유사 표현 ' + n + ')') : s[0],
        summary: s[1],
        /* AI가 분류하지 못한 미분류 케이스 — 7건 */
        category_id: (i % 9 === 4) ? null : s[2],
        category_confirmed: false,
        promoted: false,
        count: count < 4 ? 4 + (i % 7) : count,
        unresolved_rate: rate,
        top_route: route,
        trend: trendVal,
        status: status,
        /* has_doc 주기는 status(i%5)와 서로소인 7로 분리 — 반영됨 + 문서없음은 논리 모순이라 제외 */
        has_doc: status === 'applied' ? true : !(i % 7 === 3 || (route === 'fallback' && rate > 45)),
        last_asked: '2026-08-' + (14 - (i % 13) < 10 ? '0' : '') + (14 - (i % 13)),
        raws: raws
      });
    }
    return out;
  })();

  var ST_LABEL = { new: '신규', reviewed: '검토됨', drafted: '초안생성', applied: '반영됨', excluded: '제외', promoted: '추천질문' };
  ANALYTICS.total_count = (function () {
    var s = 0;
    $.each(CLUSTERS, function (i, c) { s += c.count; });
    return s;
  })();
  /* 헤더의 '대상 N건'도 같은 파생값을 써서 KPI 총 질문과 어긋나지 않게 */
  ANALYTICS.log_count = ANALYTICS.total_count;
  var anFilter = 'all';
  var anCatFilter = 'all';      /* 'all' | 'none'(미분류) | category_id */
  var anSelected = {};
  var anFiltered = [];

  function catLabelOf(id) {
    if (!id) { return '(미분류)'; }
    var hit = findCat(id);
    return hit ? hit.cat.label : '(미분류)';
  }

  /* 차트 렌더 — 인자로 받은 클러스터 집합에서 파생 (카테고리 필터 시 함께 재계산) */
  function renderAnCharts(list) {
    list = list || CLUSTERS;
    var totalCount = 0, routeAgg = { cache: 0, intent: 0, rag: 0, fallback: 0 }, catAgg = {};
    $.each(list, function (i, c) {
      totalCount += c.count;
      routeAgg[c.top_route] += c.count;
      var key = catLabelOf(c.category_id);
      if (!catAgg[key]) { catAgg[key] = { sum: 0, un: 0 }; }
      catAgg[key].sum += c.count;
      catAgg[key].un += c.count * c.unresolved_rate / 100;
    });
    if (!totalCount) { totalCount = 1; }

    var $bar = $('#anRouteBar').empty();
    var $lg = $('#anRouteLegend').empty();
    $.each(['cache', 'intent', 'rag', 'fallback'], function (i, key) {
      var rate = routeAgg[key] / totalCount * 100;
      $bar.append($('<span class="admin_stackbar_seg is_' + key + '"></span>')
        .css('width', rate + '%').attr('title', key + ' ' + rate.toFixed(1) + '%'));
      $lg.append($('<li><i class="is_' + key + '"></i>' + key + ' <b>' + rate.toFixed(1) + '%</b><span>' + routeAgg[key].toLocaleString() + '건</span></li>'));
    });

    var share = totalCount / Math.max(1, ANALYTICS.total_count);
    var t = $.map(ANALYTICS.trend, function (p) {
      return { d: p.d, total: Math.round(p.total * share), unresolved: Math.round(p.unresolved * share) };
    });
    var w = 320, h = 110, max = 0;
    $.each(t, function (i, p) { max = Math.max(max, p.total); });
    max = Math.max(20, Math.ceil(max / 20) * 20);
    function pts(key) {
      return $.map(t, function (p, i) {
        return (i * (w / (t.length - 1))).toFixed(1) + ',' + (h - 10 - (p[key] / max) * (h - 22)).toFixed(1);
      }).join(' ');
    }
    var area = 'M0,' + (h - 10) + ' L' + pts('total').split(' ').join(' L') + ' L' + w + ',' + (h - 10) + ' Z';
    $('#anTrendChart').html(
      '<path d="' + area + '" fill="rgba(48,155,162,.12)"></path>' +
      '<polyline points="' + pts('total') + '" fill="none" stroke="var(--qr-teal)" stroke-width="2" vector-effect="non-scaling-stroke"></polyline>' +
      '<polyline points="' + pts('unresolved') + '" fill="none" stroke="var(--qr-danger)" stroke-width="2" stroke-dasharray="4 3" vector-effect="non-scaling-stroke"></polyline>'
    );
    $('#anTrendAxis').empty();
    $.each(t, function (i, p) {
      if (i % 2 === 0 || i === t.length - 1) { $('#anTrendAxis').append($('<span></span>').text(p.d)); }
    });

    var tops = [];
    $.each(catAgg, function (label, v) { tops.push({ label: label, rate: v.sum ? v.un / v.sum * 100 : 0 }); });
    tops.sort(function (a, b) { return b.rate - a.rate; });
    tops = tops.slice(0, 5);
    var $bars = $('#anTopBars').empty();
    if (!tops.length) { $bars.append('<li class="admin_hint">표시할 데이터가 없습니다.</li>'); }
    $.each(tops, function (i, b) {
      $bars.append(
        '<li><div class="admin_bar_top"><span class="admin_bar_label">' + b.label + '</span>' +
        '<span class="admin_bar_val">' + b.rate.toFixed(1) + '%</span></div>' +
        '<div class="admin_bar_track"><div class="admin_bar_fill" style="width:' + Math.min(100, b.rate) + '%"></div></div></li>'
      );
    });
  }

  function renderAnKpi(list) {
    list = list || CLUSTERS;
    var total = 0, un = 0, noDoc = 0;
    $.each(list, function (i, c) {
      total += c.count;
      un += c.count * c.unresolved_rate / 100;
      if (!c.has_doc) { noDoc++; }
    });
    $('#kpiTotal').text(total.toLocaleString());
    $('#kpiUnique').text(list.length);
    $('#kpiUnresolved').text((total ? un / total * 100 : 0).toFixed(1) + '%');
    $('#kpiNoDocValue').text(noDoc);
    $('#kpiLatency').text(ANALYTICS.kpi.avg_latency.toFixed(1) + '초');
    $('#anLastRun').text(ANALYTICS.last_run_at);
    $('#anLogCount').text(ANALYTICS.log_count.toLocaleString() + '건');
  }

  function anSort(list) {
    var by = $('#anSort').val();
    return list.sort(function (a, b) {
      if (by === 'unresolved') { return b.unresolved_rate - a.unresolved_rate; }
      if (by === 'recent') { return a.last_asked < b.last_asked ? 1 : -1; }
      return b.count - a.count;
    });
  }

  function renderClusters() {
    var term = $.trim($('#anSearch').val() || '').toLowerCase();
    var $tb = $('#anTableBody').empty();
    var list = $.grep(CLUSTERS.slice(), function (c) {
      if (term && c.question.toLowerCase().indexOf(term) < 0) { return false; }
      /* 카테고리 필터 × 상태 칩 × 검색 = AND */
      if (anCatFilter === 'none' && c.category_id) { return false; }
      if (anCatFilter !== 'all' && anCatFilter !== 'none' && c.category_id !== anCatFilter) { return false; }
      if (anFilter === 'no_doc') { return !c.has_doc; }
      if (anFilter === 'unresolved') { return c.unresolved_rate >= 40; }
      if (anFilter === 'new') { return c.status === 'new'; }
      if (anFilter === 'applied') { return c.status === 'applied'; }
      return true;
    });
    anSort(list);
    anFiltered = list;

    $.each(list, function (i, c) {
      var $r = tpl('tpl_an_row').attr('data-cluster-id', c.id);
      $r.toggleClass('is_excluded', c.status === 'excluded');
      $r.find('.admin_an_check').prop('checked', !!anSelected[c.id]);
      $r.find('[data-bind="question"]').text(c.question);
      $r.find('[data-bind="summary"]').text(c.summary);
      var $cat = $r.find('[data-bind="category_label"]');
      $cat.text(catLabelOf(c.category_id) + (c.has_doc ? '' : ' · 문서 없음'));
      if (c.category_confirmed) { $cat.removeClass('is_ai_text').addClass('is_confirmed'); }
      $r.find('[data-bind="count"]').text(c.count.toLocaleString());
      $r.find('[data-bind="unresolved_rate"]').text(c.unresolved_rate + '%')
        .toggleClass('is_high', c.unresolved_rate >= 40);
      $r.find('[data-bind="top_route"]').text(c.top_route).addClass('is_' + c.top_route);
      $r.find('[data-bind="trend"]')
        .text((c.trend > 0 ? '▲ ' : c.trend < 0 ? '▼ ' : '– ') + Math.abs(c.trend) + '%')
        .addClass(c.trend > 3 ? 'is_up' : c.trend < -3 ? 'is_down' : 'is_flat');
      var $st = $r.find('[data-bind="status"]');
      $st.text(ST_LABEL[c.status]).addClass('is_' + c.status);
      /* 추천질문 등록은 상태와 다른 축 — 한 행에 뱃지 2개 가능 */
      if (c.promoted) {
        $st.after($('<span class="admin_st is_promoted"></span>').text(ST_LABEL.promoted));
      }
      $tb.append($r);
    });

    $('#anTable').closest('.admin_table_wrap').toggle(list.length > 0);
    $('#anEmpty').prop('hidden', list.length > 0);
    $('#anSearchWrap').toggleClass('is_noresult', list.length === 0 && !!term);
    /* 카테고리 필터는 타임리인이 아니라 상단 KPI·차트도 함께 재계산 */
    renderAnKpi(list);
    renderAnCharts(list);
    renderApplied();
    renderCatPicker();
    updateSelCount();
  }

  /* 적용된 조건 항목 (필 태그) */
  function renderApplied() {
    var chips = [];
    if (anCatFilter !== 'all') {
      chips.push({ kind: 'cat', label: '카테고리 · ' + (anCatFilter === 'none' ? '미분류' : catLabelOf(anCatFilter)) });
    }
    if (anFilter !== 'all') {
      chips.push({ kind: 'chip', label: '상태 · ' + $('#anFilters .admin_chip.is_active').text() });
    }
    var term = $.trim($('#anSearch').val() || '');
    if (term) { chips.push({ kind: 'term', label: '검색 · ' + term }); }

    var $tags = $('#anAppliedTags').empty();
    $.each(chips, function (i, c) {
      var $t = tpl('tpl_doc_tag').attr('data-doc-id', c.kind);
      $t.find('[data-bind="doc_id"]').text(c.label);
      $t.find('[data-tag-remove]').attr('data-applied-remove', c.kind);
      $tags.append($t);
    });
    $('#anApplied').prop('hidden', chips.length === 0);
    $('#anAppliedCount').text(anFiltered.length + '건 / 전체 ' + CLUSTERS.length + '건');
  }

  /* 카테고리 필터 팝오버 — 항목별 클러스턼 건수 표시 */
  function clusterCountFor(catId) {
    return $.grep(CLUSTERS, function (c) {
      return catId === 'all' ? true : catId === 'none' ? !c.category_id : c.category_id === catId;
    }).length;
  }

  function renderCatPicker() {
    var term = $.trim($('#anCatSearch').val() || '');
    var $sp = $('#anCatSpecial').empty();
    $.each([['all', '전체 카테고리'], ['none', '미분류 (AI가 분류 못함)']], function (i, s) {
      var $it = tpl('tpl_an_cat_item');
      $it.attr({ 'data-category-id': s[0], 'data-category-label': s[1] })
        .toggleClass('is_selected', anCatFilter === s[0])
        .attr('aria-selected', anCatFilter === s[0] ? 'true' : 'false');
      $it.find('[data-bind="label"]').text(s[1]);
      var n = clusterCountFor(s[0]);
      $it.find('[data-bind="cluster_count"]').text(n).toggleClass('is_zero', n === 0);
      $sp.append($it);
    });

    var $body = $('#anCatGroups').empty();
    var total = 0;
    $.each(CATEGORY_GROUPS, function (i, g) {
      var $g = tpl('tpl_an_cat_group').attr('data-group-id', g.group_id);
      $g.find('.chat_cat_group_head').attr('data-group-id', g.group_id);
      $g.find('[data-bind="group_label"]').text(g.group_label);
      var $list = $g.find('.chat_cat_list');
      var shown = 0, gCount = 0;
      $.each(g.categories, function (j, c) {
        var n = clusterCountFor(c.id);
        gCount += n;
        if (term && c.label.toLowerCase().indexOf(term.toLowerCase()) < 0) { return; }
        var $it = tpl('tpl_an_cat_item');
        $it.attr({ 'data-category-id': c.id, 'data-category-label': c.label, 'data-group-id': g.group_id })
          .toggleClass('is_selected', anCatFilter === c.id)
          .attr('aria-selected', anCatFilter === c.id ? 'true' : 'false');
        highlight($it.find('[data-bind="label"]'), c.label, term);
        $it.find('[data-bind="cluster_count"]').text(n).toggleClass('is_zero', n === 0);
        $list.append($it);
        shown++;
      });
      $g.find('[data-bind="count"]').text('(' + gCount + ')');
      if (term && shown === 0) { return; }
      var open = !!term || (anCatFilter !== 'all' && anCatFilter !== 'none' && findCat(anCatFilter) && findCat(anCatFilter).group.group_id === g.group_id);
      $g.find('.chat_cat_group_head').toggleClass('is_open', !!open).attr('aria-expanded', open ? 'true' : 'false');
      $g.find('.chat_cat_list').toggleClass('is_open', !!open);
      total += shown;
      $body.append($g);
    });
    $('#anCatPopover').toggleClass('is_empty', total === 0)
      .attr('data-selected-category', anCatFilter === 'all' ? '' : anCatFilter);

    var label = anCatFilter === 'all' ? '전체 카테고리' : anCatFilter === 'none' ? '미분류' : catLabelOf(anCatFilter);
    $('#anCatTrigger').toggleClass('is_active', anCatFilter !== 'all')
      .attr({ 'data-category-id': anCatFilter === 'all' ? '' : anCatFilter, 'data-category-label': label });
    $('#anCatTrigger').find('.chat_cat_trigger_label').text(label).attr('title', label);
  }

  function updateSelCount() {
    var n = 0;
    $.each(anSelected, function (k, v) { if (v) { n++; } });
    $('#anSelCount').text(n);
    $('#anDraftBtn').prop('disabled', n === 0);
    $('#anMoreBtn').prop('disabled', n === 0);
    if (n === 0) { $('#anMoreMenu').prop('hidden', true); $('#anMoreBtn').attr('aria-expanded', 'false'); }
  }

  function selectedIds() {
    var ids = [];
    $.each(anSelected, function (k, v) { if (v) { ids.push(k); } });
    return ids;
  }

  function findCluster(id) {
    var f = null;
    $.each(CLUSTERS, function (i, c) { if (c.id === id) { f = c; return false; } });
    return f;
  }

  /* 행 펼침 — 원문 질문 */
  $('#anTableBody').on('click', '[data-cluster-toggle]', function () {
    var $row = $(this).closest('tr');
    var id = $row.attr('data-cluster-id');
    var open = !$row.hasClass('is_open');
    $row.toggleClass('is_open', open);
    $row.next('.admin_an_detail').remove();
    if (!open) { return; }
    var c = findCluster(id);
    var $d = tpl('tpl_an_raw_wrap').attr('data-cluster-id', id);
    $d.find('[data-bind="raw_count"]').text('(' + c.raws.length + '건 · 최근 ' + c.last_asked + ')');
    var $ul = $d.find('.admin_an_raws');
    $.each(c.raws, function (j, r) {
      var $li = tpl('tpl_an_raw').attr('data-raw-id', r.id);
      $li.find('[data-bind="answered_by"]').text(r.answered_by).addClass('is_' + r.answered_by);
      $li.find('[data-bind="text"]').text(r.text);
      $li.find('[data-bind="asked_at"]').text(r.asked_at);
      $ul.append($li);
    });
    $row.after($d);
  });

  /* 원문 개별 제외 — 오타·장난 질문 정리 */
  $('#anTableBody').on('click', '[data-raw-exclude]', function () {
    var $li = $(this).closest('.admin_an_raw').toggleClass('is_excluded');
    $(this).text($li.hasClass('is_excluded') ? '제외 취소' : '이 질문 제외');
    toast('ok', $li.hasClass('is_excluded') ? '이 질문을 클러스터에서 제외했습니다.' : '제외를 취소했습니다.');
  });

  /* 클러스터 상태 변경 */
  $('#anTableBody').on('click', '[data-cluster-status]', function () {
    var id = $(this).closest('.admin_an_detail').attr('data-cluster-id');
    var st = $(this).attr('data-cluster-status');
    var c = findCluster(id);
    if (!c) { return; }
    c.status = st;
    renderClusters();
    renderAnKpi();
    toast('ok', '상태를 \'' + ST_LABEL[st] + '\'으로 변경했습니다.');
  });

  /* 선택 */
  $('#anTableBody').on('change', '.admin_an_check', function () {
    var id = $(this).closest('tr').attr('data-cluster-id');
    anSelected[id] = this.checked;
    updateSelCount();
  });
  $('#anCheckAll').on('change', function () {
    var on = this.checked;
    $('#anTableBody').find('.admin_an_row').each(function () {
      anSelected[$(this).attr('data-cluster-id')] = on;
      $(this).find('.admin_an_check').prop('checked', on);
    });
    updateSelCount();
  });

  /* 검색 / 필터 / 정렬 */
  $('#anSearch').on('input', function () {
    $('#anSearchWrap').toggleClass('is_filled', !!$(this).val());
    renderClusters();
  });
  $('#anFilters').on('click', '.admin_chip', function () {
    anFilter = $(this).attr('data-filter');
    $('#anFilters .admin_chip').removeClass('is_active');
    $(this).addClass('is_active');
    $('#kpiNoDoc').toggleClass('is_active', anFilter === 'no_doc');
    renderClusters();
  });
  $('#kpiNoDoc').on('click', function () {
    anFilter = 'no_doc';
    $('#anFilters .admin_chip').removeClass('is_active').filter('[data-filter="no_doc"]').addClass('is_active');
    $(this).addClass('is_active');
    renderClusters();
  });
  $('#anSort').on('change', renderClusters);

  /* ---- 카테고리 필터 팝오버 ---- */
  function openCatPop() {
    $('#anCatPopover').addClass('is_open').attr('aria-hidden', 'false');
    $('#anCatTrigger').find('.chat_cat_trigger_main').attr('aria-expanded', 'true');
    $('#anCatSearch').val('');
    renderCatPicker();
    $('#anCatSearch').trigger('focus');
  }
  function closeCatPop() {
    $('#anCatPopover').removeClass('is_open').attr('aria-hidden', 'true');
    $('#anCatTrigger').find('.chat_cat_trigger_main').attr('aria-expanded', 'false');
  }
  $('#anCatTrigger').on('click', '.chat_cat_trigger_main', function () {
    if ($('#anCatPopover').hasClass('is_open')) { closeCatPop(); } else { openCatPop(); }
  });
  $('#anCatTrigger').on('click', '[data-category-clear]', function (e) {
    e.stopPropagation();
    anCatFilter = 'all';
    renderClusters();
  });
  $('#anCatPopover').on('click', '[data-popover-close]', closeCatPop);
  $('#anCatPopover').on('click', '.chat_cat_group_head', function () {
    var open = !$(this).hasClass('is_open');
    $(this).toggleClass('is_open', open).attr('aria-expanded', open ? 'true' : 'false');
    $(this).siblings('.chat_cat_list').toggleClass('is_open', open);
  });
  $('#anCatPopover').on('click', '.chat_cat_item', function () {
    anCatFilter = $(this).attr('data-category-id');
    closeCatPop();
    renderClusters();
  });
  $('#anCatSearch').on('input', renderCatPicker);
  $(document).on('mousedown', function (e) {
    if ($('#anCatPopover').hasClass('is_open') && !$(e.target).closest('#anCatPopover, #anCatTrigger').length) { closeCatPop(); }
    if (!$('#anMoreMenu').prop('hidden') && !$(e.target).closest('.admin_split_btn').length) {
      $('#anMoreMenu').prop('hidden', true);
      $('#anMoreBtn').attr('aria-expanded', 'false');
    }
  });

  /* ---- 적용된 조건 해제 ---- */
  $('#anAppliedTags').on('click', '[data-applied-remove]', function () {
    var kind = $(this).attr('data-applied-remove');
    if (kind === 'cat') { anCatFilter = 'all'; }
    if (kind === 'chip') {
      anFilter = 'all';
      $('#anFilters .admin_chip').removeClass('is_active').filter('[data-filter="all"]').addClass('is_active');
      $('#kpiNoDoc').removeClass('is_active');
    }
    if (kind === 'term') { $('#anSearch').val(''); $('#anSearchWrap').removeClass('is_filled is_noresult'); }
    renderClusters();
  });
  $('#anResetBtn').on('click', function () {
    anCatFilter = 'all';
    anFilter = 'all';
    $('#anFilters .admin_chip').removeClass('is_active').filter('[data-filter="all"]').addClass('is_active');
    $('#kpiNoDoc').removeClass('is_active');
    $('#anSearch').val('');
    $('#anSearchWrap').removeClass('is_filled is_noresult');
    renderClusters();
  });

  /* ---- 더보기 메뉴 ---- */
  $('#anMoreBtn').on('click', function () {
    var open = $('#anMoreMenu').prop('hidden');
    $('#anMoreMenu').prop('hidden', !open);
    $(this).attr('aria-expanded', open ? 'true' : 'false');
  });
  $('#anMoreMenu').on('click', '.admin_menu_item', function () {
    var action = $(this).attr('data-action');
    $('#anMoreMenu').prop('hidden', true);
    $('#anMoreBtn').attr('aria-expanded', 'false');
    var ids = selectedIds();
    if (!ids.length) { return; }
    if (action === 'promote') { openPromote(ids); }
    if (action === 'assign') { openAssign(ids); }
    if (action === 'exclude') { bulkExclude(ids); }
  });

  /* ---- 추천 질문 등록 ---- */
  function catOptions($sel) {
    $sel.empty();
    $.each(CATEGORY_GROUPS, function (i, g) {
      $.each(g.categories, function (j, c) {
        $sel.append($('<option></option>').val(c.id).text(g.group_label + ' › ' + c.label));
      });
    });
  }

  function existingQuestions(catId) {
    var hit = findCat(catId);
    return hit ? hit.cat.questions.slice() : [];
  }

  function renderPromoteRows(ids) {
    var exists = existingQuestions($('#anPromoteCat').val());
    var $wrap = $('#anPromoteRows').empty();
    var dup = 0;
    $.each(ids, function (i, id) {
      var c = findCluster(id);
      if (!c) { return; }
      var $r = tpl('tpl_an_promote_row').attr('data-cluster-id', c.id);
      /* 대표 질문은 원문에서 뽑은 값이라 그대로 노출하면 안 되는 문구가 섞임 → 다듬은 초안을 제공 */
      var clean = c.question.replace(/^(ㅇㅇ|ㅎㅎ|아니)\s*/, '').replace(/\s*\((변형|유사)[^)]*\)$/, '').trim();
      if (!/[?？]$/.test(clean)) { clean += '?'; }
      $r.find('[data-bind="question"]').val(clean);
      $r.find('[data-bind="raw_question"]').text(c.question);
      var isDup = $.inArray(clean, exists) > -1;
      if (isDup) {
        dup++;
        $r.addClass('is_dup').find('input[type="checkbox"]').prop('checked', false);
        $r.find('[data-bind="duplicate"]').prop('hidden', false);
      }
      $wrap.append($r);
    });
    $('#anPromoteCount').text('(' + ids.length + ')');
    $('#anPromoteDupHint').prop('hidden', dup === 0);
  }

  function openPromote(ids) {
    catOptions($('#anPromoteCat'));
    var first = findCluster(ids[0]);
    if (first && first.category_id) { $('#anPromoteCat').val(first.category_id); }
    $('#anPromoteCat').data('ids', ids);
    renderPromoteRows(ids);
    setState($('#anPromoteState'), null);
    openModal('anPromoteModal');
  }

  $('#anPromoteCat').on('change', function () {
    renderPromoteRows($(this).data('ids') || []);
  });

  $('#anPromoteSaveBtn').on('click', function () {
    var catId = $('#anPromoteCat').val();
    var hit = findCat(catId);
    var picked = [];
    $('#anPromoteRows').find('.admin_promote_row').each(function () {
      if (!$(this).find('input[type="checkbox"]').prop('checked')) { return; }
      var text = $.trim($(this).find('[data-bind="question"]').val());
      if (text) { picked.push({ id: $(this).attr('data-cluster-id'), text: text }); }
    });
    if (!picked.length) {
      setState($('#anPromoteState'), 'err', '등록할 문구를 선택해 주세요');
      return;
    }
    setState($('#anPromoteState'), 'busy', '등록 중…');
    api('promoteQuestions', { category_id: catId, items: picked }, function () {
      $.each(picked, function (i, p) {
        if (hit && $.inArray(p.text, hit.cat.questions) < 0) { hit.cat.questions.push(p.text); }
        var c = findCluster(p.id);
        if (c) { c.promoted = true; }
      });
      if (selectedCatId === catId) { selectCategory(catId); }
      renderTree($('#catSearch').val());
      renderClusters();
      setState($('#anPromoteState'), 'ok', '등록되었습니다');
      toast('ok', picked.length + '건을 추천 질문으로 등록했습니다.');
      setTimeout(function () { closeModal($('#anPromoteModal')); }, 600);
    });
  });

  /* ---- 카테고리 지정 (AI 추정 → 사람 확정) ---- */
  function openAssign(ids) {
    var $tags = $('#anAssignTags').empty();
    $.each(ids, function (i, id) {
      var c = findCluster(id);
      if (!c) { return; }
      var $t = tpl('tpl_doc_tag').attr('data-doc-id', c.id);
      $t.find('[data-bind="doc_id"]').text(c.question);
      $t.find('[data-tag-remove]').remove();
      $tags.append($t);
    });
    $('#anAssignBase').text(ids.length + '건');
    catOptions($('#anAssignCat'));
    var first = findCluster(ids[0]);
    if (first && first.category_id) { $('#anAssignCat').val(first.category_id); }
    $('#anAssignCat').data('ids', ids);
    setState($('#anAssignState'), null);
    openModal('anAssignModal');
  }

  $('#anAssignSaveBtn').on('click', function () {
    var ids = $('#anAssignCat').data('ids') || [];
    var catId = $('#anAssignCat').val();
    setState($('#anAssignState'), 'busy', '확정 중…');
    api('assignCategory', { ids: ids, category_id: catId }, function () {
      $.each(ids, function (i, id) {
        var c = findCluster(id);
        if (c) { c.category_id = catId; c.category_confirmed = true; }
      });
      renderClusters();
      setState($('#anAssignState'), 'ok', '확정되었습니다');
      toast('ok', ids.length + '건의 카테고리를 확정했습니다.');
      setTimeout(function () { closeModal($('#anAssignModal')); }, 600);
    });
  });

  /* ---- 일괄 제외 (확인 모달 경유) ---- */
  function bulkExclude(ids) {
    askConfirm({
      title: '선택한 클러스터를 제외할까요?',
      message: ids.length + '건',
      desc: '제외한 클러스터는 목록에서 흐리게 표시되고, 문서화·추천질문 대상에서 빠집니다. 개별 원문 제외와는 별개입니다.',
      okLabel: '제외'
    }, function () {
      $.each(ids, function (i, id) {
        var c = findCluster(id);
        if (c) { c.status = 'excluded'; }
      });
      anSelected = {};
      renderClusters();
      toast('ok', ids.length + '건을 제외 처리했습니다.');
    });
  }

  /* 분석 실행 — 진행 상태 (초기 임베딩은 indeterminate) */
  function runAnalysis() {
    var $p = $('#anProgress').prop('hidden', false).addClass('is_indeterminate');
    $('#anProgressLabel').text('질문 임베딩 생성 중…');
    $('#anProgressFill').css('width', '0%');
    $('#anProgressNum').text('0%');
    setState($('#anRunState'), 'busy', '분석 중…');
    $('#anRunBtn').prop('disabled', true);

    setTimeout(function () {
      $p.removeClass('is_indeterminate');
      var pct = 0;
      var timer = setInterval(function () {
        pct += 7 + Math.floor(Math.random() * 9);
        if (pct >= 100) { pct = 100; }
        $('#anProgressFill').css('width', pct + '%');
        $('#anProgressNum').text(pct + '%');
        $('#anProgressLabel').text(pct < 45 ? '유사 질문 클러스터링 중…' : pct < 80 ? '대표 질문·요약 생성 중…' : '문서 커버리지 판정 중…');
        if (pct === 100) {
          clearInterval(timer);
          setTimeout(function () {
            $p.prop('hidden', true);
            $('#anRunBtn').prop('disabled', false);
            setState($('#anRunState'), 'ok', '분석 완료');
            ANALYTICS.last_run_at = '2026-08-14 10:41';
            renderClusters();
            toast('ok', '질문 분석을 완료했습니다.');
          }, 400);
        }
      }, 420);
    }, 1600);
  }
  $('#anRunBtn').on('click', runAnalysis);

  /* 초안 생성 모달 — 생성중 / 결과 / 저장중 / 실패 */
  function draftStage(stage) {
    $('#anDraftBox').find('.admin_draft_stage').prop('hidden', true)
      .filter('[data-stage="' + stage + '"]').prop('hidden', false);
    $('#anDraftSaveBtn').prop('hidden', stage !== 'result');
    $('#anDraftRetryBtn').prop('hidden', stage !== 'error');
    setState($('#anDraftState'), stage === 'error' ? 'err' : null, stage === 'error' ? '생성 실패' : '');
  }

  function openDraft(ids) {
    var $tags = $('#anDraftTags').empty();
    $.each(ids, function (i, id) {
      var c = findCluster(id);
      if (!c) { return; }
      var $t = tpl('tpl_doc_tag').attr('data-doc-id', c.id);
      $t.find('[data-bind="doc_id"]').text(c.question);
      $tags.append($t);
    });
    $('#anDraftBase').text(ids.length + '건');
    var $sel = $('#anDraftCategory').empty();
    $.each(CATEGORY_GROUPS, function (i, g) {
      $.each(g.categories, function (j, c) {
        $sel.append($('<option></option>').val(c.id).text(g.group_label + ' › ' + c.label));
      });
    });
    var first = findCluster(ids[0]);
    if (first) { $sel.val(first.category_id); }
    draftStage('generating');
    openModal('anDraftModal');

    setTimeout(function () {
      if (!first) { return; }
      $('#anDraftDocId').val('api-' + first.category_id.replace(/_/g, '-') + '-보완.md');
      $('#anDraftContent').val(
        '# ' + first.question.replace(/[?？]/g, '') + '\n\n' +
        '## 요약\n' + first.summary + '\n\n' +
        '## 안내\n' +
        '1. 좌측 메뉴 > API Manager > 해당 화면으로 이동합니다.\n' +
        '2. 화면 상단의 항목을 입력합니다. (필수 항목은 * 표시)\n' +
        '3. [저장] 후 [배포]를 눌러 게이트웨이에 반영합니다.\n\n' +
        '## 자주 겪는 문제\n' +
        '- 저장했는데 목록에 보이지 않는 경우: 배포 전 \'작성중\' 상태입니다.\n' +
        '- 권한 오류가 나는 경우: 권한그룹 설정을 먼저 확인하세요.\n\n' +
        '> 이 문서는 최근 ' + first.count + '건의 질문(미해결률 ' + first.unresolved_rate + '%)을 근거로 생성된 초안입니다.'
      );
      draftStage('result');
    }, 2200);
  }

  $('#anDraftBtn').on('click', function () {
    var ids = [];
    $.each(anSelected, function (k, v) { if (v) { ids.push(k); } });
    if (!ids.length) { return; }
    openDraft(ids);
  });
  $('#anTableBody').on('click', '[data-cluster-draft]', function () {
    openDraft([$(this).closest('tr').attr('data-cluster-id')]);
  });
  $('#anDraftRetryBtn').on('click', function () {
    var ids = $('#anDraftTags').find('.admin_tag').map(function () { return $(this).attr('data-doc-id'); }).get();
    openDraft(ids);
  });
  $('#anDraftSaveBtn').on('click', function () {
    setState($('#anDraftState'), 'busy', '문서로 저장 중…');
    api('saveDraft', { doc_id: $('#anDraftDocId').val() }, function () {
      DOCS.unshift({
        doc_id: $('#anDraftDocId').val(),
        title: $('#anDraftContent').val().split('\n')[0].replace(/^#\s*/, ''),
        category: catLabelOf($('#anDraftCategory').val()),
        url: '/portal/guide/new', updated_at: '2026-08-14', chunks: 5
      });
      renderDocs($('#docSearch').val());
      renderDocSelect();
      $.each($('#anDraftTags').find('.admin_tag'), function () {
        var c = findCluster($(this).attr('data-doc-id'));
        if (c) { c.status = 'applied'; c.has_doc = true; }
      });
      renderClusters();
      renderAnKpi();
      setState($('#anDraftState'), 'ok', '저장되었습니다');
      toast('ok', 'RAG 문서로 저장했습니다. 문서 관리 탭에서 확인하세요.');
      setTimeout(function () { closeModal($('#anDraftModal')); }, 600);
    });
  });

  /* ==========================================================================
     탭 ③ — 자주 찾는 주제 (챗봇 인트로 칩 6개)
     ========================================================================== */
  function quickIsEnabled(id) {
    var hit = findCat(id);
    return hit ? hit.cat.enabled !== false : false;
  }

  function renderQuick() {
    var $wrap = $('#quickChips').empty();
    var hasOff = false;
    $.each(quickCategoryIds, function (i, id) {
      var hit = findCat(id);
      if (!hit) { return; }
      var label = hit.cat.label;
      var $c = tpl('tpl_quick_chip');
      $c.attr({ 'data-category-id': id, 'data-category-label': label, title: label });
      $c.find('[data-bind="label"]').text(label);
      if (hit.cat.enabled === false) {
        hasOff = true;
        $c.find('[data-bind="enabled"]').prop('hidden', false);
      }
      $wrap.append($c);
    });

    var n = quickCategoryIds.length;
    var full = n >= QUICK_MAX;
    $('#quickCount').text(n + ' / ' + QUICK_MAX);
    $('#quickCard').toggleClass('is_full', full);
    $('#quickEmpty').prop('hidden', n > 0);
    $('#quickAddBtn').prop('disabled', full);
    $('#quickHint').text(full
      ? '최대 6개까지 지정할 수 있습니다. 먼저 하나를 제거해 주세요.'
      : '챗봇 첫 화면에 이 순서대로 노출됩니다. 최대 6개까지 지정할 수 있고, 순서는 드래그로 바꿉니다.');
    $('#quickWarn').prop('hidden', !hasOff);
    renderQuickPicker();
  }

  function renderQuickPicker() {
    var term = $.trim($('#quickCatSearch').val() || '');
    var $body = $('#quickCatGroups').empty();
    var total = 0;
    $.each(CATEGORY_GROUPS, function (i, g) {
      var $g = tpl('tpl_an_cat_group').attr('data-group-id', g.group_id);
      $g.find('.chat_cat_group_head').attr('data-group-id', g.group_id);
      $g.find('[data-bind="group_label"]').text(g.group_label);
      $g.find('[data-bind="count"]').text('(' + g.categories.length + ')');
      var $list = $g.find('.chat_cat_list');
      var shown = 0;
      $.each(g.categories, function (j, c) {
        if (term && c.label.toLowerCase().indexOf(term.toLowerCase()) < 0) { return; }
        var picked = $.inArray(c.id, quickCategoryIds) > -1;
        var $it = tpl('tpl_an_cat_item');
        $it.attr({ 'data-category-id': c.id, 'data-category-label': c.label, 'data-group-id': g.group_id })
          .toggleClass('is_selected', picked)
          .toggleClass('is_off', c.enabled === false)
          .attr('aria-selected', picked ? 'true' : 'false');
        highlight($it.find('[data-bind="label"]'), c.label, term);
        $it.find('[data-bind="cluster_count"]').remove();
        $list.append($it);
        shown++;
      });
      if (term && shown === 0) { return; }
      var open = !!term;
      $g.find('.chat_cat_group_head').toggleClass('is_open', open).attr('aria-expanded', open ? 'true' : 'false');
      $g.find('.chat_cat_list').toggleClass('is_open', open);
      total += shown;
      $body.append($g);
    });
    $('#quickCatPopover').toggleClass('is_empty', total === 0);
  }

  function openQuickPop() {
    $('#quickCatPopover').addClass('is_open').attr('aria-hidden', 'false');
    $('#quickAddBtn').attr('aria-expanded', 'true');
    $('#quickCatSearch').val('');
    renderQuickPicker();
    $('#quickCatSearch').trigger('focus');
  }
  function closeQuickPop() {
    $('#quickCatPopover').removeClass('is_open').attr('aria-hidden', 'true');
    $('#quickAddBtn').attr('aria-expanded', 'false');
  }

  $('#quickAddBtn').on('click', function () {
    if ($('#quickCatPopover').hasClass('is_open')) { closeQuickPop(); } else { openQuickPop(); }
  });
  $('#quickCatPopover').on('click', '[data-popover-close]', closeQuickPop);
  $('#quickCatPopover').on('click', '.chat_cat_group_head', function () {
    var open = !$(this).hasClass('is_open');
    $(this).toggleClass('is_open', open).attr('aria-expanded', open ? 'true' : 'false');
    $(this).siblings('.chat_cat_list').toggleClass('is_open', open);
  });
  /* 이미 담긴 카테고리는 토글로 제거 */
  $('#quickCatPopover').on('click', '.chat_cat_item', function () {
    var id = $(this).attr('data-category-id');
    var at = $.inArray(id, quickCategoryIds);
    if (at > -1) {
      quickCategoryIds.splice(at, 1);
    } else {
      if (quickCategoryIds.length >= QUICK_MAX) {
        toast('err', '최대 ' + QUICK_MAX + '개까지 지정할 수 있습니다.');
        return;
      }
      quickCategoryIds.push(id);
      if (!quickIsEnabled(id)) { toast('err', '미사용 카테고리라 챗봇에는 표시되지 않습니다.'); }
    }
    $('#quickCard').addClass('is_dirty');
    setState($('#quickState'), null);
    renderQuick();
  });
  $('#quickCatSearch').on('input', renderQuickPicker);
  $(document).on('mousedown', function (e) {
    if ($('#quickCatPopover').hasClass('is_open') && !$(e.target).closest('#quickCatPopover, #quickAddBtn').length) { closeQuickPop(); }
  });

  $('#quickChips').on('click', '[data-quick-remove]', function () {
    var id = $(this).closest('.admin_quick_chip').attr('data-category-id');
    quickCategoryIds = $.grep(quickCategoryIds, function (x) { return x !== id; });
    $('#quickCard').addClass('is_dirty');
    renderQuick();
  });

  $('#quickSaveBtn').on('click', function () {
    setState($('#quickState'), 'busy', '저장 중…');
    /* 실제로는 카테고리 트리와 함께 PUT /admin/categories 로 전송됩니다 */
    api('saveQuickCategories', { quick_category_ids: quickCategoryIds }, function () {
      setState($('#quickState'), 'ok', '저장되었습니다');
      $('#quickCard').removeClass('is_dirty');
      toast('ok', '자주 찾는 주제를 저장했습니다.');
    });
  });

  /* 카테고리 삭제 시 자주 찾는 주제에서도 제거 */
  function quickDropCategory(id) {
    if ($.inArray(id, quickCategoryIds) < 0) { return; }
    quickCategoryIds = $.grep(quickCategoryIds, function (x) { return x !== id; });
    renderQuick();
  }

  /* ==========================================================================
     초기화
     ========================================================================== */
  renderDocs('');
  renderDocSelect();
  selectedCatId = 'api_reg_flow';
  renderTree('');
  selectCategory('api_reg_flow');
  renderQuick();
  renderZones();
  renderAnKpi();
  renderAnCharts();
  renderClusters();
})(jQuery);
