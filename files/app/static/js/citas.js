/* ═══════════════════════════════════════════════════════════════════
   KAI Citas — Gestión de citas del estudiante
   ═══════════════════════════════════════════════════════════════════ */

const Citas = {
  async render() {
    document.getElementById('view-content').innerHTML = `
      <div class="animate-fade-in">
        <div class="flex items-center justify-between mb-6">
          <h2 style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="calendar" style="width:1.5rem;height:1.5rem;color:var(--color-success)"></i> Mis citas</h2>
          <button class="btn btn-primary" onclick="Citas.showNew()">Agendar cita</button>
        </div>
        <div id="citas-list"><div class="spinner" style="margin:3rem auto"></div></div>
      </div>`;
    await this.load();
    setTimeout(() => lucide.createIcons(), 50);
  },

  async load() {
    try {
      const citas = await API.get('/api/users/me/citas');
      const container = document.getElementById('citas-list');
      if (!citas || citas.length === 0) {
        App.renderEmpty('citas-list', 'No tienes citas agendadas', 'calendar');
        return;
      }

      container.innerHTML = citas.map(c => {
        const statusBadge = {
          pendiente: 'badge-warning',
          confirmada: 'badge-success',
          cancelada: 'badge-danger',
          completada: 'badge-info'
        }[c.estado] || 'badge-neutral';

        return `
        <div class="card mb-4">
          <div class="flex items-center justify-between">
            <div style="display:flex;align-items:center;gap:0.75rem;min-width:0">
              <i data-lucide="${c.modalidad === 'videollamada' ? 'video' : 'building-2'}" style="width:1.5rem;height:1.5rem;color:var(--color-secondary);flex-shrink:0"></i>
              <div>
                <h4 style="margin:0">${App.formatDateTime(c.fecha_hora)}</h4>
                <span class="text-sm text-muted">${c.modalidad} · ${c.duracion_minutos} min</span>
              </div>
            </div>
            <span class="badge ${statusBadge}">${c.estado}</span>
          </div>
          ${c.motivo ? `<p class="text-sm mt-3">${App.escapeHtml(c.motivo)}</p>` : ''}
          ${c.estado === 'pendiente' ? `
          <div class="flex items-center gap-3 mt-4">
            <button class="btn btn-sm btn-primary" onclick="Citas.confirm('${c.id}')">✓ Confirmar</button>
            <button class="btn btn-sm btn-ghost" onclick="Citas.cancel('${c.id}')">Cancelar</button>
          </div>` : ''}
        </div>`;
      }).join('');
    } catch (e) {
      App.toast('Error al cargar citas: ' + e.message, 'error');
    }
  },

  async confirm(id) {
    try {
      await API.patch(`/api/users/me/citas/${id}/confirmar`, {});
      App.toast('Cita confirmada', 'success');
      await this.render();
      setTimeout(() => lucide.createIcons(), 50);
    } catch (e) { App.toast('Error: ' + e.message, 'error'); }
  },

  async cancel(id) {
    const ok = await App.confirm('¿Cancelar esta cita?');
    if (!ok) return;
    try {
      await API.delete(`/api/users/me/citas/${id}`);
      App.toast('Cita cancelada', 'info');
      this.render();
    } catch (e) { App.toast('Error: ' + e.message, 'error'); }
  },

  async showNew() {
    try {
      const psicologos = await API.get('/api/users/psicologos');
      if (!psicologos || psicologos.length === 0) {
        App.toast('No hay psicólogos disponibles en este momento', 'warning');
        return;
      }

      const options = psicologos.map(p =>
        `<option value="${p.id}">${p.nombre} ${p.apellidos || ''}</option>`
      ).join('');

      App.modal({
        title: 'Agendar nueva cita',
        body: `
          <div class="form-group">
            <label class="label" for="cita-psicologo">Psicólogo</label>
            <select id="cita-psicologo" class="input">${options}</select>
          </div>
          <div class="form-group">
            <label class="label" for="cita-fecha">Fecha y hora</label>
            <input type="datetime-local" id="cita-fecha" class="input" required>
          </div>
          <div class="form-group">
            <label class="label" for="cita-modalidad">Modalidad</label>
            <select id="cita-modalidad" class="input">
              <option value="presencial">Presencial</option>
              <option value="videollamada">Videollamada</option>
            </select>
          </div>
          <div class="form-group">
            <label class="label" for="cita-motivo">Motivo (opcional)</label>
            <textarea id="cita-motivo" class="input" rows="3" placeholder="Breve descripción..."></textarea>
          </div>
        `,
        footer: `
          <button class="btn btn-ghost" onclick="this.closest('.modal-overlay').remove()">Cancelar</button>
          <button class="btn btn-primary" id="cita-save">Agendar</button>
        `
      });

      document.getElementById('cita-save').onclick = async () => {
        const btn = document.getElementById('cita-save');
        btn.disabled = true; btn.textContent = 'Agendando...';
        try {
          await API.post('/api/users/me/citas', {
            psicologo_id: document.getElementById('cita-psicologo').value,
            fecha_hora: new Date(document.getElementById('cita-fecha').value).toISOString(),
            modalidad: document.getElementById('cita-modalidad').value,
            motivo: document.getElementById('cita-motivo').value.trim() || null,
          });
          document.querySelector('.modal-overlay').remove();
          App.toast('¡Cita agendada!', 'success');
          this.render();
        } catch (e) { App.toast('Error: ' + e.message, 'error'); btn.disabled = false; btn.textContent = 'Agendar'; }
      };
    } catch (e) {
      App.toast('Error: ' + e.message, 'error');
    }
  }
};
