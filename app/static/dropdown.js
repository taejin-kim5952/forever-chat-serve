/* 공통 드롭다운: <select>를 세련된 목록으로 바꿔 줌 (값은 select에 그대로 저장) */
const ICONS = {drive:'ic-drive', folder:'ic-folder', group:'ic-share', user:'ic-user'};
let openDD = null;

function enhanceSelect(sel, opts = {}){
  const wrap = document.createElement('div');
  wrap.className = 'dd' + (opts.align === 'right' ? ' dd-right' : '') + (opts.variant === 'inline' ? ' dd-inline' : '');
  sel.parentNode.insertBefore(wrap, sel);
  wrap.appendChild(sel);
  sel.hidden = true; sel.tabIndex = -1;

  const btn = document.createElement('button');
  btn.type = 'button'; btn.className = 'dd-btn';
  btn.setAttribute('aria-haspopup', 'listbox'); btn.setAttribute('aria-expanded', 'false');
  if (sel.id) { btn.id = sel.id + '-btn'; document.querySelector(`label[for="${sel.id}"]`)?.setAttribute('for', btn.id); }
  const menu = document.createElement('div');
  menu.className = 'dd-menu'; menu.setAttribute('role', 'listbox');
  wrap.append(btn, menu);

  const lead = o => {
    const icon = o.dataset.icon;
    if (icon === 'user') return `<span class="dd-avatar">${o.textContent.trim().charAt(0)}</span>`;
    return icon ? `<svg class="i dd-ico"><use href="#${ICONS[icon]}"/></svg>` : '';
  };
  const optHTML = (o, i) => `
    <div class="dd-opt" role="option" data-i="${i}" aria-selected="${o.selected}">
      ${lead(o)}
      <span class="dd-txt"><b>${o.textContent}</b>${o.dataset.desc ? `<small>${o.dataset.desc}</small>` : ''}</span>
      <svg class="i dd-check"><use href="#ic-check"/></svg>
    </div>`;

  function build(){
    let i = 0, html = '';
    [...sel.children].forEach(node => {
      if (node.tagName === 'OPTGROUP') {
        html += `<div class="dd-group">${node.label}</div>`;
        [...node.children].forEach(o => { html += optHTML(o, i++); });
      } else html += optHTML(node, i++);
    });
    menu.innerHTML = html;
    const cur = sel.options[sel.selectedIndex];
    btn.innerHTML = `${lead(cur)}<span class="dd-val">${cur.textContent}</span><svg class="i dd-chev"><use href="#ic-down"/></svg>`;
  }
  let active = -1;
  const items = () => [...menu.querySelectorAll('.dd-opt')];
  function setActive(i){
    const list = items(); active = Math.max(0, Math.min(list.length - 1, i));
    list.forEach((el, k) => el.classList.toggle('active', k === active));
    list[active]?.scrollIntoView({block:'nearest'});
  }
  function open(){
    if (openDD && openDD !== api) openDD.close();
    const r = btn.getBoundingClientRect();
    wrap.classList.toggle('up', window.innerHeight - r.bottom < 280 && r.top > 280);
    wrap.classList.add('open'); btn.setAttribute('aria-expanded', 'true');
    setActive(sel.selectedIndex); openDD = api;
  }
  function close(){
    wrap.classList.remove('open'); btn.setAttribute('aria-expanded', 'false');
    if (openDD === api) openDD = null;
  }
  function choose(i){
    if (sel.selectedIndex !== i) { sel.selectedIndex = i; sel.dispatchEvent(new Event('change', {bubbles:true})); }
    build(); close(); btn.focus();
  }
  btn.addEventListener('click', () => wrap.classList.contains('open') ? close() : open());
  btn.addEventListener('keydown', e => {
    const isOpen = wrap.classList.contains('open');
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!isOpen) open(); else setActive(active + (e.key === 'ArrowDown' ? 1 : -1));
    } else if ((e.key === 'Enter' || e.key === ' ') && isOpen) { e.preventDefault(); choose(active); }
    else if (e.key === 'Escape' || e.key === 'Tab') close();
  });
  menu.addEventListener('mousemove', e => { const o = e.target.closest('.dd-opt'); if (o) setActive(Number(o.dataset.i)); });
  menu.addEventListener('click', e => { const o = e.target.closest('.dd-opt'); if (o) choose(Number(o.dataset.i)); });
  const api = {close};
  build();
  return api;
}
document.addEventListener('click', e => { if (openDD && !e.target.closest('.dd.open')) openDD.close(); });
