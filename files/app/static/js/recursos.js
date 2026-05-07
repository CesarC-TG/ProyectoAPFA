/* ═══════════════════════════════════════════════════════════════════
   KAI Recursos — Biblioteca de bienestar
   ═══════════════════════════════════════════════════════════════════ */

const Recursos = {
  _filter: null,

  async render() {
    document.getElementById('view-content').innerHTML = `
      <div class="animate-fade-in">
        <div class="flex items-center justify-between mb-6">
          <h2 style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="heart" style="width:1.5rem;height:1.5rem;color:var(--color-accent)"></i> Recursos de bienestar</h2>
          <div class="flex items-center gap-3">
            <input type="text" id="recurso-search" class="input" placeholder="Buscar recursos..." style="width:200px" oninput="Recursos.search()">
          </div>
        </div>
        <div class="flex flex-wrap gap-2 mb-6" id="recurso-filters"></div>
        <div class="bento-grid" id="recursos-grid"><div class="spinner" style="margin:3rem auto"></div></div>
      </div>`;
    await this.loadFilters();
    await this.loadAll();
    setTimeout(() => lucide.createIcons(), 50);
  },

  async loadFilters() {
    try {
      const tipos = await API.get('/api/recursos/tipos');
      const container = document.getElementById('recurso-filters');
      container.innerHTML = `
        <button class="btn btn-sm ${!this._filter ? 'btn-primary' : 'btn-ghost'}" onclick="Recursos.setFilter(null)">Todos</button>
        ${tipos.map(t => `<button class="btn btn-sm ${this._filter === t ? 'btn-primary' : 'btn-ghost'}" onclick="Recursos.setFilter('${t}')">${t.replace('_',' ')}</button>`).join('')}`;
    } catch {}
  },

  setFilter(tipo) {
    this._filter = tipo;
    this.render();
  },

  async search() {
    const q = document.getElementById('recurso-search')?.value || '';
    await this.loadAll(q);
  },

  async loadAll(search = '') {
    try {
      let path = '/api/recursos/?por_pagina=30';
      if (this._filter) path += `&tipo=${this._filter}`;
      if (search) path += `&buscar=${encodeURIComponent(search)}`;

      const data = await API.get(path);
      const grid = document.getElementById('recursos-grid');
      if (!data || data.length === 0) {
        App.renderEmpty('recursos-grid', 'No se encontraron recursos', 'heart');
        return;
      }

      const icons = { respiracion: 'wind', meditacion: 'sun', ejercicio: 'dumbbell', lectura: 'book-text', video: 'play-circle', clinica: 'building-2', linea_crisis: 'phone-call' };
      grid.innerHTML = data.map(r => `
        <div class="bento-card" onclick="Recursos.openDetail('${r.id}')" style="cursor:pointer">
          <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.75rem;min-width:0">
            <i data-lucide="${icons[r.tipo] || 'bookmark'}" style="width:1.5rem;height:1.5rem;color:var(--color-primary);flex-shrink:0"></i>
            <div>
              <h4 style="margin:0">${App.escapeHtml(r.titulo)}</h4>
              <span class="badge badge-neutral">${r.tipo.replace('_',' ')}</span>
            </div>
          </div>
          ${r.descripcion ? `<p class="text-sm text-muted mb-3" style="overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical">${App.escapeHtml(r.descripcion.substring(0, 100))}${r.descripcion.length>100?'...':''}</p>` : ''}
          <div class="flex items-center justify-between">
            ${r.duracion_minutos ? `<span class="text-xs text-muted">⏱ ${r.duracion_minutos} min</span>` : '<span></span>'}
            ${r.disponible_24h ? '<span class="badge badge-success">24/7</span>' : ''}
          </div>
        </div>`).join('');
    } catch (e) {
      App.toast('Error al cargar recursos: ' + e.message, 'error');
    }
  },

  async openDetail(id) {
    try {
      const r = await API.get(`/api/recursos/${id}`);
      let body = `<p style="margin-bottom:var(--space-4)">${App.escapeHtml(r.descripcion || '')}</p>`;

      if (r.contenido && r.contenido.pasos) {
        body += '<div style="background:var(--color-surface);border-radius:var(--radius-md);padding:var(--space-4);margin-bottom:var(--space-4)">';
        body += '<h4 style="margin-bottom:var(--space-3)">Pasos a seguir</h4>';
        body += r.contenido.pasos.map((p, i) => `<p style="font-size:var(--text-sm);padding:var(--space-2) 0;border-bottom:1px solid var(--color-border)"><strong>${i + 1}.</strong> ${App.escapeHtml(p)}</p>`).join('');
        body += '</div>';
      }

      if (r.telefono) body += `<p class="text-sm mt-4">📞 <a href="tel:${r.telefono}">${r.telefono}</a></p>`;
      if (r.direccion) body += `<p class="text-sm">📍 ${App.escapeHtml(r.direccion)}</p>`;
      if (r.horario) body += `<p class="text-sm">🕐 ${App.escapeHtml(r.horario)}</p>`;
      if (r.url_externo) body += `<p class="mt-4"><a href="${r.url_externo}" target="_blank" class="btn btn-outline btn-sm">Ir al recurso →</a></p>`;

      App.modal({ title: `${r.titulo}`, body, footer: '<button class="btn btn-ghost" onclick="this.closest(\'.modal-overlay\').remove()">Cerrar</button>' });
      setTimeout(() => lucide.createIcons(), 50);
    } catch (e) {
      App.toast('Error al cargar recurso: ' + e.message, 'error');
    }
  }
};
