/* ============================================================
   API Manager 도우미 — 사용자 챗봇 화면 (jQuery)

   퍼블 산출물(퍼블/채팅 디자인 퍼블 완료/chat.js)을 이식한 것이다.
   더미 데이터(CATEGORY_GROUPS / DOC_FIXTURES / MOCK_ANSWER)와 목업 바는 걷어내고
   서버 API 호출로 바꿨다. 화면 구조·클래스·템플릿은 산출물 그대로 둔다 —
   퍼블이 화면을 다시 손보면 그 파일을 여기에 다시 얹을 수 있어야 하기 때문이다.

   2026-08-17 산출물에서 옮긴 것: 인트로 주제 펼침(요청서 09) · 답변 피드백(요청서 10).
   **파일을 통째로 덮지 않는다.** 산출물에는 서버 배선이 없고, 우리가 고친 것이 옛 모습으로
   되돌아와 있다 — 이번 것에는 자동 스크롤 판정(`pushed`)을 말풍선 붙인 뒤로 되돌린 코드와
   `pushRelated` 의 `chunk_id` 배선이 빠진 채로 들어 있었다. diff 로 `+` 줄만 골라 넣는다.
   ============================================================ */

var API = {
  ask:        '/api/ask',
  support:    '/api/support',
  categories: '/api/categories',
  chunk:      '/api/docs/chunk/',
  doc:        '/api/docs/',
  docImage:   '/api/docs/img/',
  feedback:   '/api/feedback'
};

/* 서버에서 채운다. 응답 전에는 빈 배열이라 팝오버가 '결과 없음'으로 보인다. */
var CATEGORY_GROUPS = [];
var QUICK_CATEGORY_IDS = [];

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
  /* 인트로 펼침 — 아래 팝오버와 같은 마크업을 그 자리에서 쓴다 */
  var $more        = $('#chatCatMore');
  var $introCats   = $('#chatIntroCats');
  var $introList   = $('#chatIntroCatList');
  var $introSearch = $('#chatIntroCatSearch');
  var $qBtn     = $('#chatCatQBtn');
  var $qList    = $('#chatCatQuestions');
  var $modal    = $('#chatDocModal');
  var $reset    = $('#chatReset');
  var $toBottom = $('#chatToBottom');
  var $live     = $('#chatLive');

  var selected = null;   /* {category_id, name} */
  var waiting  = false;
  var BOTTOM_GAP = 160;   /* 이 거리 이상 떨어졌을 때만 [맨 아래로] 노출 */

  /* ---------- 유틸 ---------- */
  /* 렌더러는 markdown.js 로 합쳤다 - admin.js 의 검수 미리보기와 같은 함수를 써야
     사용자가 보는 답변과 검수 화면이 어긋나지 않는다. 여기서는 별칭만 둔다. */
  var esc = ChatMD.esc;
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

  /* ---------- 마크다운 렌더 ----------
     구현은 markdown.js(ChatMD) 에 있다. 답변 말풍선은 이미지를 그리지 않고(renderAnswer),
     출처 모달만 이미지를 그린다(renderDoc). 문서 이미지 경로는 화면마다 베이스가 달라
     아래에서 넣어준다. */
  ChatMD.configure({ imageBase: API.docImage });
  var inline = ChatMD.inline;
  function renderMarkdown(src){ return ChatMD.renderAnswer(src); }
  function renderDoc(src){ return ChatMD.renderDoc(src); }

  /* ---------- 인트로 칩 ---------- */
  /* 주제가 하나도 없는 설치처가 있다 — 그때는 칩·소제목·[전체 주제 보기]·아래 트리거가
     함께 숨는다. 주제는 검색 힌트일 뿐이라 없어도 질문은 계속 되어야 한다. */
  function updateCatVisibility(){
    var total = 0;
    $.each(CATEGORY_GROUPS, function(_, g){ total += (g.categories || []).length; });
    var none = total === 0;
    if(none) closeIntroCats();
    $('.chat_intro_sub, #chatCatQuick, #chatCatMore').prop('hidden', none);
    $trigWrap.prop('hidden', none);
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
     서버 응답(/api/categories)으로 매번 다시 그린다. 개수도 여기서 채운다 —
     설치처마다 대분류·주제 개수가 달라서 마크업에 박아 둘 수 없다. */
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

    /* 검색어가 없으면 첫 대분류만 펼친다 — 대분류 5줄만 보이면 "목록이 비었다"로 읽힌다.
       하위가 어떻게 생겼는지 한 번 보여줘야 나머지도 눌러 본다(요청서 09 3번). */
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

  /* ---------- 인트로 펼침 (요청서 09 A안) ----------
     팝오버 하나를 두고 좌표를 계산하지 않았다. 이 목록이 뜨는 자리가 스크롤되는 대화
     영역 안이라, 스크롤·리사이즈마다 위치를 다시 잡아야 한다. 마크업을 한 벌 더 두는
     편이 단순하다 — 목록을 그리는 함수(buildCatList)는 하나로 공유한다. */
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

  /* 말풍선을 **붙이기 전에** 하단에 있었는지 잰다.
     퍼블 산출물은 붙인 뒤에 쟀는데, 그러면 답변이 160px보다 길 때 방금 붙인 말풍선 높이 때문에
     '하단이 아님'으로 판정되어 하단에서 기다리던 사용자에게 자동 스크롤이 안 된다. */
  function pushed(isBotAnswer, wasBottom){
    updateReset();
    if(wasBottom){ scrollBottom(); }
    else if(isBotAnswer){ $toBottom.addClass('is_new'); }
    updateToBottom();
  }

  function pushUser(question, category){
    var wasBottom = atBottom();
    hideIntro();
    var $m = tpl('tpl_user');
    if(category){ $m.find('.chat_msg_cat').text('＃ ' + category.name); }
    else { $m.find('.chat_msg_cat').remove(); }   /* 미선택 시 배지 제거 */
    $m.find('[data-bind=question]').text(question);
    $inner.append($m);
    pushed(false, wasBottom);
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
    var wasBottom = atBottom();
    hideIntro();
    var $m = tpl('tpl_answer');
    /* 피드백이 어느 응답에 대한 것인지는 질문 이력의 log_id 로 잇는다. 화면이 질문 글자를
       다시 보내면 같은 질문을 두 번 한 경우를 구분할 수 없다. */
    $m.find('.chat_bubble').attr('data-log-id', data.log_id || '');
    $m.find('[data-bind=answer]').html(renderMarkdown(data.answer));
    if(data.source_docs && data.source_docs.length){
      $m.find('[data-bind=source_docs]').append(srcBadges(data.source_docs));
    } else {
      $m.find('.chat_src').remove();
    }
    $inner.append($m);
    pushed(true, wasBottom);
  }

  function pushRelated(docs, question){
    var wasBottom = atBottom();
    hideIntro();
    var $m = tpl('tpl_related');
    var $wrap = $m.find('[data-bind=related_docs]');
    $.each((docs || []).slice(0,3), function(_, d){
      var $c = tpl('tpl_related_item');
      $c.find('.chat_rel_title_txt').text(d.title);
      $c.find('.chat_rel_section').text(d.section);
      $c.find('.chat_rel_excerpt').text(d.excerpt);
      /* 관련 문서는 청크 단위로 찾았으므로 청크 id 로 연다 — 문서 첫머리가 아니라
         실제로 걸린 절을 보여줘야 "왜 이 문서지?" 라는 의문이 안 생긴다. */
      $c.find('[data-doc-open]').attr('data-chunk-id', d.chunk_id).attr('data-doc-id', d.doc_id);
      if(d.url_or_ref) $c.find('[data-doc-open]').attr('data-ref', d.url_or_ref);
      $wrap.append($c);
    });
    /* 담당자 문의 버튼이 어떤 질문을 접수할지 기억해 둔다. */
    $m.find('[data-ask-support]').attr('data-question', question || '');
    $inner.append($m);
    pushed(true, wasBottom);
  }

  function pushUnresolved(message, ticketId){
    var wasBottom = atBottom();
    hideIntro();
    var $m = tpl('tpl_unresolved');
    $m.find('[data-bind=message]').text(message || '문의가 담당자에게 접수되었습니다.');
    $m.find('[data-bind=ticket_id]').text(ticketId || newTicketId());
    $inner.append($m);
    pushed(true, wasBottom);
  }

  function pushError(question){
    var wasBottom = atBottom();
    hideIntro();
    var $m = tpl('tpl_error');
    $m.find('[data-retry]').attr('data-question', question || '');
    $inner.append($m);
    pushed(true, wasBottom);
  }

  function pushLoading(){
    var wasBottom = atBottom();
    hideIntro();
    $inner.append(tpl('tpl_loading'));
    pushed(false, wasBottom);
    setWaiting(true);
  }
  function popLoading(){
    $inner.find('.chat_msg_loading').remove();
    setWaiting(false);
  }

  /* ---------- 응답 분기 ----------
     result_type 은 서버가 정한다. 화면이 유사도를 보고 다시 판단하지 않는다 —
     임계값이 두 곳에 흩어지면 관리자 설정과 실제 동작이 조용히 어긋난다. */
  function render(data, question){
    if(data.result_type === 'related_docs'){ pushRelated(data.related_docs, question); return; }
    if(data.result_type === 'unresolved'){ pushUnresolved(data.message, data.ticket_id); return; }
    pushAnswer(data);
  }

  /* ---------- 전송 ---------- */
  function submit(text){
    var q = $.trim(text != null ? text : $input.val());
    if(!q || waiting) return;
    pushUser(q, selected);
    $input.val('');
    closePopover(); closeQuestions();
    pushLoading();

    $.ajax({
      url: API.ask, method: 'POST', contentType: 'application/json',
      data: JSON.stringify({ question: q, category_id: selected ? selected.category_id : null })
    })
    .done(function(data){ popLoading(); render(data, q); })
    .fail(function(){ popLoading(); pushError(q); });
  }

  /* ---------- 문서 모달 ---------- */
  function showDoc(d){
    $modal.find('[data-bind=doc_title]').text(d.title || '');
    $modal.find('[data-bind=doc_section]').text(d.section || '');
    /* 원문 글자를 그대로 뿌리면 `![...](...)` 가 화면에 찍힌다. 문서 쪽만 렌더한다. */
    $modal.find('[data-bind=doc_excerpt]').html(renderDoc(d.text || ''));
    var $link = $modal.find('[data-bind=doc_ref]');
    if(d.url_or_ref){ $link.removeClass('is_hidden').attr('href', d.url_or_ref); }
    else { $link.addClass('is_hidden'); }
    $modal.addClass('is_open');
    $modal.find('.chat_doc_close').trigger('focus');
  }
  function openDoc($btn){
    var chunkId = $btn.attr('data-chunk-id');
    var docId   = $btn.attr('data-doc-id');
    var url = chunkId ? API.chunk + encodeURIComponent(chunkId)
                      : API.doc + encodeURIComponent(docId || '');
    $.getJSON(url)
      .done(showDoc)
      .fail(function(){
        showDoc({ title: $btn.text() || '문서', section: '', text: '문서를 불러오지 못했습니다.' });
      });
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

  $more.on('click', function(e){ e.stopPropagation(); toggleIntroCats(); });
  $introCats.on('click', function(e){ e.stopPropagation(); });
  $(document).on('click', '.chat_cat_quick_chip', function(){
    setCategory($(this).data('category-id'));
  });

  /* 인트로 목록 — 아래 팝오버와 같은 조작이다 */
  $introList.on('click', '.chat_cat_group_head', function(){
    var $g = $(this).closest('.chat_cat_group').toggleClass('is_open');
    $(this).attr('aria-expanded', $g.hasClass('is_open') ? 'true' : 'false');
  });
  $introList.on('click', '.chat_cat_item', function(){
    setCategory($(this).attr('data-category-id'));   /* 아래 트리거도 함께 선택 상태가 된다 */
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
      if(i <= 0){ $introList.find('.is_focus').removeClass('is_focus'); $introSearch.trigger('focus'); }
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
  /* 팝오버와 인트로 목록이 함께 쓴다 — 어느 목록인지는 항목이 들고 있다 */
  function moveFocus($items, i){
    if(i < 0 || i >= $items.length) return;
    $items.closest('.chat_cat_list').find('.is_focus').removeClass('is_focus');
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

  $(document).on('click', '[data-doc-open]', function(){ openDoc($(this)); });

  $(document).on('click', '[data-ask-support]', function(){
    var $btn = $(this).prop('disabled', true);
    /* 접수번호는 서버가 만든다. 화면에서 만들면 이력에 남은 번호와 사용자가 본 번호가
       달라져, 담당자가 번호로 찾을 수 없게 된다. */
    $.ajax({
      url: API.support, method: 'POST', contentType: 'application/json',
      data: JSON.stringify({ question: $btn.attr('data-question') || '', category_id: selected ? selected.category_id : null })
    })
    .done(function(data){ pushUnresolved(data.message, data.ticket_id); })
    .fail(function(){ $btn.prop('disabled', false); pushError($btn.attr('data-question')); });
  });

  $(document).on('click', '[data-retry]', function(){
    var q = $(this).attr('data-question');
    $(this).closest('.chat_msg').remove();
    /* 사용자 말풍선은 이미 위에 남아 있으므로 다시 그리지 않고 요청만 보낸다. */
    if(!q) return;
    pushLoading();
    $.ajax({
      url: API.ask, method: 'POST', contentType: 'application/json',
      data: JSON.stringify({ question: q, category_id: selected ? selected.category_id : null })
    })
    .done(function(data){ popLoading(); render(data, q); })
    .fail(function(){ popLoading(); pushError(q); });
  });
  $(document).on('click', '.chat_ticket_copy', function(){
    var $btn = $(this), txt = $btn.closest('.chat_ticket').find('.chat_ticket_id').text();
    var ta = document.createElement('textarea');
    ta.value = txt; document.body.appendChild(ta); ta.select();
    try{ document.execCommand('copy'); }catch(err){}
    document.body.removeChild(ta);
    $btn.addClass('is_done').text('복사됨');
    setTimeout(function(){ $btn.removeClass('is_done').text('복사'); }, 1500);
  });

  $modal.on('click', function(e){ if(e.target === this) closeDoc(); });
  $modal.find('.chat_doc_close').on('click', closeDoc);

  $(document).on('click', function(){ closePopover(); closeQuestions(); closeIntroCats(); });
  $(document).on('keydown', function(e){
    if(e.key !== 'Escape') return;
    if($modal.hasClass('is_open')) closeDoc();
    else if($pop.hasClass('is_open')) closePopover();
    else if($introCats.hasClass('is_open')){ closeIntroCats(); $more.trigger('focus'); }
    else if($qList.hasClass('is_open')) closeQuestions();
  });

  /* ---------- 새 대화 (#chatReset) ----------
     서버에 대화 상태가 없다(질문마다 독립 검색). 화면의 말풍선을 지우는 것이 전부다. */
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
    /* 접수번호는 사용자가 담당자에게 불러 줘야 하는 값이라, 지우면 다시 볼 수 없다.
       이 경우에만 확인한다. */
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
  /* 화면에 보이는 글자 그대로 — 마크다운 기호·출처·검수 문구는 뺀다.
     `**굵게**` 가 그대로 붙으면 메신저에 지저분하게 들어간다. */
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
  $(document).on('click', '[data-copy]', function(){
    var $btn = $(this);
    flashCopy($btn, copyText(bubbleText($btn.closest('.chat_bubble').find('.chat_md'))));
  });

  /* ============================================================
     답변 피드백 (요청서 10 A)

     **사용자는 판정자가 아니라 신고자다.** 여기서 보낸 값은 답변 상태를 바꾸지 않는다 —
     관리자 화면의 정렬·표시에만 쓰인다. 사용자 클릭이 승인 상태를 바꾸면
     '검수한 답변만 나간다'는 이 제품의 전제가 무너진다.

     저장은 자동이고, **실패해도 화면을 멈추지 않는다.** 피드백은 덤이라 그것 때문에
     답변 읽기가 방해받으면 안 된다. 실패하면 조용히 이전 상태로 되돌린다.
     ============================================================ */
  function sendFeedback($bubble, payload, ok, fail){
    var logId = $bubble.attr('data-log-id');
    /* log_id 가 없으면 서버가 어느 응답인지 모른다. 조용히 성공 처리해서 화면만 움직인다 */
    if(!logId){ ok(); return; }
    $.ajax({
      url: API.feedback, method: 'POST', contentType: 'application/json',
      data: JSON.stringify($.extend({ log_id: logId }, payload))
    }).done(ok).fail(fail);
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
    var $btn    = $(this);
    var $bubble = $btn.closest('.chat_bubble');
    var kind    = $btn.attr('data-fb');
    var wasOn   = $btn.hasClass('is_on');
    var prev    = $bubble.find('.chat_fb_btn.is_on').attr('data-fb') || '';

    fbReset($bubble);
    $bubble.find('.chat_fb_done').removeClass('is_shown');
    /* 다시 누르면 취소, 👍↔👎 도 바꿀 수 있다 — 마지막에 고른 것만 유효하다.
       잘못 누르는 일이 잦아서 한 번 누르면 잠그는 방식은 쓰지 않는다. */
    var next = wasOn ? '' : kind;
    if(next){ $btn.addClass('is_on').attr('aria-pressed','true'); }

    sendFeedback($bubble, { vote: next }, function(){
      if(!next) return;
      if(next === 'down') $bubble.find('.chat_fb_reasons').addClass('is_open');
      else fbDone($bubble, '감사합니다');   /* 👍는 이유를 묻지 않는다 */
    }, function(){
      fbReset($bubble);
      if(prev) $bubble.find('.chat_fb_btn[data-fb="' + prev + '"]').addClass('is_on').attr('aria-pressed','true');
    });
  });

  /* 이유는 조치를 가른다: mismatch → 변형 질문·임계값 / wrong → 답변 수정 / thin → 보강.
     고르지 않아도 👎 는 위에서 이미 기록됐다 — 그래서 실패해도 완료 문구를 띄운다. */
  $(document).on('click', '.chat_fb_reason', function(){
    var $bubble = $(this).closest('.chat_bubble');
    var reason  = $(this).attr('data-reason');
    $bubble.find('.chat_fb_reasons').removeClass('is_open');
    sendFeedback($bubble, { vote:'down', reason:reason },
                 function(){ fbDone($bubble); }, function(){ fbDone($bubble); });
  });
  $(document).on('click', '.chat_fb_skip', function(){
    $(this).closest('.chat_bubble').find('.chat_fb_reasons').removeClass('is_open');
  });

  /* ---------- 맨 아래로 (#chatToBottom) ---------- */
  $list.on('scroll', updateToBottom);
  $toBottom.on('click', function(){
    $toBottom.removeClass('is_new');
    scrollBottom();
    setTimeout(updateToBottom, 220);
  });

  updateReset(); updateToBottom();

  /* ---------- 관리자 로그인 (#chatAdmin) ----------
     로그인 엔드포인트는 admin.js 와 같은 `/api/admin/login` 을 쓴다. 화면이 다르다고
     로그인 API 를 따로 만들면 실패 횟수 잠금(서버가 IP 단위로 센다)이 두 벌로 갈라져,
     한쪽이 잠겨도 다른 쪽으로 계속 찔러 볼 수 있게 된다.

     비밀번호는 이 블록 밖으로 나가지 않는다 — 보내고 나면 곧바로 지운다. */
  var ADMIN_MAX_TRY = 5, ADMIN_LOCK_SEC = 30;   /* admin.js · admin_auth.py 와 같은 값 */
  var $adminModal = $('#chatAdminModal');
  var $adminForm  = $('#chatAdminForm');
  var $adminId    = $('#chatAdminId');
  var $adminPw    = $('#chatAdminPw');
  var $adminPwTgl = $('#chatAdminPwToggle');
  var adminFail = 0, adminLockTimer = null, adminLastFocus = null;

  function adminMsg(txt){ $('#chatAdminMsg').text(txt || '').toggleClass('is_on', !!txt); }
  function adminState(state){
    $adminForm.removeClass('is_busy is_error is_locked');
    if(state) $adminForm.addClass('is_' + state);
    var stop = state === 'busy' || state === 'locked';
    $adminId.add($adminPw).prop('disabled', stop);
    $adminPwTgl.prop('disabled', stop);
    $('#chatAdminSubmit').prop('disabled', stop).text(state === 'busy' ? '확인 중…' : '로그인');
  }
  /* 서버가 준 문구를 그대로 보여준다 — 잠금 남은 초처럼 화면이 모르는 값이 들어 있다. */
  function adminDetail(xhr){
    var d = xhr && xhr.responseJSON && xhr.responseJSON.detail;
    return typeof d === 'string' ? d : '';
  }
  function adminPwReset(){
    $adminPw.val('').attr('type', 'password');
    $adminPwTgl.attr('aria-pressed', 'false').text('보기');
  }
  function adminLock(msg){
    var left = ADMIN_LOCK_SEC;
    adminState('locked');
    adminMsg(msg || ('비밀번호를 ' + ADMIN_MAX_TRY + '회 잘못 입력했습니다. ' + left + '초 후 다시 시도해 주세요.'));
    clearInterval(adminLockTimer);
    adminLockTimer = setInterval(function(){
      left--;
      if(left <= 0){
        clearInterval(adminLockTimer);
        adminFail = 0;
        adminState(null); adminMsg('');
        $adminPw.trigger('focus');
        return;
      }
      adminMsg('비밀번호를 ' + ADMIN_MAX_TRY + '회 잘못 입력했습니다. ' + left + '초 후 다시 시도해 주세요.');
    }, 1000);
  }
  function openAdmin(){
    adminLastFocus = document.activeElement;
    $adminModal.addClass('is_open');
    adminState(null); adminMsg(''); adminPwReset();
    setTimeout(function(){ ($.trim($adminId.val()) ? $adminPw : $adminId).trigger('focus'); }, 0);
  }
  function closeAdmin(){
    $adminModal.removeClass('is_open');
    /* 입력값은 남기지 않는다 */
    $adminId.val(''); adminPwReset();
    adminFail = 0; clearInterval(adminLockTimer);
    adminState(null); adminMsg('');
    if(adminLastFocus && adminLastFocus.focus) adminLastFocus.focus();
  }

  $('#chatAdmin').on('click', function(){
    /* 이미 로그인돼 있으면 묻지 않고 바로 보낸다. 세션 조회는 인증 없이 부를 수 있다. */
    $.getJSON('/api/admin/session')
      .done(function(s){ if(s && s.authenticated){ location.href = '/admin'; } else { openAdmin(); } })
      .fail(function(){ openAdmin(); });
  });

  $adminPwTgl.on('click', function(){
    var show = $adminPw.attr('type') === 'password';
    $adminPw.attr('type', show ? 'text' : 'password');
    $(this).attr('aria-pressed', show ? 'true' : 'false').text(show ? '숨기기' : '보기');
  });

  $adminId.add($adminPw).on('input', function(){
    if($adminForm.hasClass('is_locked')) return;
    $adminForm.removeClass('is_error'); adminMsg('');
  });

  $adminForm.on('submit', function(e){
    e.preventDefault();
    if($adminForm.hasClass('is_busy') || $adminForm.hasClass('is_locked')) return;

    var id = $.trim($adminId.val()), pw = $adminPw.val();
    if(!id || !pw){
      $adminForm.addClass('is_error');
      adminMsg('아이디와 비밀번호를 입력해 주세요.');
      (id ? $adminPw : $adminId).trigger('focus');
      return;
    }

    adminState('busy'); adminMsg('');
    $.ajax({
      url: '/api/admin/login',
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({ username: id, password: pw })
    })
      .done(function(){
        /* 세션 쿠키는 서버가 심어 준다(httponly). 화면이 들고 있을 것이 없다. */
        $adminId.val(''); adminPwReset();
        location.href = '/admin';
      })
      .fail(function(xhr){
        adminState(null);
        $adminForm.addClass('is_error');
        adminPwReset();
        /* 429 = 서버가 IP 단위로 잠갔다. 화면 카운트와 무관하게 서버 문구를 따른다. */
        if(xhr.status === 429){ adminLock(adminDetail(xhr)); return; }
        adminFail++;
        if(adminFail >= ADMIN_MAX_TRY){ adminLock(); return; }
        adminMsg(adminDetail(xhr) || '아이디 또는 비밀번호가 올바르지 않습니다.');
        $adminPw.trigger('focus');
      });
  });

  /* 닫기 — ✕ · 취소 · 배경 클릭 · ESC. admin.html 쪽 로그인 모달과 다른 점이다. */
  $(document).on('click', '[data-admin-cancel]', closeAdmin);
  $adminModal.on('click', function(e){ if(e.target === this) closeAdmin(); });
  $(document).on('keydown', function(e){
    if(e.key === 'Escape' && $adminModal.hasClass('is_open')) closeAdmin();
  });

  /* ---------- 카테고리 로드 ----------
     팝오버를 먼저 한 번 그려 두고(빈 상태), 응답이 오면 다시 그린다.
     응답을 기다렸다 그리면 그 사이 트리거를 누른 사용자에게 아무것도 안 열린 것처럼 보인다. */
  buildPopover('');
  $.getJSON(API.categories)
    .done(function(data){
      CATEGORY_GROUPS = data.groups || [];
      QUICK_CATEGORY_IDS = data.quick_category_ids || [];
      buildQuick();
      buildPopover($search.val());
      if($introCats.hasClass('is_open')) buildCatList($introList, $introSearch.val());
    })
    .fail(function(){
      /* 카테고리를 못 받아도 질문 입력은 계속 되어야 한다 — 주제는 검색 힌트일 뿐이다.
         주제 0건일 때와 같은 처리를 쓴다(updateCatVisibility). */
      CATEGORY_GROUPS = [];
      updateCatVisibility();
    });

});
