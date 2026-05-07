/* ═══════════════════════════════════════════════════════════════════
   KAI Diario — Entradas emocionales
   ═══════════════════════════════════════════════════════════════════ */

const Diario = {
  _page: 1,

  async render() {
    document.getElementById('view-content').innerHTML = `
      <div class="animate-fade-in">
        <div class="flex items-center justify-between mb-6">
          <h2 style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="book-open" style="width:1.5rem;height:1.5rem;color:var(--color-primary)"></i> Diario emocional</h2>
          <button class="btn btn-primary" onclick="Diario.showNewEntry()">Nueva entrada</button>
        </div>
        <div id="diario-list"><div class="spinner" style="margin:3rem auto"></div></div>
        <div id="diario-pagination" class="flex justify-center gap-3 mt-6"></div>
      </div>`;
    await this.load();
  },

  async load(page = 1) {
    this._page = page;
    try {
      const data = await API.get(`/api/diario/?pagina=${page}&por_pagina=10`);
      const container = document.getElementById('diario-list');

      if (!data.entradas || data.entradas.length === 0) {
        App.renderEmpty('diario-list', 'Aún no has escrito ninguna entrada. Empieza tu diario.', 'book-open');
        return;
      }

      container.innerHTML = data.entradas.map(e => `
        <div class="card mb-4" style="border-left:4px solid ${e.alerta_crisis ? 'var(--color-danger)' : 'var(--color-primary)'}">
          <div class="flex items-center justify-between mb-3">
            <span style="font-size:1.25rem">${e.estado_animo || '·'}</span>
            <div class="flex items-center gap-2">
              ${e.alerta_crisis ? '<span class="badge badge-danger">⚠ Crisis</span>' : ''}
              ${e.compartida ? '<span class="badge badge-info">Compartida</span>' : ''}
              <span class="text-xs text-muted">${App.formatDate(e.creada_en)}</span>
            </div>
          </div>
          <p style="white-space:pre-wrap;line-height:1.6">${App.escapeHtml(e.texto)}</p>
          ${e.etiquetas && e.etiquetas.length ? `<div class="flex flex-wrap gap-2 mt-3">${e.etiquetas.map(t => `<span class="badge badge-neutral">#${t}</span>`).join('')}</div>` : ''}
          ${e.analisis_ia && e.analisis_ia.resumen_breve ? `<p class="text-sm text-muted mt-3" style="font-style:italic">💡 ${App.escapeHtml(e.analisis_ia.resumen_breve)}</p>` : ''}
          <div class="flex items-center gap-3 mt-4">
            <button class="btn btn-sm btn-ghost" onclick="Diario.shareEntry('${e.id}')"><i data-lucide="share-2" style="width:0.875rem;height:0.875rem"></i> Compartir con psicólogo</button>
          </div>
        </div>`).join('');

      // Paginación
      const totalPages = Math.ceil(data.total / data.por_pagina);
      if (totalPages > 1) {
        const pag = document.getElementById('diario-pagination');
        let html = '';
        if (page > 1) html += `<button class="btn btn-sm btn-ghost" onclick="Diario.load(${page - 1})">← Anterior</button>`;
        html += `<span class="text-sm text-muted" style="padding:0.5rem">Página ${page} de ${totalPages}</span>`;
        if (page < totalPages) html += `<button class="btn btn-sm btn-ghost" onclick="Diario.load(${page + 1})">Siguiente →</button>`;
        pag.innerHTML = html;
      }
    } catch (e) {
      App.toast('Error al cargar el diario: ' + e.message, 'error');
    }
  },

  showNewEntry() {
    const moods = ['😄','😊','😐','😔','😰','😤','😞'];
    let selectedMood = null;

    App.modal({
      title: 'Nueva entrada de diario',
      body: `
        <div class="form-group">
          <label class="label">¿Cómo te sientes?</label>
          <div class="mood-grid" id="diario-moods">
            ${moods.map(m => `<button class="mood-btn" data-mood="${m}" onclick="this.parentElement.querySelectorAll('.mood-btn').forEach(b=>b.classList.remove('selected'));this.classList.add('selected');window._diaryMood='${m}'">${m}</button>`).join('')}
          </div>
        </div>
        <div class="form-group">
          <label class="label" for="diario-texto">Escribe lo que sientes...</label>
          <textarea id="diario-texto" class="input" rows="6" placeholder="Hoy me siento..." maxlength="10000"></textarea>
          <span class="help-text">Máximo 10,000 caracteres</span>
        </div>
        <div class="form-group">
          <label class="label" for="diario-tags">Etiquetas (separadas por coma)</label>
          <input type="text" id="diario-tags" class="input" placeholder="ansiedad, universidad, familia">
        </div>
      `,
      footer: `
        <button class="btn btn-ghost" id="diario-cancel">Cancelar</button>
        <button class="btn btn-primary" id="diario-save">Guardar entrada</button>
      `,
      onClose: () => { window._diaryMood = null; }
    });
    setTimeout(() => lucide.createIcons(), 50);

    document.getElementById('diario-cancel').onclick = () => {
      document.querySelector('.modal-overlay').remove();
    };

    document.getElementById('diario-save').onclick = async () => {
      const texto = document.getElementById('diario-texto').value.trim();
      if (!texto) { App.toast('Escribe algo antes de guardar', 'warning'); return; }

      const btn = document.getElementById('diario-save');
      btn.disabled = true; btn.textContent = 'Guardando...';
      try {
        const tags = document.getElementById('diario-tags').value.split(',').map(t => t.trim()).filter(Boolean);
        await API.post('/api/diario/', {
          texto,
          estado_animo: window._diaryMood || null,
          etiquetas: tags,
          compartida: false
        });
        document.querySelector('.modal-overlay').remove();
        App.toast('¡Entrada guardada! Tu diario se está analizando.', 'success');
        Diario.render();
      } catch (e) {
        App.toast('Error: ' + e.message, 'error');
        btn.disabled = false; btn.textContent = 'Guardar entrada';
      }
    };
  },

  async shareEntry(id) {
    const ok = await App.confirm('¿Compartir esta entrada con tu psicólogo asignado?');
    if (!ok) return;
    try {
      await API.patch(`/api/diario/${id}/compartir`, {});
      App.toast('Entrada compartida con tu psicólogo ✓', 'success');
      this.render();
      setTimeout(() => lucide.createIcons(), 50);
    } catch (e) {
      App.toast('Error: ' + e.message, 'error');
    }
  }
};
