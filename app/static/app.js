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
    // New chat button
    newChatBtn.addEventListener('click', () => resetToNewChat());

    // Delete chat button
    deleteChatBtn.addEventListener('click', async () => {
      if (!currentConversationId) return;
      if (confirm('Are you sure you want to delete this conversation?')) {
        await deleteCurrentConversation();
      }
    });

    // Chat form submit
    chatForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const content = messageInput.value.trim();
      if (!content) return;
      await handleSendMessage(content);
    });

    // Enter key submits (Shift+Enter for newline)
    messageInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event('submit'));
      }
    });

    // Auto resize textarea
    messageInput.addEventListener('input', () => {
      messageInput.style.height = 'auto';
      messageInput.style.height = `${Math.min(messageInput.scrollHeight, 150)}px`;
    });

    // Suggestion cards
    document.querySelectorAll('.suggestion-card').forEach((card) => {
      card.addEventListener('click', () => {
        const prompt = card.dataset.prompt;
        if (prompt) {
          messageInput.value = prompt;
          chatForm.dispatchEvent(new Event('submit'));
        }
      });
    });

    // Mobile menu toggle
    mobileToggleBtn.addEventListener('click', () => {
      sidebarEl.classList.toggle('open');
    });
  }

  async function checkSystemStatus() {
    try {
      const res = await fetch('/api/v1/system/status');
      if (!res.ok) return;
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
    }
  }

  async function loadConversations() {
    try {
      const res = await fetch('/api/v1/conversations');
      if (!res.ok) throw new Error('Failed to load conversations');
      const conversations = await res.json();
      renderConversationsList(conversations);
    } catch (err) {
      conversationsListEl.innerHTML = `<div class="conv-meta" style="padding:10px; color:var(--danger-color)">Error loading history</div>`;
    }
  }

  function renderConversationsList(conversations) {
    if (!conversations || conversations.length === 0) {
      conversationsListEl.innerHTML = `<div class="conv-meta" style="padding:10px; text-align:center;">No conversations yet</div>`;
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

    // Attach click handlers
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
        const iconClass = isUser ? 'fa-user' : 'fa-robot';
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

    if (!currentConversationId) {
      // 1. Create new conversation thread with initial message
      showTypingIndicator();
      welcomeScreenEl.style.display = 'none';
      messagesListEl.style.display = 'flex';
      messagesListEl.innerHTML = '';

      // Optimistically append user message
      appendSingleMessage({ role: 'user', content: content, timestamp: new Date().toISOString() });

      try {
        const res = await fetch('/api/v1/conversations', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ initial_message: content }),
        });

        if (!res.ok) throw new Error('Failed to start conversation');
        const detail = await res.json();

        currentConversationId = detail.id;
        activeChatTitleEl.textContent = detail.title;
        deleteChatBtn.style.display = 'inline-flex';

        renderMessages(detail.messages || []);
        await loadConversations();
      } catch (err) {
        alert('Error starting conversation: ' + err.message);
      } finally {
        hideTypingIndicator();
        scrollToBottom();
      }
    } else {
      // 2. Append message to existing conversation thread
      appendSingleMessage({ role: 'user', content: content, timestamp: new Date().toISOString() });
      showTypingIndicator();
      scrollToBottom();

      try {
        const res = await fetch(`/api/v1/conversations/${currentConversationId}/messages`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: content }),
        });

        if (!res.ok) {
          const errData = await res.json();
          throw new Error(errData.detail || 'Failed to send message');
        }

        const data = await res.json();
        hideTypingIndicator();
        appendSingleMessage(data.assistant_message);
        await loadConversations();
      } catch (err) {
        hideTypingIndicator();
        appendSingleMessage({
          role: 'assistant',
          content: `⚠️ Error generating response: ${err.message}`,
          timestamp: new Date().toISOString(),
        });
      } finally {
        scrollToBottom();
      }
    }
  }

  function appendSingleMessage(msg) {
    const isUser = msg.role === 'user';
    const avatarClass = isUser ? 'avatar-user' : 'avatar-assistant';
    const iconClass = isUser ? 'fa-user' : 'fa-robot';
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
    activeChatTitleEl.textContent = 'Select or start a conversation';
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
    
    // Format code blocks ```code```
    escaped = escaped.replace(/```([\s\S]*?)```/g, (match, code) => {
      return `<pre><code>${code.trim()}</code></pre>`;
    });

    // Format inline code `code`
    escaped = escaped.replace(/`([^`]+)`/g, '<code>$1</code>');

    return escaped;
  }
});
