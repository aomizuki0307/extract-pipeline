/**
 * Extract Pipeline — app.js
 * Vanilla JS frontend for the document extraction pipeline demo.
 *
 * Usage:
 *   Served as a static file by FastAPI at /web/app.js
 *   index.html loads this after Pico CSS and style.css
 */

/* ═══════════════════════════════════════════════════════════════
   State
   ═══════════════════════════════════════════════════════════════ */

/** @type {object|null} */
let currentResult = null;

/** @type {object[]} */
let schemasCache = [];

/** @type {boolean} */
let isLoading = false;

/* ═══════════════════════════════════════════════════════════════
   DOM References
   ═══════════════════════════════════════════════════════════════ */

const $ = (id) => document.getElementById(id);

const elDocText       = $('doc-text');
const elApiKey        = $('api-key');
const elApiKeyError   = $('api-key-error');
const elBtnExtract    = $('btn-extract');
const elExtractStatus = $('extract-status');
const elDropZone      = $('drop-zone');
const elSampleButtons = $('sample-buttons');

const elResultsEmpty   = $('results-empty');
const elResultsError   = $('results-error');
const elErrorMessage   = $('error-message');
const elResultsContent = $('results-content');

const elDocTypeBadge     = $('doc-type-badge');
const elConfidenceDisplay = $('confidence-display');
const elReasoningText    = $('reasoning-text');
const elFieldsList       = $('fields-list');
const elValidationResult = $('validation-result');
const elGuardrailCard    = $('guardrail-card');
const elGuardrailList    = $('guardrail-list');
const elJsonOutput       = $('json-output');

const elSchemaModal  = $('schema-modal');
const elSchemaCards  = $('schema-cards');
const elBtnSchemas   = $('btn-schemas');
const elBtnCloseModal = $('btn-close-modal');

/* Stage circle elements keyed by stage name */
const STAGE_NAMES = ['sanitize', 'classify', 'route', 'extract', 'validate', 'guard'];
const stageCircles = {};
STAGE_NAMES.forEach((name) => {
  stageCircles[name] = $(`stage-${name}`);
});

/* ═══════════════════════════════════════════════════════════════
   Helpers
   ═══════════════════════════════════════════════════════════════ */

/**
 * Fetch wrapper that automatically injects the X-API-Key header.
 * @param {string} path
 * @param {RequestInit} [options]
 * @returns {Promise<Response>}
 */
async function apiFetch(path, options = {}) {
  const key = elApiKey.value.trim();
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };
  if (key) {
    headers['X-API-Key'] = key;
  }
  return fetch(path, { ...options, headers });
}

/**
 * Escape HTML to safely insert untrusted strings into innerHTML.
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/**
 * Format a confidence float (0–1) as a percentage string.
 * @param {number} confidence
 * @returns {string}
 */
function formatConfidence(confidence) {
  if (confidence === null || confidence === undefined) return '—';
  return `${Math.round(confidence * 100)}%`;
}

/* ═══════════════════════════════════════════════════════════════
   Session Storage — API Key
   ═══════════════════════════════════════════════════════════════ */

function saveApiKey() {
  try {
    sessionStorage.setItem('extract_pipeline_api_key', elApiKey.value);
  } catch (_) {
    // sessionStorage unavailable — ignore silently
  }
}

function restoreApiKey() {
  try {
    const stored = sessionStorage.getItem('extract_pipeline_api_key');
    if (stored) {
      elApiKey.value = stored;
    }
  } catch (_) {
    // ignore
  }
}

elApiKey.addEventListener('input', saveApiKey);

/* ═══════════════════════════════════════════════════════════════
   Pipeline Stage Animation
   ═══════════════════════════════════════════════════════════════ */

/**
 * Reset all stage circles to the neutral (idle) state.
 */
function resetStages() {
  STAGE_NAMES.forEach((name) => {
    const el = stageCircles[name];
    if (!el) return;
    el.classList.remove('pass', 'fail', 'skip', 'warn');
    el.setAttribute('aria-label', `${capitalize(name)} stage`);
  });
}

/** @type {number[]} */
let stageTimers = [];

/**
 * Animate pipeline stages sequentially with 300ms between each.
 * @param {Array<{stage: string, status: string, detail: string}>} stages
 */
function animateStages(stages) {
  stageTimers.forEach(clearTimeout);
  stageTimers = [];
  resetStages();
  stages.forEach((s, index) => {
    const id = setTimeout(() => {
      const el = stageCircles[s.stage];
      if (!el) return;
      el.classList.remove('pass', 'fail', 'skip', 'warn');
      el.classList.add(s.status);
      el.setAttribute('aria-label', `${capitalize(s.stage)} stage: ${s.status}${s.detail ? ` — ${s.detail}` : ''}`);
    }, 300 * (index + 1));
    stageTimers.push(id);
  });
}

function capitalize(str) {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

/* ═══════════════════════════════════════════════════════════════
   Results Display
   ═══════════════════════════════════════════════════════════════ */

function showEmpty() {
  elResultsEmpty.hidden = false;
  elResultsError.hidden = true;
  elResultsContent.hidden = true;
}

function showError(message) {
  elResultsEmpty.hidden = true;
  elResultsError.hidden = false;
  elResultsContent.hidden = true;
  elErrorMessage.textContent = message;
}

function showResults(result) {
  elResultsEmpty.hidden = true;
  elResultsError.hidden = true;
  elResultsContent.hidden = false;

  renderClassification(result);
  renderFields(result.extraction);
  renderValidation(result.validation);
  renderGuardrails(result.guardrail_flags);
  renderJson(result);
}

/** Render the classification card. */
function renderClassification(result) {
  const cls = result.classification || {};
  const docType = cls.doc_type || result.doc_type || 'unknown';
  const confidence = cls.confidence ?? result.confidence ?? null;
  const reasoning = cls.reasoning || '';

  elDocTypeBadge.textContent = docType.replace(/_/g, ' ');
  elDocTypeBadge.setAttribute('aria-label', `Document type: ${docType}`);

  const pct = confidence !== null ? Math.round(confidence * 100) : null;
  elConfidenceDisplay.textContent = pct !== null ? `${pct}%` : '';
  elConfidenceDisplay.className = 'confidence' + (pct !== null && pct < 70 ? ' low' : '');
  elConfidenceDisplay.setAttribute('aria-label', pct !== null ? `Confidence: ${pct}%` : '');

  elReasoningText.textContent = reasoning;
}

/** Render extracted fields as a definition list. */
function renderFields(extraction) {
  elFieldsList.innerHTML = '';
  if (!extraction || typeof extraction !== 'object' || Object.keys(extraction).length === 0) {
    const dt = document.createElement('dt');
    dt.className = 'muted';
    dt.textContent = '\u2014';
    const dd = document.createElement('dd');
    dd.className = 'muted';
    dd.textContent = 'No fields extracted.';
    elFieldsList.appendChild(dt);
    elFieldsList.appendChild(dd);
    return;
  }

  const entries = Object.entries(extraction);

  const fragment = document.createDocumentFragment();
  entries.forEach(([key, value]) => {
    const dt = document.createElement('dt');
    dt.textContent = key;

    const dd = document.createElement('dd');

    if (value === null || value === undefined) {
      dd.textContent = 'null';
      dd.className = 'null-val';
    } else if (typeof value === 'object') {
      // Arrays or nested objects — render as pretty JSON
      dd.className = 'nested';
      dd.textContent = JSON.stringify(value, null, 2);
    } else {
      dd.textContent = String(value);
    }

    fragment.appendChild(dt);
    fragment.appendChild(dd);
  });

  elFieldsList.appendChild(fragment);
}

/** Render validation status. */
function renderValidation(validation) {
  elValidationResult.innerHTML = '';

  if (!validation) {
    elValidationResult.innerHTML = '<span class="muted">No validation data.</span>';
    return;
  }

  // Support {is_valid, issues} from API
  const isValid = validation.is_valid ?? validation.valid ?? (validation.status === 'pass');
  const issues  = validation.issues || validation.errors || [];
  const hasIssues = Array.isArray(issues) && issues.length > 0;

  const icon = document.createElement('span');
  icon.className = 'validation-icon ' + (isValid ? 'pass' : (hasIssues ? 'fail' : 'warn'));
  icon.setAttribute('aria-hidden', 'true');
  icon.textContent = isValid ? '✓' : '✗';

  const text = document.createElement('div');
  text.className = 'validation-text';

  const status = document.createElement('strong');
  status.textContent = isValid ? 'Passed' : 'Failed';
  text.appendChild(status);

  if (hasIssues) {
    const ul = document.createElement('ul');
    ul.className = 'validation-issues';
    ul.setAttribute('aria-label', 'Validation issues');
    issues.forEach((issue) => {
      const li = document.createElement('li');
      if (typeof issue === 'string') {
        li.textContent = issue;
      } else if (issue && issue.field) {
        li.textContent = `${issue.field}: ${issue.issue || 'invalid'}${issue.severity === 'warning' ? ' (warning)' : ''}`;
      } else {
        li.textContent = JSON.stringify(issue);
      }
      ul.appendChild(li);
    });
    text.appendChild(ul);
  }

  elValidationResult.appendChild(icon);
  elValidationResult.appendChild(text);
}

/** Render guardrail flags if any. */
function renderGuardrails(flags) {
  elGuardrailList.innerHTML = '';

  if (!Array.isArray(flags) || flags.length === 0) {
    elGuardrailCard.hidden = true;
    return;
  }

  elGuardrailCard.hidden = false;
  const fragment = document.createDocumentFragment();
  flags.forEach((flag) => {
    const li = document.createElement('li');
    li.textContent = typeof flag === 'string' ? flag : JSON.stringify(flag);
    fragment.appendChild(li);
  });
  elGuardrailList.appendChild(fragment);
}

/** Render JSON in the collapsible <details>. */
function renderJson(result) {
  elJsonOutput.textContent = JSON.stringify(result, null, 2);
  // Reset open state so it doesn't auto-expand on each run
  const details = $('json-details');
  if (details.open) details.removeAttribute('open');
}

/* ═══════════════════════════════════════════════════════════════
   Extract Button
   ═══════════════════════════════════════════════════════════════ */

function setLoadingState(loading) {
  isLoading = loading;
  elBtnExtract.disabled = loading;
  elBtnExtract.setAttribute('aria-busy', loading ? 'true' : 'false');
  elExtractStatus.textContent = loading ? 'Extracting, please wait…' : '';
}

async function handleExtract() {
  if (isLoading) return;

  const text = elDocText.value.trim();
  if (!text) {
    resetStages();
    showError('Please enter or paste document text, or load a sample above.');
    elDocText.focus();
    return;
  }

  clearApiKeyError();
  setLoadingState(true);
  stageTimers.forEach(clearTimeout);
  stageTimers = [];
  resetStages();
  showEmpty();

  try {
    const response = await apiFetch('/api/extract', {
      method: 'POST',
      body: JSON.stringify({ text }),
    });

    if (response.status === 401) {
      showApiKeyError('Invalid or missing API key.');
      showError('Authentication failed. Please check your API key.');
      return;
    }

    if (!response.ok) {
      const body = await response.text();
      let detail = `Server error (${response.status})`;
      try {
        const json = JSON.parse(body);
        detail = json.detail || json.message || detail;
      } catch (_) {
        // use the default detail string
      }
      showError(detail);
      return;
    }

    const result = await response.json();
    currentResult = result;

    if (result.stages && Array.isArray(result.stages)) {
      animateStages(result.stages);
    }

    showResults(result);

  } catch (err) {
    showError('Network error — is the server running?');
  } finally {
    setLoadingState(false);
  }
}

elBtnExtract.addEventListener('click', handleExtract);

/* Allow Ctrl+Enter in textarea to trigger extract */
elDocText.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    handleExtract();
  }
});

/* ─── API Key Error Helpers ──────────────────────────────────── */

function showApiKeyError(msg) {
  elApiKeyError.textContent = msg;
  elApiKeyError.hidden = false;
  elApiKey.setAttribute('aria-invalid', 'true');
}

function clearApiKeyError() {
  elApiKeyError.hidden = true;
  elApiKeyError.textContent = '';
  elApiKey.removeAttribute('aria-invalid');
}

elApiKey.addEventListener('input', clearApiKeyError);

/* ═══════════════════════════════════════════════════════════════
   Sample Buttons
   ═══════════════════════════════════════════════════════════════ */

/**
 * Group sample names by doc_type prefix.
 * @param {Array<{name: string, doc_type: string}>} samples
 * @returns {Map<string, string[]>}
 */
function groupSamples(samples) {
  const groups = new Map();
  samples.forEach(({ name, doc_type }) => {
    const key = doc_type || name.split('_')[0];
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(name);
  });
  return groups;
}

async function loadSamples() {
  try {
    const response = await fetch('/api/samples');
    if (!response.ok) {
      elSampleButtons.innerHTML = '<span class="muted small">Could not load samples.</span>';
      return;
    }
    const samples = await response.json();

    elSampleButtons.innerHTML = '';
    if (!samples.length) {
      elSampleButtons.innerHTML = '<span class="muted small">No samples available.</span>';
      return;
    }

    const groups = groupSamples(samples);
    const fragment = document.createDocumentFragment();

    groups.forEach((names, group) => {
      names.forEach((name, idx) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'outline sample-btn';
        btn.textContent = idx === 0
          ? capitalize(group)
          : `${capitalize(group)} ${idx + 1}`;
        btn.setAttribute('aria-label', `Load sample: ${name}`);
        btn.dataset.sampleName = name;
        btn.addEventListener('click', () => loadSample(name, btn));
        fragment.appendChild(btn);
      });
    });

    elSampleButtons.appendChild(fragment);
  } catch (_) {
    elSampleButtons.innerHTML = '<span class="muted small">Could not load samples.</span>';
  }
}

async function loadSample(name, btn) {
  const prev = btn.textContent;
  btn.disabled = true;
  btn.textContent = '…';

  try {
    const response = await fetch(`/api/samples/${encodeURIComponent(name)}`);
    if (!response.ok) return;
    const data = await response.json();
    elDocText.value = data.content || '';
    elDocText.focus();
    // Scroll to top of textarea after loading
    elDocText.setSelectionRange(0, 0);
    elDocText.scrollTop = 0;
  } catch (_) {
    // silently fail
  } finally {
    btn.disabled = false;
    btn.textContent = prev;
  }
}

/* ═══════════════════════════════════════════════════════════════
   Schema Modal
   ═══════════════════════════════════════════════════════════════ */

async function loadSchemas() {
  try {
    const response = await fetch('/api/schemas');
    if (!response.ok) {
      elSchemaCards.innerHTML = '<p class="muted">Could not load schemas.</p>';
      return;
    }
    schemasCache = await response.json();
    renderSchemaCards(schemasCache);
  } catch (_) {
    elSchemaCards.innerHTML = '<p class="muted">Could not load schemas.</p>';
  }
}

function renderSchemaCards(schemas) {
  elSchemaCards.innerHTML = '';
  if (!schemas.length) {
    elSchemaCards.innerHTML = '<p class="muted">No schemas found.</p>';
    return;
  }

  const fragment = document.createDocumentFragment();
  schemas.forEach((schema) => {
    const card = buildSchemaCard(schema);
    fragment.appendChild(card);
  });
  elSchemaCards.appendChild(fragment);
}

function buildSchemaCard(schema) {
  const card = document.createElement('details');
  card.className = 'schema-card';

  // Header / summary
  const summary = document.createElement('summary');
  summary.className = 'schema-card-header';
  summary.setAttribute('aria-label', `${schema.doc_type} schema — click to expand`);

  const titleDiv = document.createElement('div');
  titleDiv.className = 'schema-card-title';

  const badge = document.createElement('span');
  badge.className = 'schema-type-badge';
  badge.textContent = (schema.doc_type || 'unknown').replace(/_/g, ' ');

  const desc = document.createElement('span');
  desc.className = 'schema-description';
  desc.textContent = schema.description || '';

  const expandIcon = document.createElement('span');
  expandIcon.className = 'schema-expand-icon';
  expandIcon.setAttribute('aria-hidden', 'true');
  expandIcon.textContent = '▶';

  titleDiv.appendChild(badge);
  titleDiv.appendChild(desc);
  summary.appendChild(titleDiv);
  summary.appendChild(expandIcon);
  card.appendChild(summary);

  // Body
  const body = document.createElement('div');
  body.className = 'schema-card-body';

  // Field tags grid
  const grid = document.createElement('div');
  grid.className = 'schema-fields-grid';

  if (schema.required_fields && schema.required_fields.length) {
    const reqGroup = document.createElement('div');
    reqGroup.className = 'schema-field-group';
    const h4 = document.createElement('h4');
    h4.textContent = 'Required';
    const tags = document.createElement('div');
    tags.className = 'schema-field-tags';
    schema.required_fields.forEach((f) => {
      const tag = document.createElement('span');
      tag.className = 'field-tag required';
      tag.textContent = f;
      tags.appendChild(tag);
    });
    reqGroup.appendChild(h4);
    reqGroup.appendChild(tags);
    grid.appendChild(reqGroup);
  }

  if (schema.optional_fields && schema.optional_fields.length) {
    const optGroup = document.createElement('div');
    optGroup.className = 'schema-field-group';
    const h4 = document.createElement('h4');
    h4.textContent = 'Optional';
    const tags = document.createElement('div');
    tags.className = 'schema-field-tags';
    schema.optional_fields.forEach((f) => {
      const tag = document.createElement('span');
      tag.className = 'field-tag';
      tag.textContent = f;
      tags.appendChild(tag);
    });
    optGroup.appendChild(h4);
    optGroup.appendChild(tags);
    grid.appendChild(optGroup);
  }

  body.appendChild(grid);

  // YAML source toggle
  if (schema.raw_yaml) {
    const yamlToggle = document.createElement('button');
    yamlToggle.type = 'button';
    yamlToggle.className = 'outline secondary yaml-toggle-btn';
    yamlToggle.textContent = 'Show YAML source';
    yamlToggle.setAttribute('aria-expanded', 'false');
    yamlToggle.setAttribute('aria-controls', `yaml-${schema.doc_type}`);

    const yamlPre = document.createElement('pre');
    yamlPre.className = 'yaml-source';
    yamlPre.id = `yaml-${schema.doc_type}`;
    yamlPre.hidden = true;

    const yamlCode = document.createElement('code');
    yamlCode.textContent = schema.raw_yaml;
    yamlPre.appendChild(yamlCode);

    yamlToggle.addEventListener('click', () => {
      const expanded = yamlPre.hidden;
      yamlPre.hidden = !expanded;
      yamlToggle.setAttribute('aria-expanded', String(expanded));
      yamlToggle.textContent = expanded ? 'Hide YAML source' : 'Show YAML source';
    });

    body.appendChild(yamlToggle);
    body.appendChild(yamlPre);
  }

  card.appendChild(body);
  return card;
}

/* ─── Modal Open/Close ───────────────────────────────────────── */

function openModal() {
  elSchemaModal.showModal();
  // Focus the close button for keyboard accessibility
  elBtnCloseModal.focus();
}

function closeModal() {
  elSchemaModal.close();
  elBtnSchemas.focus();
}

elBtnSchemas.addEventListener('click', openModal);
elBtnCloseModal.addEventListener('click', closeModal);

// Close on backdrop click
elSchemaModal.addEventListener('click', (e) => {
  if (e.target === elSchemaModal) closeModal();
});

// Close on Escape key (browsers handle this natively for <dialog>,
// but we hook it for the button focus restoration)
elSchemaModal.addEventListener('close', () => {
  // native close event fires on Escape too
});

// Trap focus inside modal (basic: Escape already handled by <dialog>)
elSchemaModal.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    closeModal();
  }
});

/* ═══════════════════════════════════════════════════════════════
   Drag & Drop on Textarea
   ═══════════════════════════════════════════════════════════════ */

elDropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'copy';
  elDropZone.classList.add('drag-over');
});

elDropZone.addEventListener('dragleave', (e) => {
  // Only remove class if leaving the drop zone entirely
  if (!elDropZone.contains(e.relatedTarget)) {
    elDropZone.classList.remove('drag-over');
  }
});

elDropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  elDropZone.classList.remove('drag-over');

  const files = Array.from(e.dataTransfer.files);
  const txtFile = files.find((f) => f.name.endsWith('.txt') || f.type === 'text/plain');

  if (!txtFile) {
    // Ignore non-.txt drops silently
    return;
  }

  const reader = new FileReader();
  reader.onload = (ev) => {
    elDocText.value = ev.target.result || '';
    elDocText.focus();
  };
  reader.readAsText(txtFile, 'utf-8');
});

/* ═══════════════════════════════════════════════════════════════
   Initialisation
   ═══════════════════════════════════════════════════════════════ */

async function init() {
  restoreApiKey();
  showEmpty();

  // Load samples and schemas in parallel
  await Promise.allSettled([loadSamples(), loadSchemas()]);
}

// Bootstrap when DOM is ready (script is at end of body, so DOM is ready)
init();
