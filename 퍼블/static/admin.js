window.__adminLoaded = true;
/* ============================================================
   API Manager 도우미 — 관리자 화면 (jQuery)
   개발 이식 시: 최상단 상수(더미 데이터)는 서버 응답으로 교체
   ============================================================ */

/* ------------------------------------------------------------
   1. 카테고리 (대분류 5 / 카테고리 48)
   ------------------------------------------------------------ */
var CATEGORY_GROUPS = [
  { group_id:'g_reg', group_name:'API 등록', used:true, categories:[
    { category_id:'c_reg_flow',   name:'API 등록 절차', used:true, questions:[
      'API를 처음 등록하려면 무엇부터 해야 하나요?','API 등록 후 바로 호출할 수 있나요?','API 등록에 승인 절차가 있나요?'] },
    { category_id:'c_reg_fields', name:'API 등록 항목 설명', used:true, questions:[
      '권한그룹은 무엇을 뜻하나요?','서비스 URI와 운영 URI의 차이가 무엇인가요?','API 등록 화면의 필수 입력 항목만 알려주세요.'] },
    { category_id:'c_reg_error',  name:'API 등록 오류', used:true, questions:['API 등록 시 중복 오류가 뜹니다.','저장 버튼을 눌러도 반응이 없습니다.'] },
    { category_id:'c_reg_quick',  name:'퀵 API 등록', used:true, questions:[] },
    { category_id:'c_reg_bulk',   name:'API 일괄 등록(엑셀)', used:true, questions:[] },
    { category_id:'c_reg_modify', name:'등록한 API 수정', used:true, questions:[] },
    { category_id:'c_reg_delete', name:'API 삭제 · 비활성화', used:true, questions:[] },
    { category_id:'c_reg_version',name:'API 버전 관리', used:true, questions:[] },
    { category_id:'c_reg_copy',   name:'API 복제 등록', used:false, questions:[] },
    { category_id:'c_reg_swagger',name:'Swagger 파일로 등록', used:true, questions:[] },
    { category_id:'c_reg_test',   name:'등록 API 테스트 호출', used:true, questions:[] },
    { category_id:'c_reg_publish',name:'API 공개 범위 설정', used:true, questions:[] }
  ]},
  { group_id:'g_spc', group_name:'API 그룹(스펙)', used:true, categories:[
    { category_id:'c_spc_create', name:'API 그룹(SPC) 등록', used:true, questions:['API 그룹은 어떻게 만드나요?','SPC 코드 규칙이 있나요?'] },
    { category_id:'c_spc_fields', name:'API 그룹 항목 설명', used:true, questions:[] },
    { category_id:'c_spc_modify', name:'API 그룹 수정', used:true, questions:[] },
    { category_id:'c_spc_delete', name:'API 그룹 삭제', used:true, questions:[] },
    { category_id:'c_spc_mapping',name:'API ↔ 그룹 매핑', used:true, questions:[] },
    { category_id:'c_spc_owner',  name:'그룹 담당자 지정', used:true, questions:[] },
    { category_id:'c_spc_search', name:'그룹 검색 · 필터', used:false, questions:[] },
    { category_id:'c_spc_export', name:'그룹 목록 내려받기', used:true, questions:[] },
    { category_id:'c_spc_error',  name:'그룹 등록 오류', used:true, questions:[] }
  ]},
  { group_id:'g_tpl', group_name:'템플릿 관리', used:true, categories:[
    { category_id:'c_tpl_create', name:'템플릿 등록', used:true, questions:[] },
    { category_id:'c_tpl_modify', name:'템플릿 수정', used:true, questions:['템플릿을 수정하면 기존 API에도 반영되나요?','템플릿 수정 권한은 누가 갖나요?'] },
    { category_id:'c_tpl_delete', name:'템플릿 삭제', used:true, questions:[] },
    { category_id:'c_tpl_var',    name:'템플릿 변수 사용법', used:true, questions:[] },
    { category_id:'c_tpl_header', name:'요청 헤더 템플릿', used:true, questions:[] },
    { category_id:'c_tpl_body',   name:'요청 본문 템플릿', used:true, questions:[] },
    { category_id:'c_tpl_resp',   name:'응답 템플릿', used:true, questions:[] },
    { category_id:'c_tpl_err',    name:'오류 응답 템플릿', used:true, questions:[] },
    { category_id:'c_tpl_apply',  name:'템플릿 API 적용', used:true, questions:[] },
    { category_id:'c_tpl_copy',   name:'템플릿 복제', used:false, questions:[] },
    { category_id:'c_tpl_history',name:'템플릿 변경 이력', used:true, questions:[] }
  ]},
  { group_id:'g_auth', group_name:'인증 · 권한', used:true, categories:[
    { category_id:'c_auth_key',   name:'API Key 발급', used:true, questions:['API Key는 어디서 발급받나요?','API Key를 재발급하면 기존 키는 어떻게 되나요?'] },
    { category_id:'c_auth_token', name:'액세스 토큰 발급', used:true, questions:[] },
    { category_id:'c_auth_group', name:'권한그룹 관리', used:true, questions:[] },
    { category_id:'c_auth_role',  name:'사용자 역할(Role)', used:true, questions:[] },
    { category_id:'c_auth_ip',    name:'IP 허용 목록', used:true, questions:[] },
    { category_id:'c_auth_scope', name:'스코프(Scope) 설정', used:true, questions:[] },
    { category_id:'c_auth_expire',name:'인증 정보 만료 · 갱신', used:true, questions:[] },
    { category_id:'c_auth_error', name:'401 · 403 오류 대응', used:true, questions:[] }
  ]},
  { group_id:'g_ops', group_name:'운영 · 모니터링', used:true, categories:[
    { category_id:'c_ops_stat',   name:'호출 통계 조회', used:true, questions:[] },
    { category_id:'c_ops_log',    name:'호출 로그 조회', used:true, questions:[] },
    { category_id:'c_ops_limit',  name:'호출량 제한(Quota)', used:true, questions:[] },
    { category_id:'c_ops_alarm',  name:'장애 알림 설정', used:true, questions:[] },
    { category_id:'c_ops_deploy', name:'운영 반영(배포)', used:true, questions:[] },
    { category_id:'c_ops_env',    name:'개발 · 운영 환경 분리', used:true, questions:[] },
    { category_id:'c_ops_sla',    name:'응답 지연 · 타임아웃', used:true, questions:[] },
    { category_id:'c_ops_contact',name:'담당자 문의 · 지원', used:true, questions:[] }
  ]}
];

var QUICK_CATEGORY_IDS = ['c_reg_flow','c_reg_fields','c_spc_create','c_tpl_modify'];

/* ------------------------------------------------------------
   2. 더미 데이터 생성 (규모 검증용)
   ------------------------------------------------------------ */
var ALL_CATS = (function(){
  var a = [];
  $.each(CATEGORY_GROUPS, function(_, g){
    $.each(g.categories, function(_, c){ a.push($.extend({ group_id:g.group_id, group_name:g.group_name }, c)); });
  });
  return a;
})();

function rnd(seed){ var x = Math.sin(seed) * 10000; return x - Math.floor(x); }
function pad(n){ return (n < 10 ? '0' : '') + n; }
function fmtDate(d){ return d.getFullYear() + '-' + pad(d.getMonth()+1) + '-' + pad(d.getDate()); }
function fmtTs(d){ return pad(d.getMonth()+1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()); }

var Q_SEEDS = [
  '권한그룹 뭐 골라요?','API 등록은 어떻게 하나요?','서비스 URI랑 운영 URI 차이가 뭐예요?',
  'API 그룹 먼저 만들어야 하나요?','SPC 코드 규칙 알려주세요','템플릿 수정하면 기존 API도 바뀌나요?',
  'API Key 재발급하면 기존 키는요?','401 오류가 계속 납니다','호출 통계는 어디서 보나요?',
  '엑셀로 여러 개 한 번에 등록되나요?','Swagger 파일로 등록 가능한가요?','타임아웃 최대 몇 초까지 되나요?',
  '운영 반영은 누가 하나요?','호출량 제한 설정 방법','API 삭제하면 복구되나요?',
  '호출 요금이 어떻게 계산되나요?','사내 결재선은 어디서 확인하죠?','담당자 연락처 알려주세요',
  'IP 허용 목록에 대역 등록되나요?','스코프는 꼭 설정해야 하나요?','버전 올리면 기존 호출은요?',
  '테스트 호출은 어디서 하나요?','응답 템플릿 변수 목록 주세요','오류 응답 형식 규격이 있나요?',
  '개발 환경과 운영 환경 분리되나요?','장애 알림은 어디로 오나요?','API 공개 범위를 부서 단위로 줄 수 있나요?'
];
var ANSWER_MD = '**API 그룹(SPC)** 을 먼저 만든 뒤 \'API 등록\' 화면에서 등록을 진행합니다.\n\n1. API Manager > **API 그룹** 메뉴에서 그룹을 등록합니다.\n2. `API 등록` 화면에서 방금 만든 그룹을 선택합니다.\n3. 서비스 URI · 운영 URI · 권한그룹을 입력하고 저장합니다.\n\n- 권한그룹을 비워두면 내부 관리자만 호출할 수 있습니다.\n- 저장 후 **운영 반영**을 해야 운영 환경에서 호출됩니다.';
var ANSWER_MD2 = '**권한그룹(Auth Group)** 은 이 API를 호출할 수 있는 사용자 묶음입니다.\n\n- 사전에 `인증 · 권한` 메뉴에서 만들어 둔 권한그룹만 선택할 수 있습니다.\n- 비워두면 **내부 관리자만** 호출 가능한 상태로 저장됩니다.\n- 등록 후에도 상세 화면에서 변경할 수 있습니다.';

var RESULT_TYPES = ['answer','answer','answer','answer','related_docs','unresolved'];

/* RAG 문서 18건 */
var DOCS = (function(){
  var titles = ['API 등록','API 등록 - 입력 항목 상세 설명','API 등록 오류 코드','퀵 API 등록 가이드',
    'API 일괄 등록(엑셀) 양식','API 그룹(SPC) 등록','API 그룹 운영 규칙','템플릿 관리','템플릿 변수 레퍼런스',
    '요청/응답 템플릿 예제','API Key 발급 및 관리','액세스 토큰 발급','권한그룹 운영 가이드',
    '호출 통계 · 로그 조회','호출량 제한(Quota) 정책','운영 반영(배포) 절차','장애 알림 설정','담당자 문의 채널'];
  return titles.map(function(t, i){
    var c = ALL_CATS[(i * 3) % ALL_CATS.length];
    var d = new Date(2026, 6, 2 + i);
    return {
      doc_id:'doc-' + pad(i+1) + '-' + c.category_id.replace('c_',''),
      title:t, category_id:c.category_id, category_name:c.name,
      updated:fmtDate(d),
      chunks:6 + Math.floor(rnd(i+1) * 40),
      qa_count:Math.floor(rnd(i+7) * 26),
      body:'## ' + t + '\n\n이 문서는 ' + c.name + ' 에 대한 안내입니다.\n\n- 사전 조건: API 그룹(SPC)이 등록되어 있어야 합니다.\n- 권한그룹을 지정하지 않으면 내부 관리자만 호출할 수 있습니다.\n- 저장 이후에도 운영 반영 전까지는 개발 환경에서만 호출됩니다.\n\n### 입력 항목\n\n| 항목 | 설명 |\n| --- | --- |\n| 서비스 URI | 포털에 노출되는 외부 경로 |\n| 운영 URI | 실제 백엔드로 전달되는 내부 경로 |\n| 타임아웃 | 기본 5초, 최대 30초 |\n'
    };
  });
})();

/* QA 항목 84건 */
var QA_ITEMS = (function(){
  var sts = ['done','done','done','wait','wait','hold','unused'];
  var out = [];
  for(var i = 0; i < 84; i++){
    var c = ALL_CATS[(i * 5) % ALL_CATS.length];
    var vn = 5 + Math.floor(rnd(i+2) * 16);
    var vars = [];
    for(var v = 0; v < vn; v++) vars.push(Q_SEEDS[(i + v) % Q_SEEDS.length]);
    var d = new Date(2026, 7, 1 + (i % 14));
    out.push({
      qa_id:'qa-' + pad(i+1),
      question:Q_SEEDS[i % Q_SEEDS.length],
      answer:(i % 2 ? ANSWER_MD2 : ANSWER_MD),
      category_id:c.category_id, category_name:c.name,
      variants:vars,
      hit:Math.floor(rnd(i+3) * 190),
      status:sts[i % sts.length],
      updated:fmtDate(d),
      sources:[DOCS[i % DOCS.length], DOCS[(i + 4) % DOCS.length]]
    });
  }
  return out;
})();

/* ------------------------------------------------------------
   8-A. 사용자 피드백 (요청서 10)
      사용자는 판정자가 아니라 신고자입니다 — 값이 답변 상태를 바꾸지 않습니다.
      대부분은 아무것도 안 누릅니다(null 이 정상입니다).
   ------------------------------------------------------------ */
var FB_REASONS = { mismatch:'질문과 다른 답이에요', wrong:'내용이 틀려요', thin:'설명이 부족해요' };

/* 이력 행에 붙일 평가 — 12행에 한 번 정도만 값이 있습니다 */
function fbForIndex(i){
  if(i % 12 === 3) return { vote:'down', reason:['mismatch','wrong','thin'][i % 3] };
  if(i % 12 === 7) return { vote:'up', reason:'' };
  return null;
}

/* 검수 화면 '사용자 신고' 더미 — 신고가 있는 QA는 소수입니다 */
var FB_REPORTS = {
  'rev-01':[
    { at:'08-17 14:22', q:'권한그룹 설정하려면', score:0.94, reason:'mismatch' },
    { at:'08-17 11:05', q:'그룹 권한 주는 법', score:0.91, reason:'mismatch' },
    { at:'08-16 16:40', q:'권한 어떻게 바꿔요', score:0.93, reason:'wrong' }
  ],
  'rev-03':[
    { at:'08-16 09:12', q:'운영 URI 따로 넣어야 하나요', score:0.88, reason:'thin' }
  ],
  'rev-05':[
    { at:'08-15 17:30', q:'SPC 코드 자리수', score:0.90, reason:'wrong' },
    { at:'08-15 15:02', q:'스펙코드 규칙 알려줘', score:0.87, reason:'mismatch' },
    { at:'08-14 10:41', q:'그룹코드 만드는 규칙', score:0.92, reason:'mismatch' },
    { at:'08-14 09:20', q:'SPC 명명 규칙 문서', score:0.85, reason:'thin' },
    { at:'08-13 18:05', q:'코드 중복되면 어떻게', score:0.89, reason:'wrong' },
    { at:'08-13 11:33', q:'SPC 바꿀 수 있나요', score:0.86, reason:'mismatch' }
  ]
};

/* 질문 이력 240건 */
var HISTORY = (function(){
  var out = [];
  var base = new Date(2026, 7, 14, 18, 0);
  for(var i = 0; i < 240; i++){
    var rt = RESULT_TYPES[Math.floor(rnd(i+11) * RESULT_TYPES.length)];
    var c = rnd(i+5) > 0.35 ? ALL_CATS[(i * 7) % ALL_CATS.length] : null;
    var qa = rt === 'answer' ? QA_ITEMS[(i * 3) % QA_ITEMS.length] : null;
    var score = rt === 'answer' ? 0.90 + rnd(i+13) * 0.09
              : rt === 'related_docs' ? 0.56 + rnd(i+17) * 0.33 : rnd(i+19) * 0.54;
    var d = new Date(base.getTime() - i * 37 * 60000);
    out.push({
      hist_id:'h-' + pad(i+1),
      fb:fbForIndex(i),
      ts:d, ts_txt:fmtTs(d),
      question:Q_SEEDS[i % Q_SEEDS.length],
      result_type:rt,
      matched_qa:qa,
      score:rt === 'unresolved' ? null : Math.round(score * 100) / 100,
      category_id:c ? c.category_id : '', category_name:c ? c.name : '',
      channel:rnd(i+23) > 0.9 ? '포털' : '챗봇',
      is_test:rnd(i+29) > 0.88,
      ticket:rt === 'unresolved' ? 'TCK-20260814-' + (1000 + i) : '',
      related:[DOCS[i % DOCS.length], DOCS[(i+3) % DOCS.length], DOCS[(i+6) % DOCS.length]]
    });
  }
  return out;
})();

/* 질문 묶음 64건 */
var CLUSTERS = (function(){
  var sts = ['new','new','reviewed','generated','applied','excluded'];
  var out = [];
  for(var i = 0; i < 64; i++){
    var hasCat = rnd(i+31) > 0.28;
    var c = hasCat ? ALL_CATS[(i * 11) % ALL_CATS.length] : null;
    var cnt = 3 + Math.floor(rnd(i+37) * 60);
    var hit = i % 5 === 0 ? 0 : Math.round(rnd(i+41) * 100);
    var members = [];
    for(var m = 0; m < Math.min(cnt, 9); m++) members.push(Q_SEEDS[(i + m * 2) % Q_SEEDS.length]);
    out.push({
      cluster_id:'cl-' + pad(i+1),
      question:Q_SEEDS[i % Q_SEEDS.length],
      summary:'같은 뜻의 표현 ' + members.length + '가지가 묶였습니다.',
      count:cnt, hit_rate:hit,
      result_type:hit >= 70 ? 'answer' : (hit > 0 ? 'related_docs' : 'unresolved'),
      category_id:c ? c.category_id : '', category_name:c ? c.name : '미분류',
      status:hit === 0 ? 'new' : sts[i % sts.length],
      has_qa:hit > 0,
      members:members
    });
  }
  return out;
})();

/* ------------------------------------------------------------
   3. 진행 현황 (서버가 GET /api/admin/pipeline/status 로 한 번에 내려줍니다)
   ------------------------------------------------------------ */
var FLOW_DEFAULT = {
  docs:24, unindexed:2,
  drafts:24, draft_at:'08-15 14:20',
  pending:12, hold:0, low_score:3,
  approved:286, recent7:18,
  mismatch:4.2, eval_at:'08-14',
  th_match:0.90, th_related:0.55,
  gen:{ created:38, no_evidence:9, non_korean:2, low_score:3 }
};

/* ------------------------------------------------------------
   4. 검수 큐 (pending 만) — 길이·변형·채점·출처를 섞었습니다
   ------------------------------------------------------------ */
var LONG_ANSWER = (function(){
  var steps = ['API 그룹(SPC)을 먼저 등록합니다.','서비스 URI와 운영 URI를 확인합니다.',
    '권한그룹을 선택합니다. 비워두면 내부 관리자만 호출할 수 있습니다.','타임아웃 값을 정합니다. 기본 5초, 최대 30초입니다.',
    '요청 · 응답 템플릿을 연결합니다.','테스트 호출로 정상 응답을 확인합니다.','공개 범위를 지정합니다.',
    '운영 반영(배포)을 요청합니다.','호출 통계에서 첫 호출을 확인합니다.'];
  var s = '**API 등록은 다음 순서로 진행합니다.**\n\n';
  for(var i = 0; i < steps.length; i++) s += (i+1) + '. ' + steps[i] + '\n';
  s += '\n- 저장 후 **운영 반영**을 해야 운영 환경에서 호출됩니다.\n';
  s += '- 반영 전에는 ' + "`개발 환경`" + '에서만 호출됩니다.\n\n';
  s += '자세한 내용은 담당자에게 문의해 주세요.';
  return s;
})();

var REVIEW_QUEUE = (function(){
  var qs = ['API를 처음 등록하려면 무엇부터 해야 하나요?','권한그룹은 무엇을 뜻하나요?',
    '서비스 URI와 운영 URI의 차이가 무엇인가요?','API 그룹은 어떻게 만드나요?','SPC 코드 규칙이 있나요?',
    '템플릿을 수정하면 기존 API에도 반영되나요?','API Key를 재발급하면 기존 키는 어떻게 되나요?',
    '401 오류가 계속 납니다','호출 통계는 어디서 보나요?','엑셀로 여러 개를 한 번에 등록할 수 있나요?',
    'Swagger 파일로 등록할 수 있나요?','타임아웃은 최대 몇 초까지 되나요?','운영 반영은 누가 하나요?',
    '호출량 제한은 어떻게 설정하나요?'];
  var whys = ['근거 문서와 답변이 일치합니다.','근거가 일부만 확인됩니다.','문서에 없는 내용이 섞여 있습니다.',
    '질문 범위보다 답변이 넓습니다.','표현이 모호합니다.'];
  var vns = [0,15,3,7,1,10,0,4,12,2,6,9,15,5];
  var srcs = [3,0,2,1,3,0,2,3,1,2,0,3,1,2];
  var scores = [4,3,5,4,2,5,4,3,4,5,3,4,5,4];
  return qs.map(function(q, i){
    var c = ALL_CATS[(i * 7) % ALL_CATS.length];
    var vars = [];
    for(var v = 0; v < vns[i]; v++) vars.push(qs[(i + v + 1) % qs.length]);
    var scored = i % 4 !== 3;
    return {
      qa_id:'rev-' + pad(i+1),
      question:q,
      answer:(i % 5 === 1 ? LONG_ANSWER : (i % 2 ? ANSWER_MD2 : ANSWER_MD)),
      category_id:c.category_id, category_name:c.name,
      variants:vars,
      sources:DOCS.slice(i % 6, (i % 6) + srcs[i]),
      score:scored ? scores[i] : null,
      score_model:scored ? 'exaone3.5:7.8b' : '',
      score_why:scored ? whys[i % whys.length] : '',
      note:'',
      reports:FB_REPORTS['rev-' + pad(i+1)] || [],
      hit:Math.floor(rnd(i + 61) * 120),
      created:'08-1' + (i % 6) + ' 14:2' + (i % 6)
    };
  });
})();

var REVIEW_QUEUE_BACKUP = REVIEW_QUEUE.map(function(x){ return JSON.parse(JSON.stringify(x)); });

/* ------------------------------------------------------------
   6. 설치된 모델 목록 (서버가 GET 으로 내려줍니다)
   ------------------------------------------------------------ */
var MODELS = ['gemma4:latest','gemma4:12b','qwen3:14b','llama4:8b','exaone3.5:7.8b'];
var MODEL_DEFAULT = { question:'qwen3:14b', answer:'gemma4:12b', judge:'exaone3.5:7.8b' };

/* ------------------------------------------------------------
   7. 작업 현황 (GET /api/admin/jobs) — 한 번에 하나만 돕니다
   ------------------------------------------------------------ */
var JOB_TITLES = { index:'문서 색인', generate:'QA 생성', evaluate:'품질 평가', upload:'문서 업로드' };
var JOB_STAGES = {
  index:'문서를 청킹하고 임베딩 중… (24건) API 등록',
  generate:'문서에서 QA 생성 중… (24건) API 등록',
  evaluate:'평가 문항을 검색해 판정 중…',
  upload:'문서를 저장하고 색인 중… api/등록.md'
};
var JOB_TABS = { index:'docs', generate:'generate', evaluate:'eval', upload:'docs' };
var JOB_GO_LABELS = { index:'문서 화면으로', generate:'생성 화면으로', evaluate:'평가 화면으로', upload:'문서 화면으로' };

var JOBS_FIXTURE = {
  running:{
    key:'generate', title:'QA 생성', stage:JOB_STAGES.generate,
    percent:62, done:38, total:61,
    model:'질문 qwen3:14b · 답변 gemma4:12b · 채점 exaone3.5:7.8b',
    started_at:'2026-08-16T09:12:00', stopping:false, tab:'generate'
  },
  recent:[
    { key:'index', title:'문서 색인', status:'done', finished_at:'2026-08-16T08:40:00',
      summary:'24건 · 312청크', elapsed:'2분', next:{ label:'QA 생성하기', tab:'generate' } },
    { key:'generate', title:'QA 생성', status:'done', finished_at:'2026-08-16T09:12:00',
      summary:'38건 생성 · 9건 근거없음', elapsed:'14분', next:{ label:'초안 검토하기', tab:'generate' } },
    { key:'evaluate', title:'품질 평가', status:'stopped', finished_at:'2026-08-15T18:40:00',
      summary:'중지됨 (48/120)', elapsed:'', next:{ label:'다시 측정', tab:'eval' } },
    { key:'generate', title:'QA 생성', status:'failed', finished_at:'2026-08-15T14:02:00',
      summary:'LLM 호출이 모두 실패했습니다', elapsed:'1분', next:{ label:'생성 화면으로', tab:'generate' } },
    { key:'upload', title:'문서 업로드', status:'done', finished_at:'2026-08-15T11:20:00',
      summary:'42건 · 건너뜀 7건', elapsed:'6분', next:null }
  ]
};

/* 폴더 등록 더미 — 서버가 몇 건씩 나눠 처리한 결과를 이어 붙입니다 */
var UPLOAD_FIXTURE = (function(){
  var out = [];
  for(var i = 0; i < 42; i++){
    var name = ['api/등록','api/삭제','api/수정','spc/생성','spc/매핑','tpl/변수','auth/key','ops/통계'][i % 8] + (i > 7 ? '-' + i : '');
    var res = i % 11 === 5 ? 'skip' : (i % 13 === 7 ? 'fail' : (i % 3 === 1 ? 'update' : 'create'));
    out.push({
      path:name + '.md',
      doc_id:res === 'skip' ? '' : name.replace(/\//g,'-'),
      result:res,
      chunks:res === 'skip' || res === 'fail' ? null : 5 + Math.floor(rnd(i + 71) * 20),
      note:res === 'skip' ? '중복' : (res === 'fail' ? '임베딩 실패' : '')
    });
  }
  return out;
})();

/* ------------------------------------------------------------
   8. 도움말 문구 (요청서 07) — 서버가 내려주지 않는 화면 상수입니다.
      키는 GET /api/admin/pipeline/status 의 steps[].key 와 같습니다.
      개발이 확정한 문구라 임의로 다듬지 마세요 — 숫자의 의미가 달라집니다.
   ------------------------------------------------------------ */
var HELP_TEXT = {
  documents:'챗봇이 답을 찾는 원본 문서 수입니다.<br>\'모두 색인됨\' 이면 검색에 쓰입니다.<br>문서는 관련 자료 안내에 쓰이고, 답변은 승인된 QA에서 나갑니다.',
  drafts:'AI가 문서를 읽고 만든 질문·답변 후보입니다.<br>아직 사용자에게 나가지 않습니다.<br>검수 대기와 다릅니다 — 초안은 아무도 안 본 상태입니다.',
  pending:'승인만 남은 답변입니다.<br>승인해야 챗봇이 그 답을 씁니다.',
  approved:'지금 챗봇이 실제로 답하는 QA 수입니다.',
  quality:'엉뚱한 답이 나간 비율입니다(오매칭률).<br>낮을수록 좋고, 품질 평가를 돌려야 채워집니다.',
  threshold:'질문이 이만큼 비슷해야 저장된 답을 내보냅니다.<br>높일수록 신중해지고, 낮출수록 자주 답합니다.'
};

/* ------------------------------------------------------------
   9. 납품처 프로필 (data-brand 치환값)
   ------------------------------------------------------------ */
var BRAND = {
  organization:'KT',
  service_name:'API Manager 도우미',
  service_desc:'API 등록 · 그룹 · 템플릿'
};

/* ------------------------------------------------------------ */
$(function(){

  var MODE = $('body').attr('data-mode') || 'serve';
  var PAGE_SIZE = { hist:20, an:20, qa:20, doc:20 };
  var PAGE = { hist:1, an:1, qa:1, doc:1 };
  var SORT = { hist:{ key:'ts', dir:'desc' }, an:{ key:'count', dir:'desc' }, qa:{ key:'hit', dir:'desc' } };
  var FILTER = {
    hist:{ rt:'', cat:'', q:'', fb:'', test:false },
    an:{ f:'', cat:'', sort:'count' },
    qa:{ f:'', cat:'', q:'', sort:'hit' },
    doc:{ q:'' }
  };
  var QUICK = QUICK_CATEGORY_IDS.slice();
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
  function mockSave(key, $dirtyHost, okMsg){
    saveState(key, 'busy');
    setTimeout(function(){
      saveState(key, 'ok');
      if($dirtyHost) $dirtyHost.removeClass('is_dirty');
      if(okMsg) toast(okMsg, 'ok');
    }, 700);
  }

  /* ---------- 진행바 ---------- */
  function progress($p, opt){
    opt = opt || {};
    $p.addClass('is_shown').toggleClass('is_indeterminate', !!opt.indeterminate).toggleClass('is_err', !!opt.error);
    $p.find('.admin_progress_txt').text(opt.text || '');
    $p.find('.admin_progress_pct').text(opt.indeterminate || opt.pct == null ? '' : Math.round(opt.pct) + '%');
    $p.find('.admin_progress_bar').css('width', (opt.indeterminate ? 35 : (opt.pct || 0)) + '%');
  }
  function fakeRun($p, steps, done){
    var i = 0;
    (function tick(){
      if(i >= steps.length){ progress($p, { pct:100, text:'완료' }); if(done) done(); return; }
      progress($p, { pct:(i / steps.length) * 100, text:steps[i] });
      i++;
      setTimeout(tick, 450);
    })();
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
    $('#panel_review').toggleClass('is_readonly', false);
    renderQa(); renderDocs(); renderFlow();
    $('[data-dev="mode-serve"]').toggleClass('is_on', mode === 'serve');
    $('[data-dev="mode-studio"]').toggleClass('is_on', mode === 'studio');
  }

  /* ---------- 사이드바 · 탭 ---------- */
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

  /* ============================================================
     A. 역할별 모델 (요청서 06 · 3번)
     옵션은 마크업에 비워 두고 여기서 채웁니다 — 서버 목록으로 교체하세요.
     ============================================================ */
  function fillModelSelects(){
    var opts = MODELS.map(function(m){ return '<option value="' + m + '">' + esc(m) + '</option>'; }).join('');
    $('#genQuestionModel').html(opts).val(MODEL_DEFAULT.question);
    $('#genAnswerModel').html(opts).val(MODEL_DEFAULT.answer);
    /* 채점 모델은 첫 항목이 '채점 안 함'(빈 값) 입니다 */
    $('#genJudgeModel').html('<option value="">채점 안 함</option>' + opts).val(MODEL_DEFAULT.judge);
    $('#setGenModel').html(opts).val(MODEL_DEFAULT.answer);
    $('#evalModel').html(opts).val(MODEL_DEFAULT.judge);
    renderJudgeHint();
  }
  function renderJudgeHint(){
    var judge = $('#genJudgeModel').val(), answer = $('#genAnswerModel').val();
    var $h = $('#genJudgeHint').removeClass('is_warn');
    if(!judge){ $h.text('채점하지 않습니다. 초안이 점수 없이 검수로 넘어갑니다.'); return; }
    if(judge === answer){ $h.addClass('is_warn').text('답변 모델과 같습니다. 자기 답에 후한 점수를 줍니다.'); return; }
    $h.text('');
  }
  $(document).on('change', '#genJudgeModel, #genAnswerModel', renderJudgeHint);

  /* ============================================================
     C. 작업 현황판 (요청서 06 · 5번)
     한 번에 하나만 돕니다. 폴링 2초, 실행 중이 없으면 멈춥니다.
     ============================================================ */
  var JOBS = { running:null, recent:[] };
  var jobTimer = null, jobOffline = false, jobTick = 0;

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
    var tab = key ? (JOB_TABS[key] || '') : '';
    $('[data-nav-spin]').each(function(){
      var k = $(this).data('nav-spin');
      var on = !!key && (k === key || k === tab);
      $(this).prop('hidden', !on);
    });
  }

  function renderJob(){
    var r = JOBS.running;
    var $j = $('#flowJob');
    if(!r){
      $j.prop('hidden', true).removeClass('is_stopping');
      renderNavSpin();
      renderJobHistory();
      stopJobPolling();
      return;
    }
    $j.prop('hidden', false).toggleClass('is_stopping', !!r.stopping);
    $j.find('.admin_job_title_txt').text((r.title || JOB_TITLES[r.key] || '작업') + ' 중');
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
    $('#flowJobGo').text(JOB_GO_LABELS[r.key] || '작업 화면으로')
      .attr('data-goto-tab', r.tab || JOB_TABS[r.key] || 'flow');
    renderNavSpin();
    renderJobHistory();
  }

  var JOB_ICO = { done:['is_done','✓'], stopped:['is_stopped','⚠'], failed:['is_failed','✕'], running:['is_running','●'] };

  function renderJobHistory(){
    var rows = (JOBS.recent || []).slice(0, 5);
    $('#flowJobHistoryCard').prop('hidden', !rows.length);
    var $w = $('#flowJobHistory').empty();
    /* 지금 할 일 배너와 지시가 둘이면 안 됩니다 — 겹치면 배너가 우선 */
    var bannerOn = !$('#flowTodo').hasClass('is_clear');
    $.each(rows, function(i, r){
      var $r = tpl('tpl_job_row').children().attr('data-job-key', r.key);
      var ico = JOB_ICO[r.status] || JOB_ICO.done;
      $r.addClass(r.status === 'failed' ? 'is_failed' : '');
      $r.find('.admin_job_ico').addClass(ico[0]).text(ico[1]);
      $r.find('.admin_job_row_title').text(r.title || JOB_TITLES[r.key] || '작업');
      $r.find('.admin_job_row_at').text(jobAt(r.finished_at));
      $r.find('.admin_job_row_sum').text(r.summary || '');
      $r.find('.admin_job_row_elapsed').text(r.elapsed || '—');
      /* next 는 서버가 정합니다. 맨 윗줄에만, 배너가 없을 때만 */
      var showNext = i === 0 && !!r.next && !bannerOn;
      $r.toggleClass('has_next', showNext);
      if(showNext){
        $r.find('.admin_job_next').text(r.next.label).attr('data-goto-tab', r.next.tab);
      }
      $w.append($r);
    });
  }

  function startJobPolling(){
    if(jobTimer) return;
    jobTimer = setInterval(pollJobs, 2000);
  }
  function stopJobPolling(){
    if(!jobTimer) return;
    clearInterval(jobTimer); jobTimer = null;
  }
  /* 개발 교체 지점: $.getJSON('/api/admin/jobs') 결과를 JOBS 에 넣고 renderJob() */
  function pollJobs(){
    if(!JOBS.running){ stopJobPolling(); return; }
    if(jobOffline){ renderJob(); return; }
    jobTick++;
    var r = JOBS.running;
    if(!r.stopping && r.total){
      r.done = Math.min(r.total, r.done + 1);
      r.percent = Math.round(r.done / r.total * 100);
      if(r.done >= r.total) finishJob('done', num(r.total) + '건 처리');
    }
    renderJob();
  }
  function finishJob(status, summary){
    var r = JOBS.running;
    if(!r) return;
    JOBS.running = null;
    JOBS.recent.unshift({
      key:r.key, title:r.title || JOB_TITLES[r.key], status:status,
      finished_at:new Date().toISOString(), summary:summary,
      elapsed:jobElapsed(r.started_at).replace(' 경과',''),
      next:{ label:JOB_GO_LABELS[r.key] || '작업 화면으로', tab:r.tab || JOB_TABS[r.key] }
    });
    stopJobPolling();
    renderJob(); renderFlow();
  }

  function startJob(key, opt){
    opt = opt || {};
    JOBS.running = $.extend({
      key:key, title:JOB_TITLES[key], stage:JOB_STAGES[key],
      percent:0, done:0, total:key === 'evaluate' ? 120 : 61,
      model:key === 'generate'
        ? '질문 ' + $('#genQuestionModel').val() + ' · 답변 ' + $('#genAnswerModel').val() +
          ' · 채점 ' + ($('#genJudgeModel').val() || '없음')
        : (key === 'evaluate' ? $('#evalModel').val() : ''),
      started_at:new Date().toISOString(), stopping:false, tab:JOB_TABS[key]
    }, opt);
    jobOffline = false;
    renderJob();
    startJobPolling();
  }

  /* 중지는 확인 모달 없이 바로 — 지금까지 만든 것은 남습니다 */
  $('#flowJobStop').on('click', function(){
    if(!JOBS.running) return;
    JOBS.running.stopping = true;
    renderJob();
    toast('중지를 요청했습니다', 'ok');
    setTimeout(function(){
      if(JOBS.running && JOBS.running.stopping){
        finishJob('stopped', '중지됨 (' + num(JOBS.running.done) + '/' + num(JOBS.running.total) + ')');
      }
    }, 1600);
  });

  /* ============================================================
     도움말 .admin_help (요청서 07)
     클릭으로만 엽니다. 호버로 열면 카드 버튼을 누르러 가는 길에 계속 열립니다.
     ============================================================ */
  function closeHelp(focusBack){
    var $open = $('.admin_help[aria-expanded="true"]');
    if(!$open.length) return;
    $open.attr('aria-expanded','false')
      .siblings('.admin_help_pop').removeClass('is_open is_left');
    if(focusBack) $open.trigger('focus');
  }
  /* 오른쪽 끝 카드는 화면 밖으로 나갑니다 — 넘치면 왼쪽으로 펼칩니다 */
  function placeHelp($pop){
    $pop.removeClass('is_left');
    var r = $pop[0].getBoundingClientRect();
    var edge = $('.admin_main').length
      ? $('.admin_main')[0].getBoundingClientRect().right
      : window.innerWidth;
    if(r.right > edge - 8) $pop.addClass('is_left');
  }
  function openHelp($btn){
    var key = $btn.attr('data-help');
    var $pop = $btn.siblings('.admin_help_pop');
    $pop.find('.admin_help_txt').html(HELP_TEXT[key] || '');
    $btn.attr('aria-expanded','true');
    $pop.addClass('is_open');
    placeHelp($pop);
  }
  /* 한 번에 하나만 — 문서 전역 위임이라 어느 화면에 붙여도 같이 동작합니다 */
  $(document).on('click', '.admin_help', function(e){
    e.preventDefault(); e.stopPropagation();
    var $btn = $(this);
    var wasOpen = $btn.attr('aria-expanded') === 'true';
    closeHelp(false);
    if(!wasOpen) openHelp($btn);
  });
  $(document).on('click', function(e){
    if($(e.target).closest('.admin_help_wrap').length) return;
    closeHelp(false);
  });
  $(document).on('keydown', function(e){
    if(e.key !== 'Escape') return;
    if(!$('.admin_help[aria-expanded="true"]').length) return;
    e.stopPropagation();   /* 모달 ESC 핸들러보다 먼저 처리합니다 */
    closeHelp(true);       /* 포커스를 ? 로 돌려줍니다 */
  });
  $(window).on('resize', function(){
    var $pop = $('.admin_help_pop.is_open');
    if($pop.length) placeHelp($pop);
  });

  /* ---------- 브랜드 치환 (data-brand) ---------- */
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
    $(this).closest('.admin_menu').removeClass('is_open');
    var labels = { topic:'주제를 지정했습니다', exclude:'제외 처리했습니다', mark:'QA 생성 대상으로 표시했습니다',
      gen:'QA 생성을 요청했습니다', approve:'검수 완료 처리했습니다', hold:'보류로 변경했습니다',
      unuse:'사용 안 함으로 변경했습니다' };
    if(act === 'delete'){
      askConfirm('선택한 QA 항목을 삭제할까요?', '삭제하면 되돌릴 수 없습니다.', true, function(){ toast('삭제했습니다', 'ok'); });
      return;
    }
    toast(labels[act] || '처리했습니다', 'ok');
  });

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
  /* 값은 셋뿐입니다 — 👍 / 👎 / –. 대부분은 – 이고 그게 정상입니다. */
  function fbCell(fb){
    if(!fb) return '<span class="admin_fb_none">–</span>';
    if(fb.vote === 'up') return '<span class="admin_fb_badge is_up" title="도움이 됐어요">👍</span>';
    var why = FB_REASONS[fb.reason] || '이유 없음';
    return '<span class="admin_fb_badge is_down" title="' + esc(why) + '">👎</span>';
  }

  function histRows(){
    var f = FILTER.hist;
    var rows = HISTORY.filter(function(r){
      if(!f.test && r.is_test) return false;
      if(f.fb === 'down' && !(r.fb && r.fb.vote === 'down')) return false;
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
        '<td>' + fbCell(r.fb) + '</td>' +
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
  /* 👎만 — 결과 유형 칩과 한 줄에서 배타적으로 동작합니다 */
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
  $('#histExport').on('click', function(){ toast('CSV를 내려받습니다 (' + num(histRows().length) + '건)', 'ok'); });

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

    /* 추이: 14일 */
    var days = [], W = 320, H = 100;
    for(var i = 13; i >= 0; i--){
      var d = new Date(2026, 7, 14 - i);
      var tot = 60 + Math.round(rnd(i+3) * 80), un = Math.round(tot * (0.08 + rnd(i+9) * 0.12));
      days.push({ d:pad(d.getMonth()+1) + '/' + pad(d.getDate()), tot:tot, un:un });
    }
    var max = Math.max.apply(null, days.map(function(x){ return x.tot; })) * 1.15;
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
    $(this).closest('.admin_sub_item').fadeOut(150, function(){ $(this).remove(); });
    toast('묶음에서 제외했습니다', 'ok');
  });
  $('#anBody').on('click', '[data-cl-topic]', function(e){ e.stopPropagation(); toast('주제 지정 팝오버를 엽니다', 'ok'); });
  $('#panel_analytics').on('click', '[data-anf]', function(){
    $('[data-anf]').removeClass('is_active'); $(this).addClass('is_active');
    FILTER.an.f = $(this).data('anf'); PAGE.an = 1; renderAn();
  });
  $('#anSort').on('change', function(){ FILTER.an.sort = $(this).val(); PAGE.an = 1; renderAn(); });

  function runAnalysis(){
    fakeRun($('#anProgress'), ['질문 이력 수집 중…','임베딩 계산 중…','유사 질문 묶는 중…','통계 집계 중…'], function(){
      $('#anLastRun').text('2026-08-14 18:04');
      renderKpis(); renderCharts(); renderAn();
      toast('분석을 완료했습니다', 'ok');
      setTimeout(function(){ $('#anProgress').removeClass('is_shown'); }, 900);
    });
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
  $('#quickSave').on('click', function(){ mockSave('quick', $('#quickCard'), '자주 찾는 주제를 저장했습니다'); });

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
  $('#catSave').on('click', function(){ mockSave('cat', $('#catDetail'), '카테고리를 저장했습니다'); });
  $('#catCancel').on('click', function(){ if(currentCat) selectCategory(currentCat); });
  $('#catDelete').on('click', function(){
    askConfirm('이 카테고리를 삭제할까요?', '추천 질문도 함께 삭제됩니다.', true, function(){ toast('삭제했습니다', 'ok'); });
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
  $('#catGroupSave').on('click', function(){ closeModal($('#catGroupModal')); toast('대분류를 저장했습니다', 'ok'); });
  $('#catGroupDelete').on('click', function(){
    var n = $('#catGroupWarn').find('[data-bind=child_count]').text();
    askConfirm('대분류를 삭제할까요?', '하위 카테고리 ' + n + '개가 함께 사라집니다.', true, function(){
      closeModal($('#catGroupModal')); toast('삭제했습니다', 'ok');
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
     QA 검수 모달과 검수 화면이 같은 마크업 · 같은 함수를 씁니다.
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

  /* 채점이 없으면 0점이 아니라 '채점 없음' 입니다 */
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

  /* 사용자 신고 (요청서 10 C) — 0건이면 영역을 통째로 감춥니다 */
  function renderEdFeedback($host, item){
    var list = (item && item.reports) || [];
    var $w = ed($host,'feedback').prop('hidden', !list.length).removeClass('is_open');
    ed($host,'feedbackToggle').attr('aria-expanded','false');
    if(!list.length) return;

    ed($host,'feedbackCount').text('👎 ' + num(list.length));
    var tally = {};
    $.each(list, function(_, r){ tally[r.reason] = (tally[r.reason] || 0) + 1; });
    ed($host,'feedbackReasons').text($.map(tally, function(n, k){
      return (FB_REASONS[k] || k) + ' ' + n;
    }).join(' · '));

    /* 실제 질문 원문이 보이는 것이 핵심입니다 — 변형 질문을 무엇으로 추가할지 여기서 정합니다 */
    ed($host,'feedbackItems').html(list.slice(0, 5).map(function(r){
      return '<div class="admin_fb_item"><span class="admin_fb_item_at">' + esc(r.at) + '</span>' +
        '<span class="admin_fb_item_q" title="' + esc(r.q) + '">"' + esc(r.q) + '"</span>' +
        '<span class="admin_fb_item_score">' + r.score.toFixed(2) + '</span></div>';
    }).join(''));
    ed($host,'feedbackAll').prop('hidden', list.length <= 5);
    $w.attr('data-report-count', list.length);
  }
  /* 접힘이 기본입니다 — 검수 화면은 이미 세로가 깁니다 */
  $(document).on('click', '.admin_editor [data-ed="feedbackToggle"]', function(){
    var open = $(this).closest('.admin_ed_feedback').toggleClass('is_open').hasClass('is_open');
    $(this).attr('aria-expanded', open ? 'true' : 'false');
  });

  /* 출처 배지 — 누르면 근거 발췌를 접었다 폅니다 */
  function renderEdSources($host, docs){
    var $w = ed($host,'sources').empty();
    $.each(docs, function(_, d){
      var $s = tpl('tpl_src_item').children().attr('data-doc-id', d.doc_id);
      $s.find('.admin_src_name').text(d.title);
      $s.find('.admin_src_excerpt').text(d.body ? d.body.slice(0, 260) : '발췌를 불러오지 못했습니다.');
      $w.append($s);
    });
    if(!docs.length) $w.html('<p class="admin_card_sub">연결된 문서가 없습니다.</p>');
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
    var n = ed($host,'variants').children().length;
    ed($host,'variantCount').text('(' + n + ')');
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

  /* 미리보기는 챗봇 말풍선과 렌더 규칙이 같아야 합니다 */
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
  $(document).on('click', '.admin_editor [data-src-toggle]', function(e){
    if($(e.target).is('[data-tag-remove]')) return;
    $(this).closest('.admin_src_item').toggleClass('is_open');
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
    saveState(key,'busy','변형 질문 생성 중…');
    setTimeout(function(){
      var base = ed($host,'question').val();
      $.each([base + ' 알려주세요', base + ' 방법', base + ' 기준이 뭔가요'], function(_, v){
        edAddVariant($host, v);
      });
      saveState(key, null);
      toast('변형 질문 3개를 생성했습니다', 'ok');
    }, 800);
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
  $('#docPickApply').on('click', function(){
    if(!$pickHost) return closeModal($('#docPickModal'));
    var $w = ed($pickHost,'sources');
    if($w.find('.admin_src_item').length === 0) $w.empty();
    $('#docPickList input:checked').each(function(){
      var id = $(this).val();
      if($w.find('.admin_src_item[data-doc-id="' + id + '"]').length) return;
      var d = DOCS.filter(function(x){ return x.doc_id === id; })[0];
      var $s = tpl('tpl_src_item').children().attr('data-doc-id', id);
      $s.find('.admin_src_name').text(d.title);
      $s.find('.admin_src_excerpt').text(d.body.slice(0, 260));
      $w.append($s);
    });
    closeModal($('#docPickModal'));
    renderEdPreview($pickHost); edDirty($pickHost);
  });

  /* ---------- QA 검수 모달 ---------- */
  function openQaModal(id, override){
    var q = QA_ITEMS.filter(function(x){ return x.qa_id === id; })[0] || QA_ITEMS[0];
    currentQa = q;
    var readonly = MODE !== 'studio' || (override && override.readonly);
    var $m = $('#qaModal').removeClass('is_dirty');
    var $host = mountEditor('qa');

    $('#qaStatus').val((override && override.status) || q.status);
    fillEditor($host, q);

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
  $('#qaSaveBtn').on('click', function(){ mockSave('qa', $('#qaModal'), 'QA 항목을 저장했습니다'); });
  $('#qaApproveBtn').on('click', function(){
    if(mountEditor('qa').find('.is_dup').length){ toast('중복된 변형 질문이 있습니다', 'err'); return; }
    saveState('qa','busy');
    setTimeout(function(){
      saveState('qa','ok','승인했습니다');
      $('#qaStatus').val('done');
      renderEdPreview(mountEditor('qa'));
      $('#qaModal').removeClass('is_dirty');
      toast('검수 완료로 저장했습니다', 'ok');
    }, 700);
  });
  $('#qaDiscardBtn').on('click', function(){
    askConfirm('이 QA 항목을 폐기할까요?', '사용자 답변에서 즉시 제외됩니다.', true, function(){
      closeModal($('#qaModal')); toast('폐기했습니다', 'ok');
    });
  });

  /* ============================================================
     검수 #panel_review — 대기(pending) 한 건씩
     ============================================================ */
  var REV = { list:[], idx:0, cat:'', sort:'score_asc', failNext:false };

  function revRows(){
    var rows = REVIEW_QUEUE.filter(function(r){
      if(REV.cat === '__none') return !r.category_id;
      if(REV.cat) return r.category_id === REV.cat;
      return true;
    });
    var s = REV.sort;
    rows.sort(function(a, b){
      var av = a.score == null ? -1 : a.score, bv = b.score == null ? -1 : b.score;
      if(s === 'score_asc') return av - bv;
      if(s === 'score_desc') return bv - av;
      if(s === 'hit') return b.hit - a.hit;
      if(s === 'fb_desc') return (b.reports || []).length - (a.reports || []).length;
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

    fillEditor(mountEditor('rev'), REV.list[REV.idx]);
    $('#revPrev').prop('disabled', REV.idx === 0);
    applyReviewMode();
  }
  function applyReviewMode(){
    var readonly = $('#panel_review').hasClass('is_readonly');
    var $host = mountEditor('rev');
    $host.find('input, textarea, select, button').prop('disabled', readonly);
    $('#revHold, #revDisable, #revApproveNext').prop('disabled', readonly);
  }

  function revGo(step){
    var n = REV.list.length;
    if(!n) return;
    REV.idx = Math.min(Math.max(0, REV.idx + step), n - 1);
    renderReview();
  }
  /* 저장 실패하면 그 자리에 머무릅니다 — 다음 건으로 넘어가지 않습니다 */
  function revSave(status, label){
    if($('#panel_review').hasClass('is_busy')) return;
    var item = REV.list[REV.idx];
    if(!item) return;
    $('#panel_review').addClass('is_busy');
    saveState('rev','busy');
    setTimeout(function(){
      $('#panel_review').removeClass('is_busy');
      if(REV.failNext){
        REV.failNext = false;
        saveState('rev','err');
        toast('저장하지 못했습니다. 다시 시도해 주세요', 'err');
        return;
      }
      saveState('rev','ok');
      var i = REVIEW_QUEUE.indexOf(item);
      if(i > -1) REVIEW_QUEUE.splice(i, 1);
      toast(label, 'ok');
      renderReview();
      renderFlow();
    }, 700);
  }
  $('#revPrev').on('click', function(){ revGo(-1); });
  $('#revHold').on('click', function(){ revSave('hold', '보류로 저장했습니다'); });
  $('#revDisable').on('click', function(){ revSave('unused', '미사용으로 저장했습니다'); });
  $('#revApproveNext').on('click', function(){
    if(mountEditor('rev').find('.is_dup').length){ toast('중복된 변형 질문이 있습니다', 'err'); return; }
    revSave('approved', '승인했습니다');
  });
  $('#revSort').on('change', function(){ REV.sort = $(this).val(); REV.idx = 0; renderReview(); });

  /* ============================================================
     진행 현황 #panel_flow — 보여주고 보내기만 합니다
     ============================================================ */
  var FLOW = $.extend(true, {}, FLOW_DEFAULT);

  function flowTodo(){
    var f = FLOW;
    if(!f.docs) return { step:1, text:'문서가 없습니다. 먼저 문서를 넣어 주세요.', label:'RAG 문서', tab:'docs' };
    if(f.pending) return { step:3, text:'검수 대기 ' + num(f.pending) + '건. 승인해야 사용자에게 나갑니다.', label:'검수 화면 열기', tab:'review' };
    if(f.drafts) return { step:2, text:'초안 ' + num(f.drafts) + '건이 반영을 기다립니다.', label:'QA 생성', tab:'generate' };
    if(f.mismatch >= 5) return { step:5, text:'검색 오매칭이 ' + f.mismatch + '%입니다. 변형 질문이나 임계값을 손봐야 합니다.', label:'품질 평가', tab:'eval' };
    if(MODE === 'studio') return { step:2, text:'문서에서 QA를 생성할 수 있습니다.', label:'QA 생성', tab:'generate' };
    return null;
  }

  function renderFlow(){
    var f = FLOW, studio = MODE === 'studio';
    var todo = flowTodo();
    var steps = [
      { no:1, key:'documents', title:'문서', value:num(f.docs), sub:f.unindexed ? '미색인 ' + num(f.unindexed) : '모두 색인됨',
        tab:'docs', label:'문서 관리', warn:f.unindexed > 0 },
      { no:2, key:'drafts', title:'초안', value:num(f.drafts), sub:f.draft_at ? f.draft_at + ' 생성' : '생성 이력 없음',
        tab:'generate', label:'생성 시작', studioOnly:true },
      { no:3, key:'pending', title:'검수 대기', value:num(f.pending),
        sub:f.hold ? '보류 ' + num(f.hold) : (f.low_score ? '4점 미만 ' + num(f.low_score) + ' 포함' : '보류 없음'),
        tab:'review', label:'검수하기' },
      { no:4, key:'approved', title:'서비스 중', value:num(f.approved), sub:'최근 7일 +' + num(f.recent7),
        tab:'qa', label:'QA 인덱스' },
      { no:5, key:'quality', title:'품질', value:f.mismatch.toFixed(1) + '%', sub:f.eval_at ? f.eval_at + ' 측정' : '측정 이력 없음',
        tab:'eval', label:'다시 측정', studioOnly:true, warn:f.mismatch >= 5 },
      { no:6, key:'threshold', title:'임계값', value:f.th_match.toFixed(2), sub:'문서 ' + f.th_related.toFixed(2),
        tab:'settings', label:'설정' }
    ];

    closeHelp(false);
    var $w = $('#flowSteps').empty();
    $.each(steps, function(_, s){
      var $s = tpl('tpl_flow_step').children().attr('data-step', s.no);
      var off = !!s.studioOnly && !studio;
      var isTodo = !!todo && todo.step === s.no && !off;
      $s.toggleClass('is_off', off)
        .toggleClass('is_todo', isTodo)
        .toggleClass('is_warn', !isTodo && !off && !!s.warn);
      $s.find('.admin_flow_no').text(s.no);
      /* 순서(①②③)가 아니라 key 로 문구를 찾습니다 — 카드 순서가 바뀌어도 따라갑니다 */
      $s.find('.admin_help').attr('data-help', s.key);
      $s.find('.admin_flow_title_txt').text(s.title);
      $s.find('.admin_flow_flag').text(isTodo ? '★' : (!off && s.warn ? '⚠' : ''));
      $s.find('.admin_flow_value').text(s.value);
      $s.find('.admin_flow_sub').text(s.sub);
      $s.find('.admin_flow_go').text(s.label)
        .attr('data-goto-tab', s.tab)
        .prop('disabled', off)
        .attr('title', off ? '작업용 PC에서 가능합니다' : '');
      $w.append($s);
    });

    var $todo = $('#flowTodo').toggleClass('is_clear', !todo);
    $todo.find('.admin_flow_todo_txt').text(todo ? todo.text : '막힌 곳이 없습니다.');
    $todo.find('[data-flow-go]').text(todo ? todo.label : '')
      .attr('data-goto-tab', todo ? todo.tab : '');

    renderFlowSummary();
    renderNavBadge(REVIEW_QUEUE.length);
    renderJobHistory();   /* 배너가 켜지면 다음 단계 버튼을 숨겁니다 */
  }

  function renderFlowSummary(){
    var g = FLOW.gen;
    var has = !!(g && g.created);
    $('#flowSummaryCard').prop('hidden', !has);
    if(!has) return;
    var drops = [
      { label:'근거없음', n:g.no_evidence },
      { label:'비한국어', n:g.non_korean },
      { label:'4점미만', n:g.low_score }
    ].filter(function(d){ return d.n > 0; });

    var html = '<span class="admin_flow_sum_node">문서 <b>' + num(FLOW.docs) + '</b></span>' +
      '<span class="admin_flow_sum_arrow">──' + num(g.created) + '건 생성──▶</span>';
    if(drops.length){
      html += '<span class="admin_flow_sum_drop">' +
        drops.map(function(d){ return '<span>' + d.label + ' ' + num(d.n) + '</span>'; }).join(' · ') +
        ' 제외</span><span class="admin_flow_sum_arrow">──▶</span>';
    }
    html += '<span class="admin_flow_sum_node">대기 <b>' + num(FLOW.pending) + '</b></span>' +
      '<span class="admin_flow_sum_arrow">──▶</span>' +
      '<span class="admin_flow_sum_node">반영 <b>' + num(FLOW.approved) + '</b></span>';
    $('#flowSummary').html(html);
  }

  $('#flowRefresh').on('click', function(){
    FLOW.pending = REVIEW_QUEUE.length;
    renderFlow();
    toast('현황을 새로 읽었습니다', 'ok');
  });

  /* ---------- 납품처 프로필 ---------- */
  $('#subpanel_profile').on('input change', '.admin_input, .admin_select', function(){
    $('#subpanel_profile .admin_card').addClass('is_dirty');
    $('#profLogoPreview').text($('#profOrg').val().slice(0, 4));
  });
  $('#profSave').on('click', function(){
    BRAND.organization = $('#profOrg').val();
    BRAND.service_name = $('#profName').val();
    BRAND.service_desc = $('#profDesc').val();
    applyBrand();
    mockSave('prof', $('#subpanel_profile .admin_card'), '납품처 정보를 저장했습니다');
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
    currentDoc = d;
    var readonly = MODE !== 'studio';
    $('#docModalTitle').text(readonly ? '문서 보기 (읽기 전용)' : '문서 편집');
    $('#docId').val(d.doc_id).prop('readonly', true);
    $('#docTitle').val(d.title).prop('readonly', readonly);
    $('#docEditor').val(d.body).prop('readonly', readonly);
    $('#docModal').removeClass('is_dirty');
    openModal('docModal');
  }
  /* ============================================================
     B. 폴더 등록 (요청서 06 · 4번)
     한 요청에 다 보내지 않습니다 — 몇 건씩 나눠 보내고 표에 이어 붙입니다.
     ============================================================ */
  var UPL = { rows:[], idx:0, timer:null, skipped:7 };
  var UPL_RESULT = {
    create:['is_done','등록'], update:['is_applied','갱신'],
    skip:['is_hold','건너뜀'], fail:['is_excluded','실패']
  };

  function openUpload(rows, skipped){
    UPL.rows = rows; UPL.idx = 0; UPL.skipped = skipped;
    clearInterval(UPL.timer); UPL.timer = null;
    $('#docUploadSummary').text('md 파일 ' + num(rows.length) + '건을 찾았습니다.' +
      (skipped ? ' (건너뜀 ' + num(skipped) + '건 — md/txt 아님)' : ''));
    $('#docUploadOverwrite').prop('checked', false).prop('disabled', false);
    $('#docUploadBody').empty();
    $('#docUploadProgress').removeClass('is_shown is_err');
    $('#docUploadStartBtn').prop('disabled', false).text('등록 시작');
    openModal('docUploadModal');
  }
  function uploadRow(r){
    var m = UPL_RESULT[r.result];
    return '<tr><td class="admin_td_ellip">' + esc(r.path) + '</td>' +
      '<td class="admin_td_ellip" style="font-family:D2Coding,Consolas,monospace;">' + (r.doc_id ? esc(r.doc_id) : '—') + '</td>' +
      '<td><span class="admin_st ' + m[0] + '">' + m[1] + '</span></td>' +
      '<td class="qr_num">' + (r.chunks == null ? '—' : num(r.chunks)) + '</td>' +
      '<td class="admin_td_ellip">' + esc(r.note || '') + '</td></tr>';
  }
  function runUpload(){
    var total = UPL.rows.length;
    $('#docUploadStartBtn').prop('disabled', true).text('등록 중…');
    $('#docUploadOverwrite').prop('disabled', true);
    startJob('upload', { total:total, stage:JOB_STAGES.upload });
    clearInterval(UPL.timer);
    UPL.timer = setInterval(function(){
      /* 한 번에 3건씩 — 서버 왕복 한 번에 해당합니다 */
      var chunk = UPL.rows.slice(UPL.idx, UPL.idx + 3);
      if(!chunk.length){
        clearInterval(UPL.timer); UPL.timer = null;
        progress($('#docUploadProgress'), { pct:100, text:num(total) + '건 완료' });
        $('#docUploadStartBtn').text('완료');
        var failed = UPL.rows.filter(function(r){ return r.result === 'fail'; }).length;
        toast(failed ? num(total - failed) + '건 등록 · ' + num(failed) + '건 실패' : num(total) + '건을 등록했습니다',
          failed ? 'err' : 'ok');
        if(JOBS.running && JOBS.running.key === 'upload'){
          finishJob(failed ? 'failed' : 'done',
            failed ? num(failed) + '건 실패' : num(total) + '건 · 건너뜀 ' + num(UPL.skipped) + '건');
        }
        return;
      }
      $('#docUploadBody').append(chunk.map(uploadRow).join(''));
      UPL.idx += chunk.length;
      progress($('#docUploadProgress'), {
        pct:UPL.idx / total * 100,
        text:num(total) + '건 중 ' + num(UPL.idx) + '건'
      });
      if(JOBS.running && JOBS.running.key === 'upload'){
        JOBS.running.done = UPL.idx;
        JOBS.running.percent = Math.round(UPL.idx / total * 100);
        JOBS.running.stage = '문서를 저장하고 색인 중… ' + chunk[chunk.length-1].path;
        renderJob();
      }
    }, 320);
  }
  $('#docUploadBtn').on('click', function(){ $('#docUploadInput').trigger('click'); });
  $('#docUploadInput').on('change', function(){
    /* 실제로는 선택한 파일에서 md/txt 만 추립니다 */
    var n = this.files && this.files.length ? this.files.length : 0;
    openUpload(UPLOAD_FIXTURE.slice(0, n ? Math.min(n, 42) : 42), 7);
    $(this).val('');
  });
  $('#docUploadStartBtn').on('click', function(){
    if($(this).prop('disabled')) return;
    runUpload();
  });

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
  $('#docSaveBtn').on('click', function(){ mockSave('doc', $('#docModal'), '문서를 저장했습니다'); });
  $('#docDeleteBtn').on('click', function(){
    askConfirm('이 문서를 삭제할까요?', '연결된 QA의 출처 표기가 사라집니다.', true, function(){
      closeModal($('#docModal')); toast('삭제했습니다', 'ok');
    });
  });

  /* ============================================================
     ⑥ QA 생성
     ============================================================ */
  $('#genDocSel').html(DOCS.map(function(d){ return '<option value="' + d.doc_id + '">' + esc(d.title) + '</option>'; }).join(''));
  $('#genUncoveredCount').text(CLUSTERS.filter(function(c){ return !c.has_qa; }).length);

  var genStop = false;
  $('#genRunBtn').on('click', function(){
    genStop = false;
    $('#genRunBtn').prop('disabled', true);
    $('#genStopBtn').prop('disabled', false);
    var total = 40, i = 0;
    progress($('#genProgress'), { indeterminate:true, text:'모델을 불러오는 중…' });
    setTimeout(function step(){
      if(genStop){
        progress($('#genProgress'), { pct:(i/total)*100, text:'중지됨', error:true });
        $('#genRunBtn').prop('disabled', false); $('#genStopBtn').prop('disabled', true);
        toast('생성을 중지했습니다', 'err');
        return;
      }
      if(i >= total){
        progress($('#genProgress'), { pct:100, text:'완료' });
        $('#genRunBtn').prop('disabled', false); $('#genStopBtn').prop('disabled', true);
        renderGenResult();
        toast('QA 후보 12건을 생성했습니다', 'ok');
        return;
      }
      i += 2;
      progress($('#genProgress'), { pct:(i/total)*100, text:'답변 생성 중… ' + i + ' / ' + total });
      setTimeout(step, 260);
    }, 700);
  });
  $('#genStopBtn').on('click', function(){ genStop = true; });
  /* 탭 안의 진행바와 별개로 작업 현황판에도 올립니다 */
  $('#genRunBtn').on('click', function(){ if(!JOBS.running) startJob('generate'); });
  $('#evalRunBtn').on('click', function(){ if(!JOBS.running) startJob('evaluate'); });
  function renderGenResult(){
    var rows = QA_ITEMS.slice(0, 12);
    $('#genResultBody').html(rows.map(function(q, i){
      return '<tr class="is_clickable" data-qa-id="' + q.qa_id + '">' +
        '<td class="admin_col_check"><input type="checkbox" data-check="gen" checked aria-label="선택"></td>' +
        '<td class="admin_td_ellip"><span class="admin_row_title">' + esc(q.question) + '</span></td>' +
        '<td class="admin_td_ellip">' + esc(plain(q.answer).slice(0, 80)) + '</td>' +
        '<td class="admin_td_ellip">' + esc(q.category_name) + '</td>' +
        '<td class="qr_num">' + q.variants.length + '</td></tr>';
    }).join(''));
    emptyState('gen', false);
    updateGenSel();
  }
  function updateGenSel(){
    var n = $('#genResultBody input:checked').length;
    $('#genSelCount').text(n + '개 선택');
    $('#genApplyBtn').prop('disabled', !n);
  }
  $('#genResultBody').on('change', 'input[type=checkbox]', updateGenSel);
  $('#genResultBody').on('click', 'tr', function(e){
    if($(e.target).is('input[type=checkbox]')) return;
    openQaModal($(this).data('qa-id'));
  });
  $('[data-check-all="gen"]').on('change', function(){
    $('#genResultBody input[type=checkbox]').prop('checked', $(this).is(':checked'));
    updateGenSel();
  });
  $('#genApplyBtn').on('click', function(){
    var n = $('#genResultBody input:checked').length;
    askConfirm(n + '건을 QA 인덱스에 추가할까요?', '추가된 항목은 검수대기 상태가 됩니다.', false, function(){
      toast(n + '건을 추가했습니다', 'ok');
    });
  });
  $('#genTargetRadio').on('change', 'input[type=radio]', function(){
    $('#genTargetRadio .admin_radio_row').removeClass('is_disabled');
  });

  /* ============================================================
     ⑦ 품질 평가
     ============================================================ */
  $('#evalRunBtn').on('click', function(){
    fakeRun($('#evalProgress'), ['평가 문항 추출 중…','검색 실행 중…','판정 모델 호출 중…','집계 중…'], function(){
      renderEval();
      toast('평가를 완료했습니다', 'ok');
      setTimeout(function(){ $('#evalProgress').removeClass('is_shown'); }, 900);
    });
  });
  function renderEval(){
    var n = Number($('#evalCount').val()) || 200;
    var rows = [];
    for(var i = 0; i < Math.min(n, 60); i++){
      var expect = QA_ITEMS[i % QA_ITEMS.length];
      var r = rnd(i + 51);
      var verdict = r > 0.28 ? 'hit' : (r > 0.1 ? 'miss' : 'none');
      rows.push({
        q:Q_SEEDS[i % Q_SEEDS.length],
        expect:expect.question,
        actual:verdict === 'none' ? '—' : (verdict === 'hit' ? expect.question : QA_ITEMS[(i+5) % QA_ITEMS.length].question),
        score:verdict === 'none' ? null : Math.round((0.5 + r * 0.49) * 100) / 100,
        verdict:verdict
      });
    }
    var hit = rows.filter(function(r){ return r.verdict === 'hit'; }).length;
    var miss = rows.filter(function(r){ return r.verdict === 'miss'; }).length;
    var tiles = [
      { label:'적중률 (Top-1)', value:(hit / rows.length * 100).toFixed(1) + '%' },
      { label:'적중률 (Top-3)', value:Math.min(99.9, (hit / rows.length * 100 + 9.4)).toFixed(1) + '%' },
      { label:'오매칭률', value:(miss / rows.length * 100).toFixed(1) + '%' },
      { label:'평가 문항 수', value:num(rows.length) }
    ];
    $('#evalSummary').prop('hidden', false).html(tiles.map(function(t){
      return '<div class="admin_sum" style="cursor:default;"><p class="admin_sum_label">' + t.label + '</p>' +
        '<p class="admin_sum_value">' + t.value + '</p></div>';
    }).join(''));
    var VD = { hit:['is_done','적중'], miss:['is_wait','오매칭'], none:['is_hold','미검색'] };
    $('#evalBody').html(rows.map(function(r){
      return '<tr><td class="admin_td_ellip">' + esc(r.q) + '</td>' +
        '<td class="admin_td_ellip">' + esc(r.expect) + '</td>' +
        '<td class="admin_td_ellip">' + esc(r.actual) + '</td>' +
        '<td class="qr_num">' + (r.score == null ? '—' : r.score.toFixed(2)) + '</td>' +
        '<td><span class="admin_st ' + VD[r.verdict][0] + '">' + VD[r.verdict][1] + '</span></td></tr>';
    }).join(''));
    emptyState('eval', false);
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
  $('#thSave').on('click', function(){ mockSave('th', $('#thCard'), '매칭 설정을 저장했습니다'); });
  $('#thResetBtn').on('click', function(){
    $('#thMatch').val(0.90); $('#thRelated').val(0.55); $('#thRelatedCount').val(3);
    renderZone(); $('#thCard').addClass('is_dirty');
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
  /* 데모용 수신부 — 개발에서는 서버 저장 후 재렌더 */
  $(document).on('admin:reorder', function(e, d){
    toast('순서 변경: ' + d.kind + ' ' + d.fromId + ' → ' + d.toId + ' (' + d.position + ')', 'ok');
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

    /* ===== 개발 교체 지점: 서버 인증 요청 ===== */
    setTimeout(function(){
      var ok = $.trim($authId.val()) === 'admin' && $authPw.val() === 'admin';
      if(ok){
        var expired = $authModal.attr('data-auth-reason') === 'expired';
        closeAuth();
        toast(expired ? '다시 로그인했습니다. 이어서 작업하세요' : '로그인했습니다', 'ok');
        return;
      }
      authFail++;
      /* 아이디는 남기고 비밀번호만 지웁니다 */
      $authPw.val('').attr('type','password');
      $('#authPwToggle').attr('aria-pressed','false').text('보기');
      $authForm.removeClass('is_typing');
      if(authFail >= AUTH_MAX_TRY){ authLock(); return; }
      /* 어떤 아이디가 존재하는지 알려주지 않도록 문구는 항상 하나입니다 */
      authState('error');
      authMsg('아이디 또는 비밀번호가 올바르지 않습니다.');
      $authPw.trigger('focus');
    }, 800);
  });

  /* ---------- 로그아웃 ---------- */
  $('#adminLogout').on('click', function(){
    askConfirm('로그아웃할까요?', '', false, function(){ openAuth('initial'); });
  });

  /* ============================================================
     초기 렌더
     ============================================================ */
  var RENDER = { hist:renderHist, an:renderAn, qa:renderQa, doc:renderDocs };
  mountEditor('qa'); mountEditor('rev');
  fillModelSelects();
  applyBrand();
  renderHist(); renderKpis(); renderCharts(); renderAn();
  renderQuick(); renderTree(''); renderQa(); renderDocs(); renderZone();
  FLOW.pending = REVIEW_QUEUE.length;
  renderReview(); renderFlow(); selectSubtab('matching');
  JOBS = $.extend(true, {}, JOBS_FIXTURE);
  renderJob(); startJobPolling();
  applyMode(MODE);
  selectTab('flow');
  if(location.hash){
    var k = location.hash.slice(1);
    if($('.admin_nav_item[data-tab="' + k + '"]').length) selectTab(k);
  }

  /* ============================================================
     [DEV ONLY] 확인용 상태 목업 — 개발 이식 시 이 블록 전체 삭제
     ============================================================ */
  $('[data-dev-only]').on('click', 'button', function(e){
    e.stopPropagation();
    var k = $(this).data('dev');
    var $card = $('.admin_panel.is_active .admin_card').first();

    if(k === 'mode-serve') applyMode('serve');
    if(k === 'mode-studio') applyMode('studio');

    if(k === 'save-busy'){ saveState('quick','busy'); saveState('cat','busy'); saveState('th','busy'); saveState('qa','busy'); }
    if(k === 'save-ok'){ saveState('quick','ok'); saveState('cat','ok'); saveState('th','ok'); saveState('qa','ok'); }
    if(k === 'save-err'){ saveState('quick','err'); saveState('cat','err'); saveState('th','err'); saveState('qa','err'); }
    if(k === 'dirty'){ $('#quickCard, #catDetail, #thCard, #qaModal, #docModal').addClass('is_dirty'); }

    if(k === 'toast-ok') toast('저장했습니다', 'ok');
    if(k === 'toast-err') toast('저장에 실패했습니다', 'err');

    if(k === 'empty'){
      var key = $('.admin_panel.is_active').attr('id').replace('panel_','');
      var map = { history:'hist', analytics:'an', qa:'qa', docs:'doc', generate:'gen', eval:'eval' };
      if(map[key]){ $('[data-empty="' + map[key] + '"]').addClass('is_shown');
        $('[data-table-wrap="' + map[key] + '"] table').prop('hidden', true); }
    }
    if(k === 'loading'){
      var $l = $('.admin_panel.is_active [data-loading]').addClass('is_shown');
      $('.admin_panel.is_active .admin_table_wrap').hide();
      setTimeout(function(){ $l.removeClass('is_shown'); $('.admin_table_wrap').show(); }, 1600);
    }
    if(k === 'noresult'){ $('.admin_panel.is_active .admin_search').addClass('is_filled is_noresult'); }

    if(k === 'prog-pct') progress($('.admin_panel.is_active .admin_progress').first(), { pct:42, text:'답변 생성 중… 17 / 40' });
    if(k === 'prog-indet') progress($('.admin_panel.is_active .admin_progress').first(), { indeterminate:true, text:'모델을 불러오는 중…' });
    if(k === 'prog-err') progress($('.admin_panel.is_active .admin_progress').first(), { pct:42, text:'실패 — 모델 응답 없음', error:true });

    if(k === 'qa-wait'){ applyMode('studio'); openQaModal('qa-01', { status:'wait' }); }
    if(k === 'qa-done'){ applyMode('studio'); openQaModal('qa-01', { status:'done' }); }
    if(k === 'qa-ro'){ applyMode('serve'); openQaModal('qa-01', { readonly:true }); }
    if(k === 'confirm') askConfirm('선택한 항목을 검수 완료로 처리할까요?', '5건이 변경됩니다.', false, function(){ toast('처리했습니다','ok'); });
    if(k === 'confirm-danger') askConfirm('QA 항목 5건을 삭제할까요?', '삭제하면 되돌릴 수 없습니다.', true, function(){ toast('삭제했습니다','ok'); });
    if(k === 'group-modal'){ selectTab('categories'); openGroupModal('g_reg'); }

    /* ---- 사용자 피드백 ---- */
    if(k === 'fb-rows'){
      selectTab('history');
      $('#histFilters [data-rt=""]').trigger('click');
      toast('👍 · 👎 · – 가 섞인 행입니다', 'ok');
    }
    if(k === 'fb-only-down'){
      selectTab('history');
      if(!$('#histFilters [data-fb="down"]').hasClass('is_active')) $('#histFilters [data-fb="down"]').trigger('click');
    }
    if(k === 'fb-rev-none' || k === 'fb-rev-3'){
      selectTab('review');
      var want = k === 'fb-rev-3' ? 3 : 0;
      var idx = -1;
      $.each(REV.list, function(i, r){
        if(idx < 0 && ((r.reports || []).length === want)) idx = i;
      });
      if(idx > -1){ REV.idx = idx; renderReview(); }
      if(k === 'fb-rev-3') mountEditor('rev').find('[data-ed="feedbackToggle"]').trigger('click');
    }

    /* ---- 도움말 ---- */
    if(k === 'help-open'){
      selectTab('flow');
      $('#flowSteps .admin_flow_step').eq(0).find('.admin_help').trigger('click');
    }
    if(k === 'help-left'){
      selectTab('flow');
      $('#flowSteps .admin_flow_step').eq(5).find('.admin_help').trigger('click');
    }
    /* 긴 문구(①·② 세 줄)와 짧은 문구(④ 한 줄)를 나란히 열어 둡니다 */
    if(k === 'help-long-short'){
      selectTab('flow');
      closeHelp(false);
      $.each([0, 1, 3], function(_, i){
        var $btn = $('#flowSteps .admin_flow_step').eq(i).find('.admin_help');
        openHelp($btn);
      });
    }
    if(k === 'help-close'){ closeHelp(false); }

    /* ---- 작업 상태 5종 ---- */
    if(k === 'job-none'){ selectTab('flow'); JOBS.running = null; jobOffline = false; renderJob(); }
    if(k === 'job-running'){ selectTab('flow'); jobOffline = false; startJob('generate', { done:38, total:61, percent:62 }); stopJobPolling(); }
    if(k === 'job-stopping'){
      selectTab('flow'); jobOffline = false;
      startJob('generate', { done:38, total:61, percent:62 }); stopJobPolling();
      JOBS.running.stopping = true; renderJob();
    }
    if(k === 'job-done'){
      selectTab('flow');
      if(!JOBS.running) startJob('generate', { done:60, total:61, percent:98 });
      stopJobPolling();
      finishJob('done', '38건 생성 · 9건 근거없음');
    }
    if(k === 'job-failed'){
      selectTab('flow');
      if(!JOBS.running) startJob('generate', { done:12, total:61, percent:20 });
      stopJobPolling();
      finishJob('failed', 'LLM 호출이 모두 실패했습니다');
    }
    if(k === 'job-offline'){
      selectTab('flow');
      if(!JOBS.running) startJob('generate', { done:38, total:61, percent:62 });
      stopJobPolling(); jobOffline = true; renderJob();
    }
    /* ---- 작업 종류 4종 ---- */
    if(k.indexOf('job-kind-') === 0){
      selectTab('flow'); jobOffline = false;
      var kind = k.replace('job-kind-','');
      startJob(kind, { done:kind === 'evaluate' ? 48 : 24, percent:40 });
      stopJobPolling();
    }
    /* ---- 최근 작업 건수 ---- */
    if(k === 'hist-0'){ selectTab('flow'); JOBS.recent = []; renderJob(); }
    if(k === 'hist-1'){ selectTab('flow'); JOBS.recent = [$.extend(true, {}, JOBS_FIXTURE.recent[0])]; renderJob(); }
    if(k === 'hist-5'){ selectTab('flow'); JOBS.recent = $.extend(true, [], JOBS_FIXTURE.recent); renderJob(); }
    /* ---- 다음 단계 버튼 ---- */
    if(k === 'next-yes' || k === 'next-no' || k === 'next-clash'){
      selectTab('flow');
      if(!JOBS.recent.length) JOBS.recent = $.extend(true, [], JOBS_FIXTURE.recent);
      JOBS.recent[0].next = k === 'next-no' ? null : { label:'QA 생성하기', tab:'generate' };
      /* 겹침: 배너가 뜨는 상태(검수 대기 있음)로 만들어 버튼이 숨는지 봅니다 */
      FLOW = $.extend(true, {}, FLOW_DEFAULT);
      if(k === 'next-clash'){ FLOW.pending = 12; }
      else { applyMode('serve'); FLOW.pending = 0; FLOW.drafts = 0; FLOW.mismatch = 2.1; }
      renderFlow(); renderJob();
    }
    /* ---- 폴더 등록 ---- */
    if(k === 'upl-running'){
      applyMode('studio'); selectTab('docs');
      openUpload(UPLOAD_FIXTURE.slice(0, 42), 7);
      runUpload();
      setTimeout(function(){ clearInterval(UPL.timer); UPL.timer = null; }, 1400);
    }
    if(k === 'upl-done'){
      applyMode('studio'); selectTab('docs');
      var okRows = UPLOAD_FIXTURE.slice(0, 42).map(function(r){
        return $.extend({}, r, r.result === 'fail' ? { result:'create', note:'', chunks:9 } : {});
      });
      openUpload(okRows, 7);
      $('#docUploadBody').html(okRows.map(uploadRow).join(''));
      progress($('#docUploadProgress'), { pct:100, text:num(okRows.length) + '건 완료' });
      $('#docUploadStartBtn').prop('disabled', true).text('완료');
      $('#docUploadOverwrite').prop('disabled', true);
    }
    if(k === 'upl-partial'){
      applyMode('studio'); selectTab('docs');
      openUpload(UPLOAD_FIXTURE.slice(0, 42), 7);
      $('#docUploadBody').html(UPLOAD_FIXTURE.slice(0, 42).map(uploadRow).join(''));
      progress($('#docUploadProgress'), { pct:100, text:'42건 완료 · 3건 실패', error:true });
      $('#docUploadStartBtn').prop('disabled', true).text('완료');
      $('#docUploadOverwrite').prop('disabled', true);
    }
    /* ---- 모델 힌트 3상태 ---- */
    if(k.indexOf('hint-') === 0){
      applyMode('studio'); selectTab('generate');
      if(k === 'hint-same'){ $('#genJudgeModel').val($('#genAnswerModel').val()); }
      if(k === 'hint-none'){ $('#genJudgeModel').val(''); }
      if(k === 'hint-ok'){ $('#genJudgeModel').val(MODEL_DEFAULT.judge); $('#genAnswerModel').val(MODEL_DEFAULT.answer); }
      renderJudgeHint();
    }

    /* 진행 현황 칸 상태 4종 — 모든 칸에 강제로 걸어 봅니다 */
    if(k === 'flow-ok' || k === 'flow-warn' || k === 'flow-todo' || k === 'flow-off'){
      selectTab('flow');
      if(k === 'flow-off'){ applyMode('serve'); }
      else {
        renderFlow();
        var cls = { 'flow-ok':'', 'flow-warn':'is_warn', 'flow-todo':'is_todo' }[k];
        $('#flowSteps .admin_flow_step').removeClass('is_warn is_todo is_off');
        $('#flowSteps .admin_flow_flag').text('');
        if(cls){
          $('#flowSteps .admin_flow_step').addClass(cls);
          $('#flowSteps .admin_flow_flag').text(cls === 'is_todo' ? '★' : '⚠');
        }
      }
    }
    /* 지금 할 일 6가지 */
    if(k.indexOf('todo-') === 0){
      selectTab('flow');
      FLOW = $.extend(true, {}, FLOW_DEFAULT);
      if(k === 'todo-pending'){ FLOW.pending = 12; }
      if(k === 'todo-drafts'){ FLOW.pending = 0; FLOW.drafts = 7; }
      if(k === 'todo-nodraft'){ applyMode('studio'); FLOW.pending = 0; FLOW.drafts = 0; FLOW.draft_at = ''; FLOW.mismatch = 2.1; }
      if(k === 'todo-mismatch'){ FLOW.pending = 0; FLOW.drafts = 0; FLOW.mismatch = 8.4; }
      if(k === 'todo-nodocs'){ FLOW.docs = 0; FLOW.unindexed = 0; FLOW.drafts = 0; FLOW.pending = 0; FLOW.gen.created = 0; }
      if(k === 'todo-clear'){ applyMode('serve'); FLOW.pending = 0; FLOW.drafts = 0; FLOW.mismatch = 2.1; }
      renderFlow();
    }
    /* 검수 */
    if(k === 'rev-empty'){ selectTab('review'); REVIEW_QUEUE.length = 0; renderReview(); renderFlow(); }
    if(k === 'rev-loading'){
      selectTab('review');
      $('[data-loading="rev"]').addClass('is_shown');
      $('#revForm, #revActions').prop('hidden', true);
      setTimeout(function(){ $('[data-loading="rev"]').removeClass('is_shown'); renderReview(); }, 1600);
    }
    if(k === 'rev-busy'){
      selectTab('review');
      $('#panel_review').addClass('is_busy'); saveState('rev','busy');
      setTimeout(function(){ $('#panel_review').removeClass('is_busy'); saveState('rev', null); }, 2000);
    }
    if(k === 'rev-fail'){ selectTab('review'); REV.failNext = true; $('#revApproveNext').trigger('click'); }
    if(k === 'rev-ro'){ selectTab('review'); $('#panel_review').addClass('is_readonly'); applyReviewMode(); }
    if(k === 'rev-restore'){
      REVIEW_QUEUE.length = 0;
      [].push.apply(REVIEW_QUEUE, REVIEW_QUEUE_BACKUP.map(function(x){ return $.extend(true, {}, x); }));
      $('#panel_review').removeClass('is_readonly is_busy');
      REV.idx = 0; saveState('rev', null);
      selectTab('review'); renderReview(); renderFlow();
    }
    /* 브랜드 */
    if(k === 'brand-long'){
      BRAND = { organization:'대한민국표준연구원', service_name:'전사 오픈API 통합관리 지원 도우미 서비스', service_desc:'API 등록 · 그룹 · 템플릿 · 인증 · 운영' };
      $('#profOrg').val(BRAND.organization); $('#profName').val(BRAND.service_name); $('#profDesc').val(BRAND.service_desc);
      applyBrand(); toast('긴 이름으로 바꿨습니다', 'ok');
    }
    if(k === 'brand-default'){
      BRAND = { organization:'KT', service_name:'API Manager 도우미', service_desc:'API 등록 · 그룹 · 템플릿' };
      $('#profOrg').val(BRAND.organization); $('#profName').val(BRAND.service_name); $('#profDesc').val(BRAND.service_desc);
      applyBrand();
    }

    if(k === 'auth-initial') openAuth('initial');
    if(k === 'auth-expired'){ applyMode('studio'); selectTab('qa'); openAuth('expired'); }
    if(k === 'auth-typing'){ openAuth('initial'); $authId.val('admin'); $authPw.val('1234'); authTyping(); }
    if(k === 'auth-busy'){ openAuth('initial'); $authId.val('admin'); $authPw.val('1234'); authTyping(); authState('busy'); }
    if(k === 'auth-error'){
      openAuth('initial'); $authId.val('admin'); authFail = 1;
      authState('error'); authMsg('아이디 또는 비밀번호가 올바르지 않습니다.');
    }
    if(k === 'auth-locked'){ openAuth('initial'); $authId.val('admin'); authFail = AUTH_MAX_TRY; authLock(); }
    if(k === 'auth-caps'){ openAuth('initial'); $authForm.addClass('is_caps'); }
    if(k === 'auth-close') closeAuth();

    if(k === 'drag'){
      selectTab('categories');
      var $items = $('#quickChips .admin_tag');
      $items.eq(0).addClass('is_dragging');
      $items.eq(2).attr('data-drop-position','before');
      setTimeout(function(){ $items.removeClass('is_dragging').removeAttr('data-drop-position'); }, 2500);
    }
    if(k === 'reset'){
      $('.admin_toast').remove();
      closeAuth();
      $('.qr_modal_backdrop').removeClass('is_open');
      $('.is_dirty').removeClass('is_dirty');
      $('.admin_save_state').removeClass('is_busy is_ok is_err');
      $('.admin_progress').removeClass('is_shown is_err is_indeterminate');
      $('.admin_search').removeClass('is_noresult');
      $('.admin_table_wrap').show();
      $('[data-loading]').removeClass('is_shown');
      FILTER.hist = { rt:'', cat:'', q:'', fb:'', test:false };
      FILTER.qa = { f:'', cat:'', q:'', sort:'hit' };
      FILTER.an = { f:'', cat:'', sort:'count' };
      FILTER.doc = { q:'' };
      $('.admin_search_input').val('').closest('.admin_search').removeClass('is_filled');
      $('.admin_chip').removeClass('is_active');
      $('[data-rt=""], [data-anf=""], [data-qaf=""]').addClass('is_active');
      REVIEW_QUEUE.length = 0;
      [].push.apply(REVIEW_QUEUE, REVIEW_QUEUE_BACKUP.map(function(x){ return $.extend(true, {}, x); }));
      $('#panel_review').removeClass('is_readonly is_busy');
      REV = { list:[], idx:0, cat:'', sort:'score_asc', failNext:false };
      $('#revSort').val('score_asc');
      FLOW = $.extend(true, {}, FLOW_DEFAULT);
      FLOW.pending = REVIEW_QUEUE.length;
      JOBS = $.extend(true, {}, JOBS_FIXTURE);
      jobOffline = false;
      clearInterval(UPL.timer); UPL.timer = null;
      fillModelSelects();
      renderHist(); renderAn(); renderQa(); renderDocs(); renderReview(); renderFlow();
      renderJob(); startJobPolling();
    }
  });
  /* ==================== [DEV ONLY] end ==================== */

});
