/* ═══════════════════════════════════════════════════════════════════
   KAI Psicólogo — Panel de psicólogo
   ═══════════════════════════════════════════════════════════════════ */

const Psicologo = {
  _page: 'estudiantes',

  async init() {
    Auth.requireRole(['psicologo', 'admin']);

    const u = Auth.user;
    document.getElementById('user-name').textContent = u.nombre;
    document.getElementById('user-email').textContent = u.email;
    document.getElementById('user-avatar').textContent = u.nombre.charAt(0).toUpperCase();

    document.querySelectorAll('.sidebar-link[data-page]').forEach(link => {
      link.onclick = (e) => { e.preventDefault(); this.navigate(link.dataset.page); };
    });

    document.getElementById('btn-logout').onclick = async () => {
      if (await App.confirm('¿Cerrar sesión?')) { await Auth.logout(); window.location.href = '/login.html'; }
    };
    document.getElementById('menu-toggle').onclick = () => document.getElementById('sidebar').classList.toggle('open');
    if (window.innerWidth <= 768) document.getElementById('menu-toggle').style.display = 'flex';

    this.navigate('estudiantes');
  },

  navigate(page) {
    this._page = page;
    App.setActiveNav(page);
    const views = { estudiantes: () => this.renderEstudiantes(), diarios: () => this.renderDiarios(), citas: () => this.renderCitas(), actividad: () => this.renderActividad(), eventos: () => this.renderEventos() };
    if (views[page]) { views[page](); setTimeout(() => lucide.createIcons(), 50); }
  },

  async renderEstudiantes() {
    document.getElementById('view-content').innerHTML = `<div class="animate-fade-in"><h2 class="mb-6" style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="graduation-cap" style="width:1.5rem;height:1.5rem;color:var(--color-primary)"></i> Mis estudiantes</h2><div id="ps-estudiantes"><div class="spinner" style="margin:3rem auto"></div></div></div>`;
    try {
      const students = await API.get('/api/psicologo/mis-estudiantes');
      const container = document.getElementById('ps-estudiantes');
      if (!students.length) { App.renderEmpty('ps-estudiantes', 'No tienes estudiantes asignados', '👥'); return; }
      container.innerHTML = students.map(s => {
        const badge = {
          activo: 'badge-success', alerta: 'badge-warning', critico: 'badge-danger', sin_registro: 'badge-neutral'
        }[s.estado || (s.dias_sin_entrar != null ? (s.dias_sin_entrar >= 14 ? 'critico' : s.dias_sin_entrar >= 7 ? 'alerta' : 'activo') : 'sin_registro')] || 'badge-neutral';
        return `
        <div class="card mb-3">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="avatar">${s.nombre.charAt(0)}</div>
              <div>
                <strong>${App.escapeHtml(s.nombre)} ${App.escapeHtml(s.apellidos || '')}</strong>
                <p class="text-xs text-muted">${s.email} · ${s.carrera || '-'}</p>
              </div>
            </div>
            <div class="flex items-center gap-2">
              ${s.categoria_problema ? `<span class="badge badge-warning">${s.categoria_problema}</span>` : ''}
              <span class="badge ${badge}">${s.dias_sin_entrar != null ? s.dias_sin_entrar + 'd' : 'Nuevo'}</span>
            </div>
          </div>
        </div>`;
      }).join('');
    } catch (e) { App.toast('Error: ' + e.message, 'error'); }
  },

  async renderDiarios() {
    document.getElementById('view-content').innerHTML = `<div class="animate-fade-in"><h2 class="mb-6" style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="book-open-text" style="width:1.5rem;height:1.5rem;color:var(--color-secondary)"></i> Diarios compartidos</h2><div id="ps-diarios"><div class="spinner" style="margin:3rem auto"></div></div></div>`;
    try {
      const entries = await API.get('/api/psicologo/diarios');
      const container = document.getElementById('ps-diarios');
      if (!entries.length) { App.renderEmpty('ps-diarios', 'No hay diarios compartidos', '📔'); return; }
      container.innerHTML = entries.map(e => `
        <div class="card mb-4" style="border-left:4px solid ${e.alerta_crisis ? 'var(--color-danger)' : 'var(--color-primary)'}">
          <div class="flex items-center justify-between mb-3">
            <div><strong>${App.escapeHtml(e.estudiante.nombre)}</strong><span class="text-xs text-muted ml-2">${e.estudiante.carrera || ''}</span></div>
            <div class="flex items-center gap-2">
              ${e.alerta_crisis ? '<span class="badge badge-danger">⚠ Crisis</span>' : ''}
              <span class="badge badge-neutral">${e.estado_animo || '-'}</span>
              <span class="text-xs text-muted">${App.formatDate(e.creada_en)}</span>
            </div>
          </div>
          <p style="white-space:pre-wrap">${App.escapeHtml(e.texto.substring(0, 300))}${e.texto.length > 300 ? '...' : ''}</p>
        </div>`).join('');
    } catch (e) { App.toast('Error: ' + e.message, 'error'); }
  },

  async renderCitas() {
    document.getElementById('view-content').innerHTML = `
      <div class="animate-fade-in">
        <h2 class="mb-6" style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="calendar" style="width:1.5rem;height:1.5rem;color:var(--color-success)"></i> Mis citas</h2>
        <div class="flex items-center gap-3 mb-6">
          <select id="ps-cita-estado" class="input" style="width:auto" onchange="Psicologo.loadCitas()">
            <option value="">Todas</option><option value="pendiente">Pendientes</option><option value="confirmada">Confirmadas</option>
          </select>
        </div>
        <div id="ps-citas-list"><div class="spinner" style="margin:3rem auto"></div></div>
      </div>`;
    await this.loadCitas();
  },

  async loadCitas() {
    const estado = document.getElementById('ps-cita-estado')?.value || '';
    try {
      let path = '/api/psicologo/citas';
      if (estado) path += `?estado=${estado}`;
      const citas = await API.get(path);
      const container = document.getElementById('ps-citas-list');
      if (!citas.length) { App.renderEmpty('ps-citas-list', 'No tienes citas', '📅'); return; }
      container.innerHTML = citas.map(c => `
        <div class="card mb-3">
          <div class="flex items-center justify-between">
            <div>
              <strong>${App.formatDateTime(c.fecha_hora)}</strong><br>
              <span class="text-sm">${App.escapeHtml(c.estudiante.nombre)} — ${c.modalidad}</span>
            </div>
            <div class="flex items-center gap-2">
              <span class="badge badge-${c.estado==='pendiente'?'warning':'success'}">${c.estado}</span>
              ${c.estado === 'pendiente' ? `<button class="btn btn-sm btn-primary" onclick="Psicologo.confirmarCita('${c.id}')">Confirmar</button>` : ''}
            </div>
          </div>
          ${c.motivo ? `<p class="text-sm mt-2 text-muted">${App.escapeHtml(c.motivo)}</p>` : ''}
        </div>`).join('');
    } catch (e) { App.toast('Error: ' + e.message, 'error'); }
  },

  async confirmarCita(id) {
    try { await API.patch(`/api/psicologo/citas/${id}/estado?estado=confirmada`, {}); App.toast('Cita confirmada', 'success'); this.loadCitas(); }
    catch (e) { App.toast('Error: ' + e.message, 'error'); }
  },

  async renderActividad() {
    document.getElementById('view-content').innerHTML = `<div class="animate-fade-in"><h2 class="mb-6" style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="activity" style="width:1.5rem;height:1.5rem;color:var(--color-warning)"></i> Actividad</h2><div id="ps-actividad"><div class="spinner" style="margin:3rem auto"></div></div></div>`;
    try {
      const data = await API.get('/api/psicologo/actividad?dias=30');
      const container = document.getElementById('ps-actividad');
      if (!data.length) { App.renderEmpty('ps-actividad', 'Sin datos de actividad', '📈'); return; }
      container.innerHTML = data.map(u => {
        const badge = { activo: 'badge-success', alerta: 'badge-warning', critico: 'badge-danger', sin_registro: 'badge-neutral' }[u.estado] || 'badge-neutral';
        return `<div class="card mb-3">
          <div class="flex items-center justify-between">
            <div><strong>${App.escapeHtml(u.nombre)}</strong><br><span class="text-xs text-muted">${u.email}</span></div>
            <div class="flex items-center gap-2">
              <span class="badge badge-neutral">Diario: ${u.entradas_periodo}</span>
              <span class="badge badge-danger">SOS: ${u.sos_periodo}</span>
              <span class="badge ${badge}">${u.dias_sin_entrar != null ? u.dias_sin_entrar + 'd' : 'Nuevo'}</span>
            </div>
          </div>
        </div>`;
      }).join('');
    } catch (e) { App.toast('Error: ' + e.message, 'error'); }
  },

  async renderEventos() {
    document.getElementById('view-content').innerHTML = `
      <div class="animate-fade-in">
        <div class="flex items-center justify-between mb-6"><h2 style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="presentation" style="width:1.5rem;height:1.5rem;color:var(--color-secondary)"></i> Eventos</h2><button class="btn btn-primary" onclick="Psicologo.showNewEvento()"><i data-lucide="plus" style="width:1rem;height:1rem"></i> Nuevo</button></div>
        <div id="ps-eventos"><div class="spinner" style="margin:3rem auto"></div></div>
      </div>`;
    try {
      const eventos = await API.get('/api/psicologo/eventos');
      const container = document.getElementById('ps-eventos');
      if (!eventos.length) { App.renderEmpty('ps-eventos', 'No has creado eventos', '📢'); return; }
      container.innerHTML = eventos.map(e => `
        <div class="card mb-3">
          <div class="flex items-center justify-between">
            <div><strong>${App.escapeHtml(e.titulo)}</strong><br><span class="text-sm text-muted">${App.formatDateTime(e.fecha_hora)} · ${e.modalidad}</span></div>
            <span class="badge ${e.activo ? 'badge-success' : 'badge-neutral'}">${e.activo ? 'Activo' : 'Inactivo'}</span>
          </div>
        </div>`).join('');
    } catch (e) { App.toast('Error: ' + e.message, 'error'); }
  },

  showNewEvento() {
    App.modal({
      title: 'Crear evento',
      body: `
        <div class="form-group"><label class="label">Título</label><input type="text" id="ev-titulo" class="input" required></div>
        <div class="form-group"><label class="label">Fecha y hora</label><input type="datetime-local" id="ev-fecha" class="input" required></div>
        <div class="form-group"><label class="label">Modalidad</label><select id="ev-modalidad" class="input"><option value="presencial">Presencial</option><option value="en_linea">En línea</option></select></div>
        <div class="form-group"><label class="label">Lugar</label><input type="text" id="ev-lugar" class="input"></div>
        <div class="form-group"><label class="label">Descripción</label><textarea id="ev-desc" class="input" rows="3"></textarea></div>
      `,
      footer: `<button class="btn btn-ghost" onclick="this.closest('.modal-overlay').remove()">Cancelar</button><button class="btn btn-primary" id="ev-save">Crear</button>`
    });
    document.getElementById('ev-save').onclick = async () => {
      try {
        await API.post('/api/psicologo/eventos', {
          titulo: document.getElementById('ev-titulo').value,
          fecha_hora: new Date(document.getElementById('ev-fecha').value).toISOString(),
          modalidad: document.getElementById('ev-modalidad').value,
          lugar: document.getElementById('ev-lugar').value || null,
          descripcion: document.getElementById('ev-desc').value || null,
        });
        document.querySelector('.modal-overlay').remove();
        App.toast('Evento creado', 'success');
        this.renderEventos();
      } catch (e) { App.toast('Error: ' + e.message, 'error'); }
    };
  }
};
