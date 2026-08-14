/* ============================================================
   API Manager 도우미 — 사용자 챗봇 화면 (jQuery)

   퍼블 산출물(퍼블/채팅 디자인 퍼블 완료/chat.js)을 이식한 것이다.
   더미 데이터(CATEGORY_GROUPS / DOC_FIXTURES / MOCK_ANSWER)와 목업 바는 걷어내고
   서버 API 호출로 바꿨다. 화면 구조·클래스·템플릿은 산출물 그대로 둔다 —
   퍼블이 화면을 다시 손보면 그 파일을 여기에 다시 얹을 수 있어야 하기 때문이다.
   ============================================================ */

var API = {
  ask:        '/api/ask',
  support:    '/api/support',
  categories: '/api/categories',
  chunk:      '/api/docs/chunk/',
  doc:        '/api/docs/'
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
  var $qBtn     = $('#chatCatQBtn');
  var $qList    = $('#chatCatQuestions');
  var $modal    = $('#chatDocModal');

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
  function buildQuick(){
    var $wrap = $('#chatCatQuick').empty();
    $.each(QUICK_CATEGORY_IDS.slice(0,6), function(_, id){
      var c = findCategory(id);
      if(!c) return;
      $('<button type="button" class="chat_cat_quick_chip"></button>')
        .attr('data-category-id', c.category_id).text(c.name).appendTo($wrap);
    });
    /* 자주 찾는 주제가 하나도 없으면 소제목만 남아 어색하다. */
    $('.chat_intro_sub').toggle($wrap.children().length > 0);
  }

  /* ---------- 팝오버 목록 ---------- */
  function buildPopover(query){
    var q = $.trim(query || '').toLowerCase();
    $popList.empty();
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
      $g.appendTo($popList);
    });

    $pop.toggleClass('is_empty', hit === 0);
  }

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
  }

  /* ---------- 메시지 렌더 ---------- */
  function hideIntro(){ $intro.hide(); }

  function pushUser(question, category){
    hideIntro();
    var $m = tpl('tpl_user');
    if(category){ $m.find('.chat_msg_cat').text('＃ ' + category.name); }
    else { $m.find('.chat_msg_cat').remove(); }   /* 미선택 시 배지 제거 */
    $m.find('[data-bind=question]').text(question);
    $inner.append($m);
    scrollBottom();
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
    scrollBottom();
  }

  function pushRelated(docs, question){
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
    scrollBottom();
  }

  function pushUnresolved(message, ticketId){
    hideIntro();
    var $m = tpl('tpl_unresolved');
    $m.find('[data-bind=message]').text(message || '문의가 담당자에게 접수되었습니다.');
    $m.find('[data-bind=ticket_id]').text(ticketId || newTicketId());
    $inner.append($m);
    scrollBottom();
  }

  function pushError(question){
    hideIntro();
    var $m = tpl('tpl_error');
    $m.find('[data-retry]').attr('data-question', question || '');
    $inner.append($m);
    scrollBottom();
  }

  function pushLoading(){
    hideIntro();
    $inner.append(tpl('tpl_loading'));
    scrollBottom();
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
    $modal.find('[data-bind=doc_excerpt]').text(d.text || '');
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

  $('.chat_cat_more').on('click', function(){ openPopover(); });
  $(document).on('click', '.chat_cat_quick_chip', function(){
    setCategory($(this).data('category-id'));
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

  $(document).on('click', function(){ closePopover(); closeQuestions(); });
  $(document).on('keydown', function(e){
    if(e.key !== 'Escape') return;
    if($modal.hasClass('is_open')) closeDoc();
    else if($pop.hasClass('is_open')) closePopover();
    else if($qList.hasClass('is_open')) closeQuestions();
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
    })
    .fail(function(){
      /* 카테고리를 못 받아도 질문 입력은 계속 되어야 한다 — 주제는 검색 힌트일 뿐이다. */
      $('.chat_cat_more').hide();
      $('.chat_intro_sub').hide();
    });

});
