/* ═══════════════════════════════════════════════════════════════════
   KAI Dashboard — Módulo principal del estudiante
   ═══════════════════════════════════════════════════════════════════ */

const Dashboard = {
  async init() {
    Auth.requireAuth();

    // User info in navbar
    const user = Auth.user;
    document.getElementById('user-name').textContent = user.nombre;
    document.getElementById('user-email').textContent = user.email;
    const avatar = document.getElementById('user-avatar');
    if (user.avatar_url) {
      avatar.innerHTML = `<img src="${user.avatar_url}" alt="${user.nombre}">`;
    } else {
      avatar.textContent = user.nombre.charAt(0).toUpperCase();
    }

    // Cargar stats rápidas
    this.loadStats();

    // Setup navegación
    App.setActiveNav('dashboard');
    document.querySelectorAll('.sidebar-link[data-page]').forEach(link => {
      link.onclick = (e) => {
        e.preventDefault();
        const page = link.dataset.page;
        this.navigate(page);
      };
    });

    // SOS FAB
    document.getElementById('sos-fab').onclick = () => SOS.showQuickSOS();
    document.getElementById('sos-mobile').onclick = () => SOS.showQuickSOS();

    // Logout
    document.getElementById('btn-logout').onclick = async () => {
      const ok = await App.confirm('¿Cerrar sesión?');
      if (ok) { await Auth.logout(); window.location.href = '/login.html'; }
    };

    // Mobile sidebar toggle
    document.getElementById('menu-toggle').onclick = () => {
      document.getElementById('sidebar').classList.toggle('open');
    };

    // Load initial view
    const hash = window.location.hash.slice(1);
    this.navigate(hash || 'dashboard');
  },

  navigate(page) {
    window.location.hash = page;
    App.setActiveNav(page);
    const content = document.getElementById('view-content');

    const views = {
      dashboard:  () => this.renderDashboard(),
      diario:     () => Diario.render(),
      recursos:   () => Recursos.render(),
      chatbot:    () => Chatbot.render(),
      citas:      () => Citas.render(),
      perfil:     () => Perfil.render(),
    };

    if (views[page]) views[page]();
  },

  async loadStats() {
    try {
      const stats = await API.get('/api/diario/');
      const notif = await API.get('/api/notificaciones/mis');

      document.getElementById('stat-diario').textContent = stats.total || 0;
      document.getElementById('stat-notif').textContent = notif.sin_leer || 0;

      // Últimas entradas
      if (stats.entradas && stats.entradas.length > 0) {
        const latest = document.getElementById('latest-entries');
        latest.innerHTML = stats.entradas.slice(0, 3).map(e => `
          <div style="display:flex;align-items:center;gap:0.75rem;padding:0.75rem 0;border-bottom:1px solid var(--color-border);min-width:0">
            <span style="font-size:1.25rem;flex-shrink:0">${e.estado_animo || '·'}</span>
            <div style="flex:1;min-width:0;overflow:hidden">
              <p style="font-size:var(--text-sm);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${App.escapeHtml(e.texto.substring(0, 80))}${e.texto.length > 80 ? '...' : ''}</p>
              <span class="text-xs text-muted">${App.timeAgo(e.creada_en)}</span>
            </div>
            ${e.alerta_crisis ? '<span class="badge badge-danger" style="flex-shrink:0">Crisis</span>' : ''}
          </div>`).join('');
      }
    } catch (e) {
      document.getElementById('stat-diario').textContent = '-';
      document.getElementById('stat-notif').textContent = '-';
    }
  },

  renderDashboard() {
    document.getElementById('view-content').innerHTML = `
      <div class="animate-fade-in">
        <h2 style="margin-bottom:0.25rem">Hola, ${Auth.user.nombre.split(' ')[0]}</h2>
        <p class="text-muted mb-4">¿Cómo te sientes hoy?</p>
        <div id="quick-mood" class="mood-grid mb-6">
          ${['😄','😊','😐','😔','😰','😤','😞'].map(m => `<button class="mood-btn" data-mood="${m}" onclick="Dashboard.quickMood('${m}')">${m}</button>`).join('')}
        </div>

        <div class="bento-grid-2" style="margin-top:1.5rem">
          <div class="bento-card">
            <div class="card-header">
              <span class="card-title" style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="book-open" style="width:1.25rem;height:1.25rem;color:var(--color-primary)"></i> Diario emocional</span>
            </div>
            <div id="latest-entries"><p class="text-muted text-sm">Cargando...</p></div>
            <button class="btn btn-outline w-full mt-4" onclick="Dashboard.navigate('diario')">Ir al diario</button>
          </div>
          <div class="bento-card">
            <div class="card-header">
              <span class="card-title" style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="message-circle" style="width:1.25rem;height:1.25rem;color:var(--color-secondary)"></i> Chat con KAI</span>
            </div>
            <p class="text-muted text-sm mb-4">Habla con KAI, tu compañero de apoyo emocional.</p>
            <button class="btn btn-primary w-full" onclick="Dashboard.navigate('chatbot')">Abrir chat</button>
          </div>
          <div class="bento-card">
            <div class="card-header">
              <span class="card-title" style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="heart" style="width:1.25rem;height:1.25rem;color:var(--color-accent)"></i> Recursos de bienestar</span>
            </div>
            <p class="text-muted text-sm mb-4">Ejercicios de respiración, meditación y más.</p>
            <button class="btn btn-outline w-full" onclick="Dashboard.navigate('recursos')">Explorar recursos</button>
          </div>
          <div class="bento-card">
            <div class="card-header">
              <span class="card-title" style="display:flex;align-items:center;gap:0.5rem"><i data-lucide="calendar" style="width:1.25rem;height:1.25rem;color:var(--color-success)"></i> Mis citas</span>
            </div>
            <div style="text-align:center;padding:2rem 0">
              <div class="stat-value" id="stat-diario">-</div>
              <div class="stat-label">Entradas escritas</div>
            </div>
            <button class="btn btn-outline w-full mt-4" onclick="Dashboard.navigate('citas')">Ver citas</button>
          </div>
        </div>
      </div>`;

    this.loadStats();
    setTimeout(() => lucide.createIcons(), 50);
  },

  async quickMood(mood) {
    try {
      await API.post('/api/diario/', {
        texto: `Me siento ${mood}`,
        estado_animo: mood,
      });
      App.toast('Estado de ánimo registrado ✓', 'success');
      this.loadStats();
    } catch (e) {
      App.toast('Error al guardar: ' + e.message, 'error');
    }
    document.querySelectorAll('.mood-btn').forEach(b => b.classList.remove('selected'));
  }
};
