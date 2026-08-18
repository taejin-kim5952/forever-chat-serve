/* ============================================================
   markdown.js — 답변/문서 본문 렌더러 (chat.js · admin.js 공용)

   전에는 chat.js 와 admin.js 에 같은 renderMarkdown() 이 복붙돼 있었다. 이 둘은
   **글자 하나까지 같아야 한다** — 관리자가 검수 화면에서 본 모양이 곧 사용자가 챗봇에서
   보는 모양이기 때문이다. 복붙 상태에서는 한쪽만 고치면 조용히 어긋나므로 여기로 합쳤다.

   ## 지원 범위 (일부러 좁게 잡은 것이다)

     문단 · 줄바꿈 · 번호목록 · 불릿 · 제목 · 표 · 코드블록 · 인라인코드 · 굵게 · 링크
     이미지는 **문서 본문(renderDoc)에서만** 그린다.

   답변 말풍선에 이미지를 넣지 않는 이유: 화면 캡처·도식을 답변마다 박으면 제품 UI 가
   바뀔 때 그 그림을 인용한 답변을 전부 찾아 고쳐야 한다. 그림은 원본 문서 한 곳에만 두고
   문서 상세에서 본다. 갱신 지점이 하나가 된다.

   ## 보안

   마크다운 라이브러리를 쓰지 않는다. 흔한 파서들은 명세를 따라 **원시 HTML 을 그대로
   통과**시키는데, 답변 본문은 LLM 이 만들거나 문서에서 가져온 텍스트라 그러면 XSS 통로가
   된다. 여기서는 esc() 로 전부 이스케이프한 뒤 **정해진 태그만** 붙인다. 방어선이
   esc() 한 곳이라 검증이 쉽다.

   링크도 같은 이유로 스킴을 검사한다(safeHref) — `javascript:` `data:` 는 링크로
   만들지 않고 글자로 흘린다. 운영이 폐쇄망이라 외부 주소는 어차피 열리지 않으므로
   같은 오리진만 허용한다.
   ============================================================ */

window.ChatMD = (function () {

  /* 문서 이미지 경로. 화면마다 앞에 붙는 베이스가 다를 수 있어(API Manager 안에서는
     /apidev/chat/api/docs/img/) 바깥에서 넣어준다. */
  var CFG = { imageBase: '/api/docs/img/' };

  function configure(opts) {
    if (opts && opts.imageBase) { CFG.imageBase = opts.imageBase; }
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  /* ---------- 링크 ---------- */

  /* 허용: 사이트 절대경로(/apidev/...) 와 같은 오리진의 http(s) 주소.
     막음: javascript:/data:/vbscript: 같은 스킴, //evil.com 같은 프로토콜 상대주소,
           그리고 다른 오리진 전부(폐쇄망이라 어차피 안 열린다).
     허용되지 않으면 빈 문자열을 돌려주고, 호출부는 링크 대신 글자로 남긴다. */
  function safeHref(raw) {
    var url = String(raw == null ? '' : raw).trim();
    if (!url) { return ''; }
    if (url.indexOf('//') === 0) { return ''; }          // 프로토콜 상대주소
    if (url.charAt(0) === '/') { return url; }            // 사이트 절대경로

    // 스킴이 붙어 있으면 http(s) + 같은 오리진일 때만 허용한다.
    if (/^[a-z][a-z0-9+.-]*:/i.test(url)) {
      if (!/^https?:/i.test(url)) { return ''; }
      try {
        if (new URL(url).origin !== window.location.origin) { return ''; }
      } catch (e) {
        return '';
      }
      return url;
    }
    return '';   // 상대경로는 챗봇이 어느 화면에서 열렸느냐에 따라 달라져 쓰지 않는다
  }

  /* ---------- 인라인 ---------- */

  /* esc() 를 먼저 돌리므로 아래 치환은 이미 안전한 문자열 위에서 일어난다.
     `"` 가 &quot; 로 바뀐 뒤라 href 속성을 깨고 나갈 수 없다. */
  function inline(text) {
    return esc(text)
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, function (whole, label, url) {
        var href = safeHref(url);
        return href ? '<a class="chat_link" href="' + href + '">' + label + '</a>' : whole;
      });
  }

  /* ---------- 블록 ---------- */

  var RE_FENCE   = /^\s*```/;
  var RE_HEADING = /^(#{1,4})\s+(.*)$/;
  var RE_OL      = /^\s*\d+\.\s/;
  var RE_UL      = /^\s*[-*]\s/;
  var RE_TABLE_SEP = /^\s*\|?[\s:|-]+\|[\s:|-]*$/;
  var RE_IMAGE   = /^!\[([^\]]*)\]\(([^)\s]+)\)$/;

  function tableCells(line) {
    return line.replace(/^\s*\|/, '').replace(/\|\s*$/, '').split('|').map(function (c) {
      return c.trim();
    });
  }

  /* 폭이 좁은 말풍선 안에서도 넘치지 않도록 가로 스크롤 컨테이너로 감싼다. */
  function table(rows) {
    var head = '<tr>' + tableCells(rows[0]).map(function (c) {
      return '<th>' + inline(c) + '</th>';
    }).join('') + '</tr>';
    var body = rows.slice(2).map(function (l) {
      return '<tr>' + tableCells(l).map(function (c) {
        return '<td>' + inline(c) + '</td>';
      }).join('') + '</tr>';
    }).join('');
    return '<div class="chat_tbl_wrap"><table class="chat_tbl">' +
           '<thead>' + head + '</thead><tbody>' + body + '</tbody></table></div>';
  }

  /* `img/파일명` 만 받는다. 절대 URL(폐쇄망에서 안 뜬다)과 상위경로는 그림으로 안 그린다. */
  function image(line) {
    var m = line.trim().match(RE_IMAGE);
    if (!m) { return ''; }
    var src = m[2];
    if (src.indexOf('img/') !== 0 || src.indexOf('..') > -1) { return ''; }
    return '<figure class="chat_fig"><img src="' + CFG.imageBase + encodeURIComponent(src.slice(4)) +
           '" alt="' + esc(m[1]) + '" loading="lazy"></figure>';
  }

  /* 줄 단위로 훑는다. 이전에는 빈 줄로 블록을 나눴는데, 그러면 코드블록 안의 빈 줄에서
     블록이 쪼개져 코드가 문단으로 흩어진다. */
  function render(src, withImages) {
    var lines = String(src || '').replace(/\r\n/g, '\n').split('\n');
    var html = '';
    var i = 0;

    while (i < lines.length) {
      var line = lines[i];

      if (line.trim() === '') { i++; continue; }

      // 코드블록 — 닫는 울타리가 없으면 끝까지가 코드다
      if (RE_FENCE.test(line)) {
        var code = [];
        i++;
        while (i < lines.length && !RE_FENCE.test(lines[i])) { code.push(lines[i]); i++; }
        i++;   // 닫는 울타리
        html += '<pre class="chat_code"><code>' + esc(code.join('\n')) + '</code></pre>';
        continue;
      }

      // 이미지 — 문서 본문에서만
      if (withImages) {
        var fig = image(line);
        if (fig) { html += fig; i++; continue; }
      }

      // 제목
      var heading = line.match(RE_HEADING);
      if (heading) {
        var level = Math.min(heading[1].length + 2, 6);   // 화면 제목보다 낮춘다
        html += '<h' + level + ' class="chat_h">' + inline(heading[2]) + '</h' + level + '>';
        i++;
        continue;
      }

      // 표 — 둘째 줄이 |---|---| 구분선일 때만 표로 본다
      if (line.indexOf('|') > -1 && i + 1 < lines.length && RE_TABLE_SEP.test(lines[i + 1])) {
        var rows = [];
        while (i < lines.length && lines[i].trim() !== '' && lines[i].indexOf('|') > -1) {
          rows.push(lines[i]); i++;
        }
        html += table(rows);
        continue;
      }

      // 목록
      if (RE_OL.test(line) || RE_UL.test(line)) {
        var ordered = RE_OL.test(line);
        var tag = ordered ? 'ol' : 'ul';
        var items = [];
        while (i < lines.length && (ordered ? RE_OL : RE_UL).test(lines[i])) {
          items.push('<li>' + inline(lines[i].replace(ordered ? RE_OL : RE_UL, '')) + '</li>');
          i++;
        }
        html += '<' + tag + '>' + items.join('') + '</' + tag + '>';
        continue;
      }

      // 문단 — 빈 줄이나 다른 블록이 나올 때까지
      var para = [];
      while (i < lines.length && lines[i].trim() !== ''
             && !RE_FENCE.test(lines[i]) && !RE_HEADING.test(lines[i])
             && !RE_OL.test(lines[i]) && !RE_UL.test(lines[i])) {
        para.push(inline(lines[i]));
        i++;
      }
      if (para.length) { html += '<p>' + para.join('<br>') + '</p>'; }
    }

    return html;
  }

  return {
    configure: configure,
    esc: esc,
    inline: inline,
    safeHref: safeHref,
    /** 답변 말풍선 · 검수 미리보기 — 이미지 없음 */
    renderAnswer: function (src) { return render(src, false); },
    /** 문서 상세 모달 — 이미지 포함 */
    renderDoc: function (src) { return render(src, true); }
  };
})();
