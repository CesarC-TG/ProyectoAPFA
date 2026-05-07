/* ═══════════════════════════════════════════════════════════════════
   KAI Auth Module — Login, registro, logout, refresh, perfil
   ═══════════════════════════════════════════════════════════════════ */

const Auth = {
  _user: null,

  async init() {
    const token = localStorage.getItem('access_token');
    if (!token) return null;
    try {
      this._user = await API.get('/api/auth/me');
      return this._user;
    } catch {
      const rt = localStorage.getItem('refresh_token');
      if (rt) {
        try {
          const r = await API.post('/api/auth/refresh', { refresh_token: rt });
          localStorage.setItem('access_token', r.access_token);
          localStorage.setItem('refresh_token', r.refresh_token);
          this._user = r.usuario;
          return this._user;
        } catch { this._clear(); }
      }
      this._clear();
      return null;
    }
  },

  get user() { return this._user; },
  get isLoggedIn() { return !!this._user; },
  get isAdmin() { return this._user && this._user.rol === 'admin'; },
  get isPsicologo() { return this._user && this._user.rol === 'psicologo'; },
  get isEstudiante() { return this._user && this._user.rol === 'estudiante'; },

  _clear() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    this._user = null;
  },

  async login(email, password) {
    const r = await API.post('/api/auth/login', { email, password });
    localStorage.setItem('access_token', r.access_token);
    localStorage.setItem('refresh_token', r.refresh_token);
    this._user = r.usuario;
    return r;
  },

  async register(data) {
    const r = await API.post('/api/auth/registro', data);
    localStorage.setItem('access_token', r.access_token);
    localStorage.setItem('refresh_token', r.refresh_token);
    this._user = r.usuario;
    return r;
  },

  async loginGoogle(token) {
    const r = await API.post('/api/auth/google', { token });
    localStorage.setItem('access_token', r.access_token);
    localStorage.setItem('refresh_token', r.refresh_token);
    this._user = r.usuario;
    return r;
  },

  async logout() {
    try { await API.post('/api/auth/logout'); } catch {}
    this._clear();
  },

  async updateProfile(data) {
    this._user = await API.patch('/api/users/me', data);
    return this._user;
  },

  async uploadAvatar(file) {
    this._user = await API.upload('/api/users/me/avatar', file);
    return this._user;
  },

  requireAuth() {
    if (!this.isLoggedIn) {
      window.location.href = '/login.html';
      throw new Error('No autenticado');
    }
  },

  requireRole(roles) {
    this.requireAuth();
    if (!roles.includes(this._user.rol)) {
      App.toast('No tienes permisos para acceder aquí', 'error');
      if (this.isEstudiante) window.location.href = '/';
      else if (this.isPsicologo) window.location.href = '/psicologo.html';
      else if (this.isAdmin) window.location.href = '/admin.html';
      throw new Error('Rol no autorizado');
    }
  },

  redirectByRole() {
    if (!this.isLoggedIn) return;
    if (this.isAdmin) window.location.href = '/admin.html';
    else if (this.isPsicologo) window.location.href = '/psicologo.html';
  }
};
