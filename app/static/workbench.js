import {views} from './columns.js';
import {hookRunActions} from './actions.js';

const $ = selector => document.querySelector(selector);
const run = document.body.dataset.run;
const options = $('#evidence-view');
const status = $('#evidence-status');
const search = $('#ticket-filter');
const showFilter = $('#show-filter');
const back = $('#page-back');
const next = $('#page-next');
const limit = 20;
let selectedShow = '';
let active = 'reconcile';
let offset = 0;
let request;

const dateFormatter = new Intl.DateTimeFormat('zh-CN', {timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit',
  day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23'});
const numberFormat = new Intl.NumberFormat('zh-CN');
const format = {
  money: cents => {
    const digits = Math.abs(cents);
    return `${cents < 0 ? '−' : ''}${numberFormat.format(Math.floor(digits / 100))}.${String(digits % 100).padStart(2, '0')}`;
  },
  time: value => dateFormatter.format(new Date(value)),
  eligible: value => value ? '合资格' : '暂缓',
  showStatus: value => value === 'open' ? '开放' : '暂缓',
  number: value => numberFormat.format(value),
};

function evidenceDetails(row) {
  const details = document.createElement('details');
  const label = document.createElement('summary');
  label.textContent = '查看';
  const contents = document.createElement('code');
  contents.className = 'raw';
  const raw = JSON.stringify(row.raw, null, 2);
  contents.textContent = Object.keys(row.detail || {}).length ? `${raw}\n${JSON.stringify(row.detail, null, 2)}` : raw;
  details.append(label, contents);
  return details;
}

function displayCell(row, key, type) {
  const cell = document.createElement('td');
  if (['money', 'number', 'row'].includes(type)) cell.className = 'num';
  if (type === 'raw' && row.raw) {
    cell.append(evidenceDetails(row));
  } else {
    const text = document.createElement('span');
    const value = row[key];
    if (type === 'row' && Number.isInteger(value) && row.end_line !== value) {
      text.textContent = `${value}–${row.end_line}`;
    } else {
      text.textContent = value === null || value === undefined || value === '' ? '—' : (format[type]?.(value) ?? value);
    }
    text.title = text.textContent;
    cell.append(text);
  }
  return cell;
}

function render(columns, rows, message, error = false) {
  const header = document.createElement('tr');
  for (const [, label, type] of columns) {
    const heading = document.createElement('th');
    heading.scope = 'col';
    heading.textContent = label;
    if (['money', 'number', 'row'].includes(type)) heading.className = 'num';
    header.append(heading);
  }
  $('#evidence-columns').replaceChildren(header);
  const table = $('#evidence-rows');
  table.replaceChildren();
  if (!rows.length) {
    const empty = table.insertRow().insertCell();
    empty.colSpan = columns.length;
    empty.className = error ? 'empty error' : 'empty';
    empty.textContent = message;
    return;
  }
  for (const row of rows) {
    const tr = table.insertRow();
    for (const [key, , type] of columns) tr.append(displayCell(row, key, type));
  }
}

async function refresh() {
  request?.abort();
  const controller = new AbortController();
  request = controller;
  const view = options.value;
  const [, columns] = views[active][view];
  const query = new URLSearchParams({view, q: search.value, show: selectedShow, offset, limit});
  status.textContent = '读取中…';
  render(columns, [], '读取票房证据…');
  back.disabled = next.disabled = true;
  try {
    const response = await fetch(`/api/${active}/${encodeURIComponent(run)}?${query}`, {signal: controller.signal});
    if (!response.ok) throw new Error('读取失败，请重新筛选。');
    const data = await response.json();
    if (request !== controller) return;
    render(columns, data.items, '无匹配记录，请调整筛选。');
    status.textContent = `${data.total} 行${data.items.length ? ` · ${offset + 1}–${offset + data.items.length}` : ''}`;
    back.disabled = offset === 0;
    next.disabled = offset + limit >= data.total;
  } catch (error) {
    if (error.name === 'AbortError' || request !== controller) return;
    status.textContent = '读取失败';
    render(columns, [], '读取失败，请点击筛选重试。', true);
  }
}

function markShow(show, label = '') {
  selectedShow = show;
  showFilter.hidden = !show;
  showFilter.textContent = show ? `${label || show} ×` : '';
  document.querySelectorAll('[data-show-row]').forEach(row => row.classList.toggle('is-selected', Boolean(show) && row.dataset.showRow === show));
  document.querySelectorAll('button[data-show]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.show === show)));
}

function changeModule(module, show = '', label = '') {
  active = module;
  offset = 0;
  document.querySelectorAll('nav [data-module]').forEach(link => {
    if (link.dataset.module === module) {
      link.setAttribute('aria-current', 'location');
      $('#module-name').textContent = link.textContent;
    } else link.removeAttribute('aria-current');
  });
  options.replaceChildren(...Object.entries(views[module]).map(([key, [label]]) => new Option(label, key)));
  markShow(show, label);
  refresh();
}

for (const link of document.querySelectorAll('[data-module]')) {
  link.addEventListener('click', event => {
    event.preventDefault();
    const module = link.dataset.module;
    history.replaceState(null, '', `#${module}`);
    changeModule(module);
    $('#proof').scrollIntoView({block: 'nearest'});
  });
}
for (const button of document.querySelectorAll('button[data-show]')) {
  button.addEventListener('click', () => {
    const show = button.dataset.show === selectedShow ? '' : button.dataset.show;
    history.replaceState(null, '', '#reconcile');
    search.value = '';
    changeModule('reconcile', show, button.querySelector('strong').textContent);
  });
}
showFilter.addEventListener('click', () => { markShow(''); offset = 0; refresh(); });
$('#evidence-filters').addEventListener('submit', event => { event.preventDefault(); offset = 0; refresh(); });
options.addEventListener('change', () => {
  if (['venues', 'sources', 'tickets'].includes(options.value)) markShow('');
  offset = 0;
  refresh();
});
back.addEventListener('click', () => { offset = Math.max(0, offset - limit); refresh(); });
next.addEventListener('click', () => { offset += limit; refresh(); });
const initial = location.hash.slice(1);
changeModule(Object.hasOwn(views, initial) ? initial : 'reconcile');
hookRunActions();
