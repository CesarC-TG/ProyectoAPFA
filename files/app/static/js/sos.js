/* ═══════════════════════════════════════════════════════════════════
   KAI SOS — Crisis y emergencias
   ═══════════════════════════════════════════════════════════════════ */

const SOS = {
  async showQuickSOS() {
    try {
      const lineas = await API.get('/api/sos/lineas');
      let linesHtml = lineas.map(l => `
        <div style="padding:var(--space-3);background:var(--color-surface);border-radius:var(--radius-md);margin-bottom:var(--space-2)">
          <strong>${l.icono} ${l.nombre}</strong><br>
          <a href="${l.telefono_href}" style="font-size:var(--text-lg);font-weight:700;color:var(--color-primary)">${l.telefono}</a>
          ${l.descripcion ? `<br><span class="text-xs text-muted">${l.descripcion}</span>` : ''}
          ${l.disponible_24h ? ' <span class="badge badge-success">24/7</span>' : ''}
        </div>`).join('');

      App.modal({
        title: 'Ayuda en crisis',
        size: 'large',
        body: `
          <div class="card mb-6" style="border-left:4px solid var(--color-danger);background:var(--color-danger-light)">
            <p style="font-weight:600;margin-bottom:0.5rem">No estás solo/a. Hay personas que quieren ayudarte.</p>
            <p class="text-sm">Si estás en crisis, llama a cualquiera de estas líneas:</p>
          </div>
          ${linesHtml}
          <button class="btn btn-sos w-full mt-6" onclick="SOS.registerEvent();document.querySelector('.modal-overlay').remove()">
            <i data-lucide="alert-triangle" style="width:1.25rem;height:1.25rem"></i> Registrar evento de emergencia
          </button>
        `,
        footer: '<button class="btn btn-ghost" onclick="this.closest(\'.modal-overlay\').remove()">Cerrar</button>'
      });
    } catch {
      App.toast('Error cargando líneas de crisis', 'error');
    }
  },

  async registerEvent() {
    try {
      await API.post('/api/sos/evento', {
        tipo_accion: 'chatbot',
        descripcion: 'Usuario activó el botón SOS',
      });
      App.toast('Alerta enviada. Un profesional te contactará pronto.', 'success');
    } catch (e) {
      App.toast('Error al registrar: ' + e.message, 'error');
    }
  }
};
