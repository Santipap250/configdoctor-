// static/js/motor_prop.js — OBIXConfig Doctor v5.2
// Companion script for motor_prop.html
// Handles: CLI copy button (id="cliCopyBtn") + keyboard shortcut

'use strict';

document.addEventListener('DOMContentLoaded', () => {

  /* ── CLI Copy Button ────────────────────────────────────────────────── */
  // Button id="cliCopyBtn" is rendered by Jinja2 inside the results block.
  // Use event delegation so it works whether results are present at load or
  // rendered after a form submit (no re-registration needed).
  document.body.addEventListener('click', (e) => {
    const btn = e.target.closest('#cliCopyBtn');
    if (!btn) return;

    // Collect all CLI span elements (cli_c1–cli_c4, cli_1–cli_6)
    const spans = document.querySelectorAll(
      '#cli_c1,#cli_c2,#cli_c3,#cli_c4,#cli_1,#cli_2,#cli_3,#cli_4,#cli_5,#cli_6'
    );
    const text = Array.from(spans)
      .map(s => s.textContent.trim())
      .filter(Boolean)
      .join('\n');

    if (!text) return;

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        _flashBtn(btn, 'คัดลอกแล้ว!');
      }).catch(() => _fallbackCopy(text, btn));
    } else {
      _fallbackCopy(text, btn);
    }
  });

  /* ── Keyboard shortcut: Ctrl/Cmd + Shift + C ────────────────────────── */
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'C') {
      const btn = document.getElementById('cliCopyBtn');
      if (btn) btn.click();
    }
  });

  /* ── Helpers ─────────────────────────────────────────────────────────── */
  function _fallbackCopy(text, btn) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;opacity:0;pointer-events:none;';
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand('copy');
      _flashBtn(btn, 'คัดลอกแล้ว!');
    } catch (_) {
      _flashBtn(btn, 'คัดลอกไม่ได้');
    }
    document.body.removeChild(ta);
  }

  function _flashBtn(btn, msg) {
    const orig = btn.textContent;
    btn.textContent = msg;
    btn.disabled = true;
    setTimeout(() => {
      btn.textContent = orig;
      btn.disabled = false;
    }, 1800);
  }

});
