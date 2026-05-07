/* ═══════════════════════════════════════════════════════════════════
   KAI Chatbot — Conversación con IA de apoyo emocional
   ═══════════════════════════════════════════════════════════════════ */

const Chatbot = {
  _sessionId: null,
  _messages: [],

  async render() {
    document.getElementById('view-content').innerHTML = `
      <div class="animate-fade-in" style="height:calc(100vh - var(--navbar-height) - var(--space-8)*2)">
        <div class="chat-container">
          <div class="chat-messages" id="chat-msgs">
            <div class="chat-msg assistant">
              ¡Hola! Soy <strong>KAI</strong>, tu compañero de apoyo emocional. 💚<br>
              Puedes contarme cómo te sientes. Estoy aquí para escucharte sin juzgar.
            </div>
          </div>
          <div class="chat-input-bar">
            <input type="text" id="chat-input" class="input" placeholder="Escribe tu mensaje..."
                   onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();Chatbot.send()}">
            <button class="btn btn-primary" onclick="Chatbot.send()" id="chat-send-btn">Enviar</button>
          </div>
        </div>
      </div>`;

    document.getElementById('chat-input').focus();
  },

  async send() {
    const input = document.getElementById('chat-input');
    const btn = document.getElementById('chat-send-btn');
    const msg = input.value.trim();
    if (!msg) return;

    input.value = '';
    input.disabled = true;
    btn.disabled = true;

    this._addMessage('user', msg);

    // Show typing indicator
    const msgs = document.getElementById('chat-msgs');
    const typing = document.createElement('div');
    typing.className = 'chat-msg assistant';
    typing.innerHTML = '<div class="chat-typing"><span></span><span></span><span></span></div>';
    msgs.appendChild(typing);
    msgs.scrollTop = msgs.scrollHeight;

    try {
      const res = await API.post('/api/chatbot/mensaje', {
        contenido: msg,
        sesion_id: this._sessionId,
      });
      if (res.sesion_id) this._sessionId = res.sesion_id;
      typing.remove();
      this._addMessage('assistant', res.respuesta || 'Estoy aquí para ti. Cuéntame más.');
    } catch (e) {
      typing.remove();
      this._addMessage('assistant', 'Lo siento, estoy teniendo problemas para responder ahora. ¿Puedes intentarlo de nuevo? 💚');
    }

    input.disabled = false;
    btn.disabled = false;
    input.focus();
  },

  _addMessage(role, content) {
    const msgs = document.getElementById('chat-msgs');
    const div = document.createElement('div');
    div.className = `chat-msg ${role}`;
    div.textContent = content;
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
  }
};
