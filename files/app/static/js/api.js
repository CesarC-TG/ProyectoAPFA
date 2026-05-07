/* ═══════════════════════════════════════════════════════════════════
   KAI API Client — HTTP wrapper + token management
   ═══════════════════════════════════════════════════════════════════ */

const API = {
  BASE: '',

  _token() {
    return localStorage.getItem('access_token');
  },

  _headers(extra = {}) {
    const h = { 'Content-Type': 'application/json', ...extra };
    const t = this._token();
    if (t) h['Authorization'] = 'Bearer ' + t;
    return h;
  },

  async _request(method, path, body = null, opts = {}) {
    const url = this.BASE + path;
    const config = { method, headers: this._headers(opts.headers) };
    if (body && !opts.noJson) config.body = JSON.stringify(body);
    if (opts.noJson) config.body = body;

    const res = await fetch(url, config);
    if (res.status === 204) return null;

    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const err = new Error((data && data.detail) || `Error ${res.status}`);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  },

  get(path, opts)      { return this._request('GET', path, null, opts); },
  post(path, body, opts){ return this._request('POST', path, body, opts); },
  patch(path, body, opts){ return this._request('PATCH', path, body, opts); },
  put(path, body, opts) { return this._request('PUT', path, body, opts); },
  delete(path, opts)    { return this._request('DELETE', path, null, opts); },

  async upload(path, file, field = 'archivo') {
    const fd = new FormData();
    fd.append(field, file);
    return this._request('POST', path, fd, { noJson: true, headers: {} });
  }
};
