/* ═══════════════════════════════════════════════════════════════════
   KAI App — UI helpers, modals, toasts, navigation
   ═══════════════════════════════════════════════════════════════════ */

const App = {
  toast(msg, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container') || (() => {
      const c = document.createElement('div');
      c.id = 'toast-container';
      c.className = 'toast-container';
      document.body.appendChild(c);
      return c;
    })();

    const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.innerHTML = `<span style="font-weight:600">${icons[type] || ''}</span><span>${msg}</span>`;
    container.appendChild(el);

    setTimeout(() => {
      el.style.opacity = '0';
      el.style.transform = 'translateX(100%)';
      el.style.transition = 'all 250ms ease';
      setTimeout(() => el.remove(), 300);
    }, duration);
  },

  modal({ title, body, footer, onClose, size = 'default' }) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal" style="${size === 'large' ? 'max-width:680px' : ''}">
        <div class="modal-header">
          <h3 style="margin:0">${title || ''}</h3>
          <button class="btn btn-ghost btn-icon" id="modal-close">&times;</button>
        </div>
        <div class="modal-body">${body || ''}</div>
        ${footer ? `<div class="modal-footer">${footer}</div>` : ''}
      </div>`;
    document.body.appendChild(overlay);

    const close = () => { overlay.remove(); if (onClose) onClose(); };
    overlay.querySelector('#modal-close').onclick = close;
    overlay.addEventListener('click', e => { if (e.target === overlay) close(); });
    document.addEventListener('keydown', function esc(e) { if (e.key === 'Escape') { close(); document.removeEventListener('keydown', esc); } });

    return { overlay, close };
  },

  confirm(msg) {
    return new Promise(resolve => {
      const m = this.modal({
        title: 'Confirmar',
        body: `<p>${msg}</p>`,
        footer: `
          <button class="btn btn-ghost" id="confirm-cancel">Cancelar</button>
          <button class="btn btn-danger" id="confirm-ok">Confirmar</button>`,
      });
      m.overlay.querySelector('#confirm-cancel').onclick = () => { m.close(); resolve(false); };
      m.overlay.querySelector('#confirm-ok').onclick = () => { m.close(); resolve(true); };
    });
  },

  formatDate(iso) {
    if (!iso) return '-';
    return new Date(iso).toLocaleDateString('es-MX', { day: 'numeric', month: 'short', year: 'numeric' });
  },

  formatDateTime(iso) {
    if (!iso) return '-';
    return new Date(iso).toLocaleDateString('es-MX', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  },

  timeAgo(iso) {
    if (!iso) return '-';
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60) return 'Ahora';
    if (diff < 3600) return `Hace ${Math.floor(diff / 60)} min`;
    if (diff < 86400) return `Hace ${Math.floor(diff / 3600)} h`;
    return `Hace ${Math.floor(diff / 86400)} d`;
  },

  escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  },

  showLoading(id) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = '<div class="spinner" style="margin:2rem auto"></div>';
  },

  renderEmpty(id, msg = 'No hay datos disponibles', icon = 'inbox') {
    const el = document.getElementById(id);
    if (el) el.innerHTML = `<div class="empty-state"><i data-lucide="${icon}" style="width:3rem;height:3rem;opacity:0.3;margin-bottom:1rem"></i><p>${msg}</p></div>`;
    setTimeout(() => lucide.createIcons(), 50);
  },

  setActiveNav(page) {
    document.querySelectorAll('.sidebar-link').forEach(l => l.classList.remove('active'));
    const link = document.querySelector(`[data-page="${page}"]`);
    if (link) link.classList.add('active');
  }
};
