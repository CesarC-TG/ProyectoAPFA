/* ═══════════════════════════════════════════════════════════════════
   KAI Admin — Panel de administración
   ═══════════════════════════════════════════════════════════════════ */

const Admin = {
  _page: 'stats',

  async init() {
    Auth.requireRole(['admin']);

    // User info
    const u = Auth.user;
    document.getElementById('user-name').textContent = u.nombre;
    document.getElementById('user-email').textContent = u.email;
    const avatar = document.getElementById('user-avatar');
    avatar.textContent = u.nombre.charAt(0).toUpperCase();

    // Nav
    document.querySelectorAll('.sidebar-link[data-page]').forEach(link => {
      link.onclick = (e) => { e.preventDefault(); this.navigate(link.dataset.page); };
    });

    document.getElementById('btn-logout').onclick = async () => {
      if (await App.confirm('¿Cerrar sesión?')) {
        await Auth.logout(); window.location.href = '/login.html';
      }
    };

    document.getElementById('menu-toggle').onclick = () => {
      document.getElementById('sidebar').classList.toggle('open');
    };

    if (window.innerWidth <= 768) document.getElementById('menu-toggle').style.display = 'flex';

    this.navigate('stats');
  },

  navigate(page) {
    this._page = page;
    App.setActiveNav(page);
    const views = { stats: () => this.renderStats(), usuarios: () => this.renderUsuarios(), actividad: () => this.renderActividad(), citas: () => this.renderCitas() };
    if (views[page]) { views[page](); setTimeout(() => lucide.createIcons(), 50); }
  },

  async renderStats() {
    document.getElementById('view-content').innerHTML = `<div class="animate-fade-in"><h2 class="mb-6" style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="layout-dashboard" style="width:1.5rem;height:1.5rem;color:var(--color-primary)"></i> Panel de control</h2><div id="stats-grid" class="bento-grid-3 mb-6"></div><div id="mood-chart" class="card"><h3>Estados de ánimo (30 días)</h3><div id="mood-data" style="margin-top:1rem"></div></div></div>`;

    try {
      const [stats, moods] = await Promise.all([
        API.get('/api/admin/stats'),
        API.get('/api/admin/reportes/estados-animo?dias=30')
      ]);

      document.getElementById('stats-grid').innerHTML = `
        <div class="bento-card"><div class="stat-value">${stats.total_estudiantes}</div><div class="stat-label">Estudiantes activos</div></div>
        <div class="bento-card"><div class="stat-value">${stats.total_psicologos}</div><div class="stat-label">Psicólogos</div></div>
        <div class="bento-card"><div class="stat-value">${stats.entradas_hoy}</div><div class="stat-label">Entradas hoy</div></div>
        <div class="bento-card"><div class="stat-value">${stats.alertas_activas}</div><div class="stat-label" style="color:var(--color-danger)">Alertas activas</div></div>
        <div class="bento-card"><div class="stat-value">${stats.entradas_compartidas}</div><div class="stat-label">Entradas compartidas</div></div>
        <div class="bento-card"><div class="stat-value">${stats.sesiones_chat_semana}</div><div class="stat-label">Chats (7 días)</div></div>`;

      if (moods && moods.length) {
        document.getElementById('mood-data').innerHTML = moods.map(m => `
          <div class="flex items-center justify-between" style="padding:var(--space-2) 0;border-bottom:1px solid var(--color-border)">
            <span>${m.estado || 'Sin registro'}</span>
            <span class="badge badge-neutral">${m.total}</span>
          </div>`).join('');
      }
    } catch (e) { App.toast('Error: ' + e.message, 'error'); }
  },

  async renderUsuarios() {
    document.getElementById('view-content').innerHTML = `
      <div class="animate-fade-in">
        <div class="flex items-center justify-between mb-6">
          <h2 style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="users" style="width:1.5rem;height:1.5rem;color:var(--color-secondary)"></i> Usuarios</h2>
          <button class="btn btn-primary" onclick="Admin.showCreateUser()"><i data-lucide="user-plus" style="width:1rem;height:1rem"></i> Nuevo usuario</button>
        </div>
        <div class="flex items-center gap-3 mb-6">
          <select id="user-rol-filter" class="input" style="width:auto" onchange="Admin.loadUsuarios()">
            <option value="">Todos los roles</option>
            <option value="estudiante">Estudiantes</option>
            <option value="psicologo">Psicólogos</option>
            <option value="admin">Admins</option>
          </select>
          <input type="text" id="user-search" class="input" placeholder="Buscar..." style="width:200px" oninput="Admin.loadUsuarios()">
        </div>
        <div id="users-list"><div class="spinner" style="margin:3rem auto"></div></div>
      </div>`;
    await this.loadUsuarios();
  },

  async loadUsuarios() {
    const rol = document.getElementById('user-rol-filter')?.value || '';
    const search = document.getElementById('user-search')?.value || '';
    try {
      let path = '/api/admin/usuarios?por_pagina=50';
        if (rol) path += `&rol=${rol}`;
      if (search) path += `&buscar=${encodeURIComponent(search)}`;
      const users = await API.get(path);
      const container = document.getElementById('users-list');
      setTimeout(() => lucide.createIcons(), 50);

      container.innerHTML = users.map(u => `
        <div class="card mb-3">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="avatar">${u.nombre.charAt(0).toUpperCase()}</div>
              <div>
                <strong>${App.escapeHtml(u.nombre)} ${App.escapeHtml(u.apellidos || '')}</strong>
                <p class="text-xs text-muted">${u.email}</p>
              </div>
            </div>
            <div class="flex items-center gap-3">
              <span class="badge badge-info">${u.rol}</span>
              ${u.activo ? '<span class="badge badge-success">Activo</span>' : '<span class="badge badge-danger">Inactivo</span>'}
              <button class="btn btn-sm btn-ghost" onclick="Admin.editUser('${u.id}')"><i data-lucide="pencil" style="width:0.875rem;height:0.875rem"></i></button>
            </div>
          </div>
        </div>`).join('');
    } catch (e) { App.toast('Error: ' + e.message, 'error'); }
  },

  async renderActividad() {
    document.getElementById('view-content').innerHTML = `<div class="animate-fade-in"><h2 class="mb-6" style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="activity" style="width:1.5rem;height:1.5rem;color:var(--color-warning)"></i> Actividad de usuarios</h2><div id="actividad-list"><div class="spinner" style="margin:3rem auto"></div></div></div>`;
    try {
      const data = await API.get('/api/admin/actividad-usuarios?dias=30');
      const container = document.getElementById('actividad-list');
      container.innerHTML = data.map(u => {
        const badge = {
          activo: 'badge-success', alerta: 'badge-warning', critico: 'badge-danger', sin_registro: 'badge-neutral'
        }[u.estado] || 'badge-neutral';
        return `
        <div class="card mb-3">
          <div class="flex items-center justify-between">
            <div>
              <strong>${App.escapeHtml(u.nombre)}</strong>
              <p class="text-xs text-muted">${u.email} · ${u.carrera || '-'}</p>
            </div>
            <div class="flex items-center gap-3">
              <span class="text-xs text-muted">${u.dias_sin_entrar != null ? u.dias_sin_entrar + 'd' : 'Nunca'}</span>
              <span class="badge ${badge}">${u.estado}</span>
              <span class="badge badge-neutral">SOS: ${u.sos_periodo}</span>
            </div>
          </div>
        </div>`;
      }).join('');
    } catch (e) { App.toast('Error: ' + e.message, 'error'); }
  },

  async renderCitas() {
    document.getElementById('view-content').innerHTML = `
      <div class="animate-fade-in">
        <h2 class="mb-6" style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="calendar-check" style="width:1.5rem;height:1.5rem;color:var(--color-success)"></i> Gestión de citas</h2>
        <div class="flex items-center gap-3 mb-6">
          <select id="admin-cita-estado" class="input" style="width:auto" onchange="Admin.loadCitas()">
            <option value="">Todos</option>
            <option value="pendiente">Pendientes</option>
            <option value="confirmada">Confirmadas</option>
            <option value="cancelada">Canceladas</option>
          </select>
        </div>
        <div id="admin-citas-list"><div class="spinner" style="margin:3rem auto"></div></div>
      </div>`;
    await this.loadCitas();
  },

  async loadCitas() {
    const estado = document.getElementById('admin-cita-estado')?.value || '';
    try {
      let path = '/api/admin/citas';
      if (estado) path += `?estado=${estado}`;
      const citas = await API.get(path);
      const container = document.getElementById('admin-citas-list');
      container.innerHTML = citas.length ? citas.map(c => `
        <div class="card mb-3">
          <div class="flex items-center justify-between">
            <div><strong>${App.formatDateTime(c.fecha_hora)}</strong><br><span class="text-xs text-muted">${c.modalidad}</span></div>
            <div class="flex items-center gap-2">
              <span class="badge badge-${c.estado==='pendiente'?'warning':c.estado==='confirmada'?'success':'danger'}">${c.estado}</span>
              ${c.estado === 'pendiente' ? `<button class="btn btn-sm btn-primary" onclick="Admin.updateCitaEstado('${c.id}','confirmada')">Confirmar</button>` : ''}
            </div>
          </div>
        </div>`).join('') : '<div class="empty-state"><div class="icon">📅</div><p>No hay citas</p></div>';
    } catch (e) { App.toast('Error: ' + e.message, 'error'); }
  },

  async updateCitaEstado(id, estado) {
    try { await API.patch(`/api/admin/citas/${id}/estado?estado=${estado}`, {}); App.toast('Cita actualizada', 'success'); this.loadCitas(); }
    catch (e) { App.toast('Error: ' + e.message, 'error'); }
  },

  showCreateUser() {
    App.modal({
      title: 'Crear usuario',
      body: `
        <div class="form-group"><label class="label">Nombre</label><input type="text" id="new-name" class="input" required></div>
        <div class="form-group"><label class="label">Email</label><input type="email" id="new-email" class="input" required></div>
        <div class="form-group"><label class="label">Contraseña (mín. 8)</label><input type="password" id="new-pw" class="input" required minlength="8"></div>
        <div class="form-group"><label class="label">Rol</label><select id="new-rol" class="input"><option value="estudiante">Estudiante</option><option value="psicologo">Psicólogo</option><option value="admin">Admin</option></select></div>
      `,
      footer: `<button class="btn btn-ghost" onclick="this.closest('.modal-overlay').remove()">Cancelar</button><button class="btn btn-primary" id="create-user-btn">Crear</button>`
    });
    document.getElementById('create-user-btn').onclick = async () => {
      try {
        await API.post('/api/admin/usuarios', {
          nombre: document.getElementById('new-name').value,
          email: document.getElementById('new-email').value,
          password: document.getElementById('new-pw').value,
          rol: document.getElementById('new-rol').value,
        });
        document.querySelector('.modal-overlay').remove();
        App.toast('Usuario creado', 'success');
        this.renderUsuarios();
      } catch (e) { App.toast('Error: ' + e.message, 'error'); }
    };
  },

  async editUser(id) {
    App.toast('Funcionalidad en desarrollo', 'info');
  }
};
