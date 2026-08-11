document.addEventListener('DOMContentLoaded', () => {
  // State
  let currentConversationId = null;

  // DOM Elements
  const conversationsListEl = document.getElementById('conversations-list');
  const messagesListEl = document.getElementById('messages-list');
  const messagesContainerEl = document.getElementById('messages-container');
  const welcomeScreenEl = document.getElementById('welcome-screen');
  const typingIndicatorEl = document.getElementById('typing-indicator');
  const chatForm = document.getElementById('chat-form');
  const messageInput = document.getElementById('message-input');
  const newChatBtn = document.getElementById('new-chat-btn');
  const deleteChatBtn = document.getElementById('delete-chat-btn');
  const activeChatTitleEl = document.getElementById('active-chat-title');
  const providerBadgeEl = document.getElementById('provider-badge');
  const providerTextEl = document.getElementById('provider-text');
  const mobileToggleBtn = document.getElementById('mobile-toggle');
  const sidebarEl = document.getElementById('sidebar');

  // Initialize
  initApp();

  async function initApp() {
    setupEventListeners();
    await checkSystemStatus();
    await loadConversations();
  }

  function setupEventListeners() {
    newChatBtn.addEventListener('click', () => resetToNewChat());

    deleteChatBtn.addEventListener('click', async () => {
      if (!currentConversationId) return;
      if (confirm('Are you sure you want to delete this conversation?')) {
        await deleteCurrentConversation();
      }
    });

    chatForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const content = messageInput.value.trim();
      if (!content) return;
      await handleSendMessage(content);
    });

    messageInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event('submit'));
      }
    });

    messageInput.addEventListener('input', () => {
      messageInput.style.height = 'auto';
      messageInput.style.height = `${Math.min(messageInput.scrollHeight, 140)}px`;
    });

    document.querySelectorAll('.suggestion-card').forEach((card) => {
      card.addEventListener('click', () => {
        const prompt = card.dataset.prompt;
        if (prompt) {
          messageInput.value = prompt;
          chatForm.dispatchEvent(new Event('submit'));
        }
      });
    });

    mobileToggleBtn.addEventListener('click', () => {
      sidebarEl.classList.toggle('open');
    });
  }

  async function checkSystemStatus() {
    try {
      const res = await fetch('/api/v1/system/status');
      if (!res.ok) throw new Error('Status failed');
      const data = await res.json();

      const dot = providerBadgeEl.querySelector('.status-dot');
      if (data.has_api_key) {
        dot.classList.remove('mock');
        providerTextEl.textContent = `OpenRouter (${data.model_configured.split('/')[1] || data.model_configured})`;
      } else {
        dot.classList.add('mock');
        providerTextEl.textContent = 'Mock Mode (No API Key)';
      }
    } catch (err) {
      console.warn('Could not check system status:', err);
      providerTextEl.textContent = 'Engine Offline';
    }
  }

  async function loadConversations() {
    try {
      const res = await fetch('/api/v1/conversations');
      if (!res.ok) throw new Error('Failed to load conversations');
      const conversations = await res.json();
      renderConversationsList(conversations);
    } catch (err) {
      conversationsListEl.innerHTML = `<div class="conv-meta" style="padding:10px; text-align:center; color:var(--text-muted)">No saved conversations</div>`;
    }
  }

  function renderConversationsList(conversations) {
    if (!conversations || conversations.length === 0) {
      conversationsListEl.innerHTML = `<div class="conv-meta" style="padding:10px; text-align:center; color:var(--text-muted)">No conversations yet</div>`;
      return;
    }

    conversationsListEl.innerHTML = conversations
      .map((conv) => {
        const isActive = conv.id === currentConversationId ? 'active' : '';
        const timeAgo = formatTime(conv.updated_at);
        return `
          <div class="conv-item ${isActive}" data-id="${conv.id}">
            <div class="conv-info">
              <span class="conv-title">${escapeHtml(conv.title)}</span>
              <span class="conv-meta">${conv.message_count || 0} msgs • ${timeAgo}</span>
            </div>
          </div>
        `;
      })
      .join('');

    conversationsListEl.querySelectorAll('.conv-item').forEach((item) => {
      item.addEventListener('click', () => {
        const id = item.dataset.id;
        if (id !== currentConversationId) {
          selectConversation(id);
          sidebarEl.classList.remove('open');
        }
      });
    });
  }

  async function selectConversation(convId) {
    currentConversationId = convId;
    deleteChatBtn.style.display = 'inline-flex';

    try {
      const res = await fetch(`/api/v1/conversations/${convId}`);
      if (!res.ok) throw new Error('Failed to load conversation details');
      const detail = await res.json();

      activeChatTitleEl.textContent = detail.title;
      welcomeScreenEl.style.display = 'none';
      messagesListEl.style.display = 'flex';

      renderMessages(detail.messages || []);
      scrollToBottom();
      await loadConversations();
    } catch (err) {
      console.error(err);
      alert('Could not open conversation');
    }
  }

  function renderMessages(messages) {
    messagesListEl.innerHTML = messages
      .map((msg) => {
        const isUser = msg.role === 'user';
        const avatarClass = isUser ? 'avatar-user' : 'avatar-assistant';
        const iconClass = isUser ? 'fa-user' : 'fa-cube';
        const rowClass = isUser ? 'user' : 'assistant';
        const formattedTime = new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        return `
          <div class="message-row ${rowClass}">
            ${!isUser ? `<div class="avatar ${avatarClass}"><i class="fa-solid ${iconClass}"></i></div>` : ''}
            <div class="message-wrapper">
              <div class="message-bubble">${formatMessageContent(msg.content)}</div>
              <div class="message-time">${formattedTime}</div>
            </div>
            ${isUser ? `<div class="avatar ${avatarClass}"><i class="fa-solid ${iconClass}"></i></div>` : ''}
          </div>
        `;
      })
      .join('');
  }

  async function handleSendMessage(content) {
    messageInput.value = '';
    messageInput.style.height = 'auto';

    welcomeScreenEl.style.display = 'none';
    messagesListEl.style.display = 'flex';

    // 1. Create conversation first if not active
    if (!currentConversationId) {
      try {
        const res = await fetch('/api/v1/conversations', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: 'New Conversation' }),
        });

        if (!res.ok) throw new Error('Failed to create conversation thread');
        const detail = await res.json();

        currentConversationId = detail.id;
        activeChatTitleEl.textContent = detail.title;
        deleteChatBtn.style.display = 'inline-flex';
        await loadConversations();
      } catch (err) {
        alert('Error initializing chat thread: ' + err.message);
        return;
      }
    }

    // 2. Append User Message to UI
    appendSingleMessage({ role: 'user', content: content, timestamp: new Date().toISOString() });

    // 3. Create placeholder for Assistant Response
    const asstBubbleId = `asst-bubble-${Date.now()}`;
    const asstMsgHtml = `
      <div class="message-row assistant">
        <div class="avatar avatar-assistant"><i class="fa-solid fa-cube"></i></div>
        <div class="message-wrapper">
          <div class="message-bubble" id="${asstBubbleId}"></div>
          <div class="message-time">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
        </div>
      </div>
    `;
    messagesListEl.insertAdjacentHTML('beforeend', asstMsgHtml);
    const asstBubbleEl = document.getElementById(asstBubbleId);

    showTypingIndicator();
    scrollToBottom();

    // 4. Stream response via SSE
    let accumulatedText = '';
    try {
      const response = await fetch(`/api/v1/conversations/${currentConversationId}/messages/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: content }),
      });

      if (!response.ok) {
        throw new Error(`Streaming failed with status ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop(); // Keep incomplete line chunk in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.replace('data: ', ''));
              if (data.error) {
                accumulatedText += `\n⚠️ Error: ${data.error}`;
                asstBubbleEl.innerHTML = formatMessageContent(accumulatedText);
                break;
              }

              if (data.content) {
                hideTypingIndicator();
                accumulatedText += data.content;
                asstBubbleEl.innerHTML = formatMessageContent(accumulatedText);
                scrollToBottom();
              }

              if (data.done) {
                hideTypingIndicator();
                if (data.title) {
                  activeChatTitleEl.textContent = data.title;
                }
                await loadConversations();
              }
            } catch (e) {
              console.warn('Failed to parse SSE payload:', e);
            }
          }
        }
      }
    } catch (err) {
      hideTypingIndicator();
      asstBubbleEl.innerHTML = formatMessageContent(`⚠️ Connection error: ${err.message}`);
    } finally {
      hideTypingIndicator();
      scrollToBottom();
    }
  }

  function appendSingleMessage(msg) {
    const isUser = msg.role === 'user';
    const avatarClass = isUser ? 'avatar-user' : 'avatar-assistant';
    const iconClass = isUser ? 'fa-user' : 'fa-cube';
    const rowClass = isUser ? 'user' : 'assistant';
    const formattedTime = new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const msgHtml = `
      <div class="message-row ${rowClass}">
        ${!isUser ? `<div class="avatar ${avatarClass}"><i class="fa-solid ${iconClass}"></i></div>` : ''}
        <div class="message-wrapper">
          <div class="message-bubble">${formatMessageContent(msg.content)}</div>
          <div class="message-time">${formattedTime}</div>
        </div>
        ${isUser ? `<div class="avatar ${avatarClass}"><i class="fa-solid ${iconClass}"></i></div>` : ''}
      </div>
    `;

    messagesListEl.insertAdjacentHTML('beforeend', msgHtml);
  }

  async function deleteCurrentConversation() {
    if (!currentConversationId) return;
    try {
      const res = await fetch(`/api/v1/conversations/${currentConversationId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete');
      resetToNewChat();
      await loadConversations();
    } catch (err) {
      alert('Could not delete conversation');
    }
  }

  function resetToNewChat() {
    currentConversationId = null;
    activeChatTitleEl.textContent = 'New Conversation';
    deleteChatBtn.style.display = 'none';
    messagesListEl.style.display = 'none';
    messagesListEl.innerHTML = '';
    welcomeScreenEl.style.display = 'flex';
    messageInput.value = '';
    loadConversations();
  }

  function showTypingIndicator() {
    typingIndicatorEl.style.display = 'flex';
    scrollToBottom();
  }

  function hideTypingIndicator() {
    typingIndicatorEl.style.display = 'none';
  }

  function scrollToBottom() {
    messagesContainerEl.scrollTop = messagesContainerEl.scrollHeight;
  }

  function formatTime(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  }

  function escapeHtml(str) {
    return (str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function formatMessageContent(content) {
    if (!content) return '';
    let escaped = escapeHtml(content);

    const codeBlocks = [];
    escaped = escaped.replace(/```([\s\S]*?)```/g, (match, code) => {
      codeBlocks.push(code);
      return `@@CODE_BLOCK_${codeBlocks.length - 1}@@`;
    });

    const inlineCodes = [];
    escaped = escaped.replace(/`([^`\n]+)`/g, (match, code) => {
      inlineCodes.push(code);
      return `@@INLINE_CODE_${inlineCodes.length - 1}@@`;
    });

    escaped = escaped.replace(/^(?:---|\*\*\*|___)\s*$/gm, '<hr>');
    escaped = escaped.replace(/^######\s+(.+)$/gm, '<h6>$1</h6>');
    escaped = escaped.replace(/^#####\s+(.+)$/gm, '<h5>$1</h5>');
    escaped = escaped.replace(/^####\s+(.+)$/gm, '<h4>$1</h4>');
    escaped = escaped.replace(/^###\s+(.+)$/gm, '<h3>$1</h3>');
    escaped = escaped.replace(/^##\s+(.+)$/gm, '<h2>$1</h2>');
    escaped = escaped.replace(/^#\s+(.+)$/gm, '<h1>$1</h1>');
    escaped = escaped.replace(/^> ?(.+)$/gm, '<blockquote>$1</blockquote>');

    escaped = escaped.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    escaped = escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    escaped = escaped.replace(/\*(.+?)\*/g, '<em>$1</em>');

    escaped = escaped.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

    escaped = escaped.replace(/^(\|?.+\|.*)\r?\n\|?\s*[:\-]+[:\s]*\|(?:\s*[:\-]+[:\s]*\|?)+\s*\r?\n(?:\|?.+\|.*(?:\r?\n|$))+/gm, (match) => {
      const lines = match.trim().split(/\r?\n/);
      if (lines.length < 2) return match;

      const parseRow = (line) => line.trim().replace(/^\||\|$/g, '').split('|').map((cell) => cell.trim());
      const headerCells = parseRow(lines[0]);
      const bodyRows = lines.slice(2).map(parseRow).filter((row) => row.some((cell) => cell !== ''));

      const thead = `<thead><tr>${headerCells.map((cell) => `<th>${cell}</th>`).join('')}</tr></thead>`;
      const tbody = bodyRows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join('')}</tr>`).join('');
      return `<div class="md-table-wrapper"><table>${thead}<tbody>${tbody}</tbody></table></div>`;
    });

    escaped = escaped.replace(/^(?:[-*+] .+(?:\n[-*+] .+)*)/gm, (match) => {
      const items = match.trim().split('\n').map((line) => `<li>${line.replace(/^[-*+] /, '')}</li>`);
      return `<ul>${items.join('')}</ul>`;
    });

    escaped = escaped.replace(/^(?:\d+\. .+(?:\n\d+\. .+)*)/gm, (match) => {
      const items = match.trim().split('\n').map((line) => `<li>${line.replace(/^\d+\. /, '')}</li>`);
      return `<ol>${items.join('')}</ol>`;
    });

    escaped = escaped.replace(/\n{2,}/g, '<br><br>');
    escaped = escaped.replace(/\n/g, '<br>');

    escaped = escaped.replace(/@@INLINE_CODE_(\d+)@@/g, (_, idx) => `<code>${inlineCodes[idx]}</code>`);
    escaped = escaped.replace(/@@CODE_BLOCK_(\d+)@@/g, (_, idx) => `<pre><code>${codeBlocks[idx].trim()}</code></pre>`);

    return escaped;
  }
});
