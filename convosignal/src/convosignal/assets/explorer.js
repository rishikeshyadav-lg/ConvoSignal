'use strict';
const data = JSON.parse(document.getElementById('dataset').textContent);
const $ = id => document.getElementById(id);
const node = (tag, text, cls) => {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = String(text);
  if (cls) element.className = cls;
  return element;
};
const append = (parent, ...children) => { children.forEach(child => parent.append(child)); return parent; };
const pill = label => node('span', label, 'pill ' + label.toLowerCase());
const conversations = new Map(data.conversations.map(c => [c.number, c]));
let page = 0;
let filtered = data.samples;
const pageSize = 20;
$('meta').textContent = data.metadata.agent_name + ' · ' + data.metadata.stage + ' (' + data.metadata.stage_basis + ') · ' + data.metadata.report_date;
for (const label of ['Satisfied', 'Dissatisfied', 'Neutral', 'Skipped', 'Error']) {
  $('stats').append(append(node('div', undefined, 'stat'), node('b', data.counts[label]), node('span', label), node('p', 'Selected trace rows', 'small')));
}
$('verification').textContent = data.sample_count + ' selected trace rows; ' + data.prompt_count + ' captured user messages; ' + data.conversation_count + ' conversations. ' + data.replayed_conversations + ' classified conversations replayed identically. ' + data.conversation_counts.Error + ' conversations remain unclassified.';
$('prompts').textContent = JSON.stringify(data.evaluator_prompts, null, 2);
const searchText = new Map(data.conversations.map(c => [c.number, [c.reason, ...c.messages.map(m => m.text), ...c.goals.flatMap(g => g.requirements.map(r => r.text))].join(' ').toLocaleLowerCase()]));
function refresh(reset = true) {
  if (reset) page = 0;
  const query = $('search').value.trim().toLocaleLowerCase();
  filtered = data.samples.filter(s => (!$('decision').value || s.label === $('decision').value) && (!query || [s.id, s.trace_id, s.reason, searchText.get(s.conversation_number)].join(' ').toLocaleLowerCase().includes(query)));
  page = Math.min(page, Math.max(0, Math.ceil(filtered.length / pageSize) - 1));
  $('samples').replaceChildren();
  for (const sample of filtered.slice(page * pageSize, (page + 1) * pageSize)) {
    const prompt = sample.messages.filter(m => m.role === 'user').map(m => m.text).join('\n\n');
    const button = node('button', 'Inspect');
    button.type = 'button';
    button.setAttribute('aria-label', 'Inspect ' + sample.id);
    button.onclick = () => openSample(sample);
    const cell = append(node('td'), node('div', prompt || 'No captured user prompt (source failure)', 'preview'), node('p', 'Conversation ' + sample.conversation_number + ' · ' + sample.reason, 'small'));
    $('samples').append(append(node('tr'), node('td', sample.id, 'mono'), cell, append(node('td'), pill(sample.label)), append(node('td'), button)));
  }
  if (!filtered.length) { const cell = node('td', 'No matching samples'); cell.colSpan = 4; $('samples').append(append(node('tr'), cell)); }
  $('result-count').textContent = filtered.length ? 'Showing ' + (page * pageSize + 1) + '–' + Math.min((page + 1) * pageSize, filtered.length) + ' of ' + filtered.length + ' trace rows' : 'No matching samples';
  $('previous').disabled = page === 0;
  $('next').disabled = (page + 1) * pageSize >= filtered.length;
}
function messages(parent, captured) {
  for (const message of captured) parent.append(append(node('section', undefined, 'message'), node('h3', message.role === 'user' ? 'User prompt' : 'Actual agent answer'), node('div', message.text, 'text'), node('p', message.turn_id, 'small mono')));
}
function openSample(sample) {
  const conversation = conversations.get(sample.conversation_number);
  $('detail-title').textContent = sample.id + ' · Conversation ' + sample.conversation_number;
  const body = $('detail-content');
  body.replaceChildren();
  append(body, pill(sample.label), node('p', sample.explanation), node('p', 'Decision unit: containing conversation at captured cutoff.', 'small'));
  if (sample.errors.length) body.append(node('p', 'Processing errors: ' + sample.errors.join('; '), 'callout'));
  body.append(node('h3', 'Selected interaction'));
  messages(body, sample.messages);
  if (!sample.messages.some(m => m.role === 'assistant')) body.append(node('p', 'No agent answer was captured for this interaction.', 'callout'));
  if (!conversation.context_complete) body.append(node('p', 'The source has incomplete history. Individual goals may still be evaluated when their relevant request and result are complete.', 'callout'));
  const context = node('details');
  context.append(node('summary', 'Full captured conversation, in chronological order'));
  messages(context, conversation.messages);
  body.append(context, node('h3', 'Goal-level reasons'));
  for (const goal of conversation.goals) {
    const box = append(node('section', undefined, 'goal'), node('h3', goal.id + ' · ' + (goal.label || 'Skipped')), node('p', goal.explanation));
    box.append(node('p', ['basis', 'outcome', 'user_response', 'correctness', 'recovery', 'reason'].map(k => k.replaceAll('_', ' ') + ': ' + goal[k]).join(' · '), 'small'));
    const table = node('table');
    table.append(append(node('thead'), append(node('tr'), node('th', 'Requirement'), node('th', 'Importance'), node('th', 'State'))));
    const rows = node('tbody');
    for (const r of goal.requirements) rows.append(append(node('tr'), node('td', r.text), node('td', r.material ? 'Essential' : 'Optional'), node('td', r.status)));
    table.append(rows); box.append(append(node('div', undefined, 'tablewrap'), table));
    for (const limitation of goal.limitations) box.append(node('p', 'Recorded limitation: ' + limitation));
    box.append(node('p', 'Evidence turn IDs: ' + goal.source_turn_ids.join(', '), 'small mono'));
    body.append(box);
  }
  const provenance = append(node('details'), node('summary', 'Source and version provenance'), node('pre', JSON.stringify({trace_id: sample.trace_id, timestamp_ms: sample.timestamp_ms, input_checksum: conversation.input_checksum, versions: conversation.versions}, null, 2)));
  body.append(provenance);
  $('detail').showModal(); $('detail').scrollTop = 0;
}
$('search').addEventListener('input', () => refresh());
$('decision').addEventListener('change', () => refresh());
$('previous').onclick = () => { page--; refresh(false); };
$('next').onclick = () => { page++; refresh(false); };
$('close-detail').onclick = () => $('detail').close();
$('theme').onclick = () => { const current = document.documentElement.dataset.theme; const dark = current === 'dark' || (!current && matchMedia('(prefers-color-scheme: dark)').matches); document.documentElement.dataset.theme = dark ? 'light' : 'dark'; };
function download(text, name, type) { const url = URL.createObjectURL(new Blob([text], {type})); const link = node('a'); link.href = url; link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
$('json').onclick = () => download(JSON.stringify(data, null, 2), 'decision-data.json', 'application/json');
$('csv').onclick = () => {
  const quote = value => { let text = String(value ?? ''); if (/^[=+@\-]/.test(text.replace(/^[ \t\r\n]+/, '')) || /^[\t\r]/.test(text)) text = "'" + text; return '"' + text.replaceAll('"', '""') + '"'; };
  const rows = [['Sample', 'Conversation', 'Conversation decision', 'Reason', 'Prompt count', 'User prompts', 'Agent answers'], ...data.samples.map(s => [s.id, s.conversation_number, s.label, s.reason, s.prompt_count, s.messages.filter(m => m.role === 'user').map(m => m.text).join('\n\n'), s.messages.filter(m => m.role === 'assistant').map(m => m.text).join('\n\n')])];
  download('\ufeff' + rows.map(row => row.map(quote).join(',')).join('\r\n') + '\r\n', 'decisions.csv', 'text/csv');
};
refresh();
window.reportAudit = {sampleCount: data.sample_count, promptCount: data.prompt_count, labels: data.counts, get visible() { return filtered.length; }};
