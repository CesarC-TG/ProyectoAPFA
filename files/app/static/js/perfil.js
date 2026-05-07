/* ═══════════════════════════════════════════════════════════════════
   KAI Perfil — Gestión del perfil de usuario
   ═══════════════════════════════════════════════════════════════════ */

const Perfil = {
  async render() {
    const u = Auth.user;
    document.getElementById('view-content').innerHTML = `
      <div class="animate-fade-in" style="max-width:640px">
        <h2 class="mb-6" style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="user" style="width:1.5rem;height:1.5rem;color:var(--color-secondary)"></i> Mi perfil</h2>
        <div class="card mb-6" style="text-align:center">
          <div class="avatar avatar-lg" style="margin:0 auto var(--space-4)" id="perfil-avatar">
            ${u.avatar_url ? `<img src="${u.avatar_url}" alt="${u.nombre}">` : u.nombre.charAt(0).toUpperCase()}
          </div>
          <h3>${u.nombre} ${u.apellidos || ''}</h3>
          <p class="text-muted">${u.email}</p>
          <span class="badge badge-info">${u.rol}</span>
          <div class="mt-4">
            <label class="btn btn-sm btn-outline" style="cursor:pointer">
              <i data-lucide="camera" style="width:1rem;height:1rem"></i> Cambiar foto
              <input type="file" accept="image/jpeg,image/png,image/webp" style="display:none" onchange="Perfil.uploadAvatar(this)">
            </label>
          </div>
        </div>
        <form id="perfil-form" class="card">
          <div class="grid" style="grid-template-columns:1fr 1fr;gap:var(--space-4)">
            <div class="form-group">
              <label class="label" for="pf-nombre">Nombre</label>
              <input type="text" id="pf-nombre" class="input" value="${App.escapeHtml(u.nombre)}" required>
            </div>
            <div class="form-group">
              <label class="label" for="pf-apellidos">Apellidos</label>
              <input type="text" id="pf-apellidos" class="input" value="${App.escapeHtml(u.apellidos || '')}">
            </div>
            <div class="form-group">
              <label class="label" for="pf-carrera">Carrera</label>
              <input type="text" id="pf-carrera" class="input" value="${App.escapeHtml(u.carrera || '')}">
            </div>
            <div class="form-group">
              <label class="label" for="pf-semestre">Semestre</label>
              <input type="number" id="pf-semestre" class="input" min="1" max="12" value="${u.semestre || ''}">
            </div>
            <div class="form-group">
              <label class="label" for="pf-telefono">Teléfono</label>
              <input type="text" id="pf-telefono" class="input" value="${App.escapeHtml(u.telefono || '')}">
            </div>
          </div>
          <h4 class="mt-6 mb-4">Contacto de emergencia</h4>
          <div class="grid" style="grid-template-columns:1fr 1fr;gap:var(--space-4)">
            <div class="form-group">
              <label class="label" for="pf-em-nombre">Nombre</label>
              <input type="text" id="pf-em-nombre" class="input" value="${App.escapeHtml(u.emergencia_nombre || '')}">
            </div>
            <div class="form-group">
              <label class="label" for="pf-em-telefono">Teléfono</label>
              <input type="text" id="pf-em-telefono" class="input" value="${App.escapeHtml(u.emergencia_telefono || '')}">
            </div>
            <div class="form-group" style="grid-column:span 2">
              <label class="label" for="pf-em-email">Email</label>
              <input type="email" id="pf-em-email" class="input" value="${App.escapeHtml(u.emergencia_email || '')}">
            </div>
          </div>
          <button type="submit" class="btn btn-primary mt-6">Guardar cambios</button>
        </form>
        <button class="btn btn-outline w-full mt-4" onclick="Perfil.exportData()"><i data-lucide="download" style="width:1rem;height:1rem"></i> Exportar mis datos</button>
      </div>`;

    document.getElementById('perfil-form').onsubmit = async (e) => {
      e.preventDefault();
      try {
        await Auth.updateProfile({
          nombre: document.getElementById('pf-nombre').value.trim(),
          apellidos: document.getElementById('pf-apellidos').value.trim() || null,
          carrera: document.getElementById('pf-carrera').value.trim() || null,
          semestre: parseInt(document.getElementById('pf-semestre').value) || null,
          telefono: document.getElementById('pf-telefono').value.trim() || null,
          emergencia_nombre: document.getElementById('pf-em-nombre').value.trim() || null,
          emergencia_telefono: document.getElementById('pf-em-telefono').value.trim() || null,
          emergencia_email: document.getElementById('pf-em-email').value.trim() || null,
        });
        App.toast('Perfil actualizado ✓', 'success');
      } catch (e) { App.toast('Error: ' + e.message, 'error'); }
    };
  },

  async uploadAvatar(input) {
    const file = input.files[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { App.toast('El archivo pesa más de 10 MB', 'error'); return; }
    try {
      await Auth.uploadAvatar(file);
      App.toast('Avatar actualizado ✓', 'success');
        this.render();
        setTimeout(() => lucide.createIcons(), 50);
      } catch (e) { App.toast('Error: ' + e.message, 'error'); }
    };
  },

  async exportData() {
    try {
      const data = await API.get('/api/users/me/exportar');
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'kai-mis-datos.json'; a.click();
      URL.revokeObjectURL(url);
      App.toast('Datos exportados ✓', 'success');
    } catch (e) { App.toast('Error: ' + e.message, 'error'); }
  }
};
