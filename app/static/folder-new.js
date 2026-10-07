/* folder-new.js — 새 프로젝트 만들기.
 *
 * 퍼블 산출물의 '새 폴더 만들기' 를 프로젝트 만들기로 바꾼 것입니다. 산출물의 접근 권한
 * 표는 후순위라 화면에서 감춰 두었고(`#permCard[hidden]`), 그 자리에 **AI 가 알아야 할
 * 것**(소개·도메인·언어)을 넣었습니다 — 조직 이름을 소스에 박지 않으려고 둔 값들입니다.
 *
 * 서버와 닿는 자리 두 군데:
 *   POST /api/admin/projects          프로젝트 뼈대 만들기 (studio + 관리자)
 *   PUT  /api/admin/profile?project=  그 프로젝트의 소개·언어
 */
(function () {
  'use strict';

  function $(id) { return document.getElementById(id); }

  var nameEl = $('pname'), idEl = $('pid'), saveBtn = $('saveBtn');
  /* 사람이 ID 를 직접 적기 전까지는 이름에서 만들어 보여 줍니다. 두 칸을 다 채우게 하면
     대부분 같은 값을 두 번 적습니다. */
  var idTouched = false;

  function slug(text) {
    return String(text).toLowerCase()
      .replace(/[^a-z0-9_-]+/g, '-')     /* 한글·공백·기호는 전부 '-' 로 */
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '')
      .slice(0, 40);
  }

  function toast(msg) {
    var el = $('toast');
    el.textContent = msg; el.classList.add('show');
    setTimeout(function () { el.classList.remove('show'); }, 2800);
  }

  function refresh() {
    if (!idTouched) idEl.value = slug(nameEl.value);
    $('pathPreview').textContent = 'packs / ' + (idEl.value || '(프로젝트 ID)');
  }

  function hint(el, text, bad) {
    el.textContent = text;
    el.classList.toggle('err', !!bad);
  }

  nameEl.addEventListener('input', function () {
    nameEl.classList.remove('err');
    hint($('nameHint'), '40자 이내로 입력해 주세요.', false);
    refresh();
  });
  idEl.addEventListener('input', function () {
    idTouched = true;
    idEl.classList.remove('err');
    /* 받는 글자만 남깁니다. 못 쓰는 글자를 적는 순간 보이게 하는 편이, 저장을 눌렀을 때
       서버가 400 을 내는 것보다 짧습니다. */
    var cleaned = idEl.value.toLowerCase().replace(/[^a-z0-9_-]/g, '');
    if (cleaned !== idEl.value) {
      idEl.value = cleaned;
      hint($('idHint'), '영문 소문자·숫자·- 만 쓸 수 있어 바꿨습니다.', false);
    }
    refresh();
  });

  function fail(message) {
    $('formErr').textContent = message;
    $('formErr').removeAttribute('hidden');
    saveBtn.disabled = false;
    saveBtn.textContent = '프로젝트 만들기';
  }

  $('projectForm').addEventListener('submit', function (e) {
    e.preventDefault();
    $('formErr').setAttribute('hidden', '');

    var name = nameEl.value.trim();
    if (!name) {
      nameEl.classList.add('err');
      hint($('nameHint'), '프로젝트 이름을 입력해 주세요.', true);
      nameEl.focus();
      return;
    }
    var projectId = idEl.value.trim() || slug(name);
    if (!/^[a-z0-9][a-z0-9_-]{0,39}$/.test(projectId)) {
      idEl.classList.add('err');
      hint($('idHint'), '영문 소문자로 시작하고, 소문자·숫자·- 만 쓸 수 있습니다.', true);
      idEl.focus();
      return;
    }

    saveBtn.disabled = true;
    saveBtn.textContent = '만드는 중…';

    fetch('/api/admin/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId, name: name,
                             description: $('pdesc').value.trim(), role: $('prole').value })
    }).then(function (r) {
      if (r.status === 401 || r.status === 403) throw new Error('관리자로 로그인한 뒤 다시 시도해 주세요. (관리자 설정 → 로그인)');
      return r.json().then(function (body) {
        if (!r.ok) throw new Error(body.detail || ('프로젝트를 만들지 못했습니다 (' + r.status + ')'));
        return body;
      });
    }).then(function (created) {
      /* 프로필은 **만든 뒤에** 따로 저장합니다. 프로젝트가 없으면 저장할 경로가 없습니다.
         여기서 실패해도 프로젝트는 남으므로, 관리자 설정에서 고칠 수 있다고 알려 줍니다. */
      var profile = {
        organization: name,
        service_name: name,
        service_desc: $('pdesc').value.trim() || '',
        domain_intro: $('pdomain').value.trim() || name,
        language: $('plang').value
      };
      return fetch('/api/admin/profile?project=' + encodeURIComponent(created.project_id), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile)
      }).then(function (r) {
        if (!r.ok) toast('프로젝트는 만들었습니다. 소개·언어는 관리자 설정에서 저장해 주세요.');
        return created;
      }, function () {
        toast('프로젝트는 만들었습니다. 소개·언어는 관리자 설정에서 저장해 주세요.');
        return created;
      });
    }).then(function (created) {
      /* 만든 프로젝트를 고른 상태로 자료 화면을 엽니다 — 바로 자료를 올리는 흐름입니다. */
      location.href = '/?project=' + encodeURIComponent(created.project_id);
    }).catch(function (err) {
      fail(err && err.message ? err.message : '프로젝트를 만들지 못했습니다.');
    });
  });

  enhanceSelect($('prole'));
  enhanceSelect($('plang'));
  refresh();
})();
