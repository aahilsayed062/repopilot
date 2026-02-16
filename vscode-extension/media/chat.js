/**
 * RepoPilot VS Code Extension – Copilot/Antigravity Chat UI
 * Handles: messages, history, settings, Round 2 panels
 */
(function () {
    // @ts-ignore
    const vscode = acquireVsCodeApi();

    // ── Elements ──────────────────────────────────────────────
    const statusIndicator = document.getElementById('status-indicator');
    const statusLabel = document.getElementById('status-label');
    const messagesContainer = document.getElementById('messages-container');
    const welcomeScreen = document.getElementById('welcome-screen');
    const inputEl = document.getElementById('input');
    const sendBtn = document.getElementById('btn-send');
    const historyPanel = document.getElementById('history-panel');
    const historyList = document.getElementById('history-list');
    const settingsMenu = document.getElementById('settings-menu');

    // Buttons
    const newChatBtn = document.getElementById('btn-new-chat');
    const historyBtn = document.getElementById('btn-history');
    const settingsBtn = document.getElementById('btn-settings');
    const indexBtn = document.getElementById('btn-index');
    const generateBtn = document.getElementById('btn-generate');
    const testsBtn = document.getElementById('btn-tests');
    const exportBtn = document.getElementById('btn-export');
    const clearBtn = document.getElementById('btn-clear');
    const cancelBtn = document.getElementById('btn-cancel');

    // Welcome actions
    const welcomeIndex = document.getElementById('welcome-index');
    const welcomeAsk = document.getElementById('welcome-ask');
    const welcomeGenerate = document.getElementById('welcome-generate');

    // ── State ─────────────────────────────────────────────────
    let isLoading = false;
    let currentStatus = 'not_connected';
    let hasMessages = false;
    let chatSessions = [];
    let currentSessionId = Date.now();

    // @ mention state
    let workspaceFiles = [];
    let mentionActive = false;
    let mentionQuery = '';
    let mentionStartPos = -1;
    let mentionSelectedIdx = 0;
    let mentionedFiles = []; // files mentioned in current message

    const statusLabels = {
        'not_connected': 'Disconnected',
        'not_indexed': 'Not Indexed',
        'loading': 'Loading…',
        'indexing': 'Indexing…',
        'ready': 'Ready',
        'error': 'Error'
    };

    // ── Status ────────────────────────────────────────────────
    function updateStatus(status, repoName) {
        currentStatus = status;
        statusIndicator.className = 'status-indicator';
        if (status === 'ready') statusIndicator.classList.add('connected');
        else if (status === 'loading' || status === 'indexing') statusIndicator.classList.add('loading');
        else if (status === 'error') statusIndicator.classList.add('error');
        else statusIndicator.classList.add('disconnected');

        let label = statusLabels[status] || status;
        if (status === 'ready' && repoName) label = repoName;
        statusLabel.textContent = label;

        setInputState(status === 'ready', isLoading);
    }

    function setInputState(isReady, loading) {
        // Input and send are always enabled unless loading
        inputEl.disabled = !!loading;
        sendBtn.disabled = !!loading;

        // Index button is ALWAYS clickable
        if (indexBtn) {
            indexBtn.style.opacity = '1';
            indexBtn.style.pointerEvents = 'auto';
        }

        // Generate and Tests only active when ready and not loading
        var genTestEnabled = isReady && !loading;
        [generateBtn, testsBtn].forEach(function (btn) {
            if (btn) {
                btn.style.opacity = genTestEnabled ? '1' : '0.5';
                btn.style.pointerEvents = genTestEnabled ? 'auto' : 'none';
            }
        });
    }

    // ── Loading ───────────────────────────────────────────────
    function setLoading(loading) {
        isLoading = loading;
        setInputState(currentStatus === 'ready', loading);

        // Toggle send/cancel button visibility
        if (sendBtn && cancelBtn) {
            sendBtn.style.display = loading ? 'none' : '';
            cancelBtn.style.display = loading ? 'flex' : 'none';
        }

        if (loading) {
            showChat();
            addThinking();
            scrollToBottom();
        } else {
            removeThinking();
        }
    }

    function addThinking() {
        removeThinking();
        const el = document.createElement('div');
        el.id = 'thinking-indicator';
        el.className = 'thinking-indicator';
        el.innerHTML = '<div class="thinking-dots"><span></span><span></span><span></span></div><span>RepoPilot is thinking…</span>';
        messagesContainer.appendChild(el);
    }

    function removeThinking() {
        const el = document.getElementById('thinking-indicator');
        if (el) el.remove();
    }

    // ── Welcome / Chat toggle ─────────────────────────────────
    function showChat() {
        if (!hasMessages) {
            hasMessages = true;
            welcomeScreen.classList.add('hidden');
            messagesContainer.classList.remove('hidden');
        }
    }

    function showWelcome() {
        hasMessages = false;
        welcomeScreen.classList.remove('hidden');
        messagesContainer.classList.add('hidden');
        messagesContainer.innerHTML = '';
    }

    // ── SVG helpers ───────────────────────────────────────────
    const SVG = {
        copilot: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2L2 7l10 5 10-5-10-5zm0 15l-5-2.5V10L12 12.5 17 10v4.5L12 17z"/></svg>',
        chevron: '<svg viewBox="0 0 16 16" fill="currentColor"><path d="M5.7 13.7l5-5a1 1 0 000-1.4l-5-5a1 1 0 00-1.4 1.4L8.58 8l-4.3 4.3a1 1 0 001.42 1.4z"/></svg>',
        file: '<svg viewBox="0 0 16 16" fill="currentColor"><path d="M3.5 1A1.5 1.5 0 002 2.5v11A1.5 1.5 0 003.5 15h9a1.5 1.5 0 001.5-1.5V5.621a1.5 1.5 0 00-.44-1.06l-3.12-3.122A1.5 1.5 0 009.378 1H3.5zM3 2.5a.5.5 0 01.5-.5h5.878a.5.5 0 01.354.146l3.122 3.122a.5.5 0 01.146.354V13.5a.5.5 0 01-.5.5h-9a.5.5 0 01-.5-.5v-11z"/></svg>',
        copy: '<svg viewBox="0 0 16 16" fill="currentColor"><path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 010 1.5h-1.5a.25.25 0 00-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 00.25-.25v-1.5a.75.75 0 011.5 0v1.5A1.75 1.75 0 019.25 16h-7.5A1.75 1.75 0 010 14.25v-7.5z"/><path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0114.25 11h-7.5A1.75 1.75 0 015 9.25v-7.5zm1.75-.25a.25.25 0 00-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 00.25-.25v-7.5a.25.25 0 00-.25-.25h-7.5z"/></svg>'
    };

    // ── Add Message ───────────────────────────────────────────
    function addMessage(role, content, citations, buttons) {
        // Only remove thinking if this is a real message (not empty streaming placeholder)
        if (content && content.trim()) {
            removeThinking();
        }
        showChat();

        const msgDiv = document.createElement('div');
        msgDiv.className = 'message ' + role;

        if (role === 'user') {
            msgDiv.innerHTML =
                '<div class="msg-avatar">U</div>' +
                '<div class="msg-content">' + parseMarkdown(content) + '</div>';
        } else if (role === 'assistant') {
            let html = '<div class="msg-header">' +
                '<div class="msg-avatar">' + SVG.copilot + '</div>' +
                '<span class="msg-name">RepoPilot</span></div>' +
                '<div class="msg-content">' + parseMarkdown(content);

            // Citations
            if (citations && citations.length > 0) {
                html += '<div class="citations">';
                citations.forEach(function (cit) {
                    const label = cit.file_path + (cit.line_range ? ':' + cit.line_range : '');
                    html += '<span class="citation-chip" data-path="' + escapeAttr(cit.file_path) +
                        '" data-range="' + escapeAttr(cit.line_range || '') + '">' +
                        SVG.file + ' ' + escapeHtml(label) + '</span>';
                });
                html += '</div>';
            }

            // Action buttons
            if (buttons && buttons.length > 0) {
                html += '<div class="msg-actions">';
                buttons.forEach(function (btn) {
                    html += '<button class="msg-action-btn" data-action="' + btn.action + '">' +
                        escapeHtml(btn.label) + '</button>';
                });
                html += '</div>';
            }

            html += '</div>';
            msgDiv.innerHTML = html;

            // Post-process: inject per-file Accept/Reject buttons after each file's diff
            injectPerFileButtons(msgDiv);

            // Bind citation clicks
            msgDiv.querySelectorAll('.citation-chip').forEach(function (chip) {
                chip.addEventListener('click', function () {
                    const filePath = chip.getAttribute('data-path');
                    const range = chip.getAttribute('data-range');
                    let startLine, endLine;
                    if (range) {
                        const match = range.match(/(\d+)(?:-(\d+))?/);
                        if (match) {
                            startLine = parseInt(match[1]);
                            endLine = match[2] ? parseInt(match[2]) : startLine;
                        }
                    }
                    vscode.postMessage({ type: 'OPEN_CITATION', file_path: filePath, start_line: startLine, end_line: endLine });
                });
            });

            // Bind action buttons (Accept All, Run Tests, etc.)
            msgDiv.querySelectorAll('.msg-action-btn').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    vscode.postMessage({ type: btn.getAttribute('data-action') });
                });
            });

            // Bind per-file accept/reject buttons
            msgDiv.querySelectorAll('.file-accept-btn').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var filePath = btn.getAttribute('data-file');
                    vscode.postMessage({ type: 'ACCEPT_FILE', file_path: filePath });
                    btn.closest('.file-action-bar').style.opacity = '0.4';
                    btn.closest('.file-action-bar').innerHTML = '<span style="color:var(--success,#48bb78);font-size:11px">✅ Applied</span>';
                });
            });
            msgDiv.querySelectorAll('.file-reject-btn').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    var filePath = btn.getAttribute('data-file');
                    vscode.postMessage({ type: 'REJECT_FILE', file_path: filePath });
                    btn.closest('.file-action-bar').style.opacity = '0.4';
                    btn.closest('.file-action-bar').innerHTML = '<span style="color:var(--error,#e53e3e);font-size:11px">❌ Skipped</span>';
                });
            });

            // Bind copy buttons
            msgDiv.querySelectorAll('.copy-btn').forEach(function (btn) {
                btn.addEventListener('click', function () {
                    const codeEl = btn.closest('.code-block').querySelector('.code-content code');
                    if (codeEl) {
                        navigator.clipboard.writeText(codeEl.textContent).then(function () {
                            const orig = btn.innerHTML;
                            btn.innerHTML = '✓ Copied';
                            setTimeout(function () { btn.innerHTML = orig; }, 1500);
                        });
                    }
                });
            });

        } else if (role === 'system') {
            msgDiv.innerHTML = '<div class="msg-content">' + parseMarkdown(content) + '</div>';
        }

        messagesContainer.appendChild(msgDiv);
        scrollToBottom();
        saveCurrentSession();
    }

    function updateLastMessage(content, citations) {
        const lastMsg = messagesContainer.lastElementChild;
        if (!lastMsg || !lastMsg.classList.contains('assistant')) {
            addMessage('assistant', content, citations);
            return;
        }

        const contentDiv = lastMsg.querySelector('.msg-content');
        if (contentDiv) {
            // Preserve header
            const header = lastMsg.querySelector('.msg-header');
            let html = '';
            if (header) html += header.outerHTML;

            html += '<div class="msg-content">' + parseMarkdown(content) + '</div>';

            // Re-add citations/buttons if they existed or are new?
            // Simplified: rebuild content div + citations
            contentDiv.innerHTML = parseMarkdown(content);
        }

        scrollToBottom();
        saveCurrentSession();
    }

    // ── Markdown Parser ───────────────────────────────────────
    function parseMarkdown(text) {
        if (!text) return '';
        var html = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Code blocks
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function (_, lang, code) {
            return '<div class="code-block">' +
                '<div class="code-header"><span>' + (lang || 'text') + '</span>' +
                '<button class="copy-btn">' + SVG.copy + ' Copy</button></div>' +
                '<pre class="code-content"><code>' + code.trim() + '</code></pre></div>';
        });

        // Inline code
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
        // Bold
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        // Italic
        html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
        // Stats +N -M
        html = html.replace(/`(\+\d+ -\d+)`/g, '<span class="diff-stats">$1</span>');
        // Headers → bold + margin
        html = html.replace(/^### (.+)$/gm, '<strong style="display:block;margin:8px 0 4px">$1</strong>');
        html = html.replace(/^#### (.+)$/gm, '<strong class="file-header" style="display:block;font-size:13px;margin:12px 0 4px">$1</strong>');
        // Unordered lists
        html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
        html = html.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>');
        // Remove consecutive ul tags
        html = html.replace(/<\/ul>\s*<ul>/g, '');
        // Lines
        html = html.replace(/\n/g, '<br>');

        return html;
    }

    function injectPerFileButtons(container) {
        // Find all file headers
        const headers = container.querySelectorAll('.file-header');
        headers.forEach(header => {
            // Find the file name
            const text = header.textContent;
            const match = text.match(/📁\s+([^\s]+)/);
            if (!match) return;
            const filePath = match[1];

            // Find the next code block
            let next = header.nextElementSibling;
            while (next && !next.classList.contains('code-block')) {
                next = next.nextElementSibling;
            }

            if (next && next.classList.contains('code-block')) {
                // Create action bar
                const bar = document.createElement('div');
                bar.className = 'file-action-bar';
                bar.innerHTML = `
                    <button class="file-accept-btn" data-file="${escapeAttr(filePath)}">✅ Accept</button>
                    <button class="file-reject-btn" data-file="${escapeAttr(filePath)}">❌ Reject</button>
                `;
                // Insert after code block
                next.parentNode.insertBefore(bar, next.nextSibling);
            }
        });
    }

    // ── Helpers ───────────────────────────────────────────────
    function escapeHtml(str) {
        return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function escapeAttr(str) {
        return (str || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function scrollToBottom() {
        var area = document.querySelector('.chat-area');
        if (area) area.scrollTop = area.scrollHeight;
    }

    // ── Chat History ──────────────────────────────────────────
    function saveCurrentSession() {
        var msgs = messagesContainer.innerHTML;
        if (!msgs.trim()) return;
        // Find existing session
        var found = false;
        for (var i = 0; i < chatSessions.length; i++) {
            if (chatSessions[i].id === currentSessionId) {
                chatSessions[i].html = msgs;
                chatSessions[i].preview = getSessionPreview();
                chatSessions[i].time = Date.now();
                found = true;
                break;
            }
        }
        if (!found && hasMessages) {
            chatSessions.unshift({
                id: currentSessionId,
                html: msgs,
                preview: getSessionPreview(),
                time: Date.now()
            });
        }
        // Keep max 20 sessions
        if (chatSessions.length > 20) chatSessions.length = 20;
        try {
            vscode.setState({ chatSessions: chatSessions, currentSessionId: currentSessionId });
        } catch (e) { /* ignore */ }
    }

    function getSessionPreview() {
        var firstUser = messagesContainer.querySelector('.message.user .msg-content');
        return firstUser ? firstUser.textContent.substring(0, 60) : 'Chat session';
    }

    function loadState() {
        try {
            var state = vscode.getState();
            if (state && state.chatSessions) {
                chatSessions = state.chatSessions;
                currentSessionId = state.currentSessionId || Date.now();
            }
        } catch (e) { /* ignore */ }
    }

    function renderHistory() {
        if (!historyList) return;
        historyList.innerHTML = '';
        if (chatSessions.length === 0) {
            historyList.innerHTML = '<div class="history-empty">No recent chats</div>';
            return;
        }
        chatSessions.forEach(function (session) {
            var item = document.createElement('div');
            item.className = 'history-item' + (session.id === currentSessionId ? ' active' : '');
            var timeAgo = getTimeAgo(session.time);
            item.innerHTML =
                '<svg viewBox="0 0 16 16" fill="currentColor"><path d="M1.5 1.75V13.5h13.25a.75.75 0 010 1.5H.75a.75.75 0 01-.75-.75V1.75a.75.75 0 011.5 0zm14.28 2.53l-5 5a.75.75 0 01-1.06 0L7 6.56 3.28 10.28a.75.75 0 01-1.06-1.06l4.25-4.25a.75.75 0 011.06 0L10.25 7.69l4.47-4.47a.75.75 0 111.06 1.06z"/></svg>' +
                '<span class="history-item-text">' + escapeHtml(session.preview) + '</span>' +
                '<span class="history-item-time">' + timeAgo + '</span>';
            item.addEventListener('click', function () {
                loadSession(session.id);
                toggleHistory(false);
            });
            historyList.appendChild(item);
        });
    }

    function loadSession(sessionId) {
        for (var i = 0; i < chatSessions.length; i++) {
            if (chatSessions[i].id === sessionId) {
                currentSessionId = sessionId;
                messagesContainer.innerHTML = chatSessions[i].html;
                showChat();
                // Re-bind event listeners
                rebindMessageListeners();
                scrollToBottom();
                break;
            }
        }
    }

    function rebindMessageListeners() {
        messagesContainer.querySelectorAll('.citation-chip').forEach(function (chip) {
            chip.addEventListener('click', function () {
                var filePath = chip.getAttribute('data-path');
                var range = chip.getAttribute('data-range');
                var startLine, endLine;
                if (range) {
                    var match = range.match(/(\d+)(?:-(\d+))?/);
                    if (match) {
                        startLine = parseInt(match[1]);
                        endLine = match[2] ? parseInt(match[2]) : startLine;
                    }
                }
                vscode.postMessage({ type: 'OPEN_CITATION', file_path: filePath, start_line: startLine, end_line: endLine });
            });
        });
        messagesContainer.querySelectorAll('.msg-action-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                vscode.postMessage({ type: btn.getAttribute('data-action') });
            });
        });
        messagesContainer.querySelectorAll('.copy-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var codeEl = btn.closest('.code-block').querySelector('.code-content code');
                if (codeEl) {
                    navigator.clipboard.writeText(codeEl.textContent).then(function () {
                        var orig = btn.innerHTML;
                        btn.innerHTML = '✓ Copied';
                        setTimeout(function () { btn.innerHTML = orig; }, 1500);
                    });
                }
            });
        });
    }

    function getTimeAgo(ts) {
        var diff = Date.now() - ts;
        var mins = Math.floor(diff / 60000);
        if (mins < 1) return 'now';
        if (mins < 60) return mins + 'm';
        var hours = Math.floor(mins / 60);
        if (hours < 24) return hours + 'h';
        var days = Math.floor(hours / 24);
        return days + 'd';
    }

    // ── Toggles ───────────────────────────────────────────────
    function toggleHistory(forceState) {
        var isOpen = typeof forceState === 'boolean' ? forceState : !historyPanel.classList.contains('open');
        if (isOpen) {
            renderHistory();
            historyPanel.classList.add('open');
            settingsMenu.classList.remove('open');
        } else {
            historyPanel.classList.remove('open');
        }
    }

    function toggleSettings(forceState) {
        var isOpen = typeof forceState === 'boolean' ? forceState : !settingsMenu.classList.contains('open');
        if (isOpen) {
            settingsMenu.classList.add('open');
            historyPanel.classList.remove('open');
        } else {
            settingsMenu.classList.remove('open');
        }
    }

    // ── Input Handling ────────────────────────────────────────
    function handleSend() {
        var text = inputEl.value.trim();
        if (!text) return;

        // Collect @mentioned file names
        var fileMentions = [];
        var mentionPattern = /@([\w.\-\/\\]+)/g;
        var match;
        while ((match = mentionPattern.exec(text)) !== null) {
            fileMentions.push(match[1]);
        }

        // If files are mentioned, request their content from extension
        if (fileMentions.length > 0) {
            vscode.postMessage({ type: 'REQUEST_FILE_CONTEXT', files: fileMentions });
        }

        if (text.startsWith('/generate ')) {
            addMessage('user', text);
            vscode.postMessage({ type: 'GENERATE', request: text.substring(10) });
        } else if (text.startsWith('/refine ')) {
            addMessage('user', text);
            vscode.postMessage({ type: 'REFINE', request: text.substring(8) });
        } else {
            addMessage('user', text);
            vscode.postMessage({ type: 'ASK', question: text });
        }
        inputEl.value = '';
        mentionedFiles = [];
        autoResizeInput();
        closeMentionDropdown();
    }

    function autoResizeInput() {
        inputEl.style.height = 'auto';
        inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
    }

    // ── @ Mention Autocomplete ────────────────────────────────
    var mentionDropdown = document.createElement('div');
    mentionDropdown.className = 'mention-dropdown';
    mentionDropdown.id = 'mention-dropdown';
    document.querySelector('.input-area').appendChild(mentionDropdown);

    function openMentionDropdown(query) {
        mentionActive = true;
        mentionQuery = query;
        mentionSelectedIdx = 0;
        var filtered = filterFiles(query);
        if (filtered.length === 0) {
            closeMentionDropdown();
            return;
        }
        mentionDropdown.innerHTML = '';
        filtered.slice(0, 12).forEach(function (file, idx) {
            var item = document.createElement('div');
            item.className = 'mention-item' + (idx === 0 ? ' selected' : '');
            var icon = getFileIcon(file);
            item.innerHTML = '<span class="mention-icon">' + icon + '</span>' +
                '<span class="mention-path">' + escapeHtml(file) + '</span>';
            item.addEventListener('mousedown', function (e) {
                e.preventDefault();
                insertMention(file);
            });
            item.addEventListener('mouseenter', function () {
                mentionSelectedIdx = idx;
                highlightMentionItem(idx);
            });
            mentionDropdown.appendChild(item);
        });
        mentionDropdown.classList.add('open');
    }

    function closeMentionDropdown() {
        mentionActive = false;
        mentionDropdown.classList.remove('open');
        mentionDropdown.innerHTML = '';
        mentionStartPos = -1;
    }

    function highlightMentionItem(idx) {
        var items = mentionDropdown.querySelectorAll('.mention-item');
        items.forEach(function (item, i) {
            item.classList.toggle('selected', i === idx);
        });
        // Scroll selected into view
        if (items[idx]) items[idx].scrollIntoView({ block: 'nearest' });
    }

    function insertMention(file) {
        var val = inputEl.value;
        var before = val.substring(0, mentionStartPos);
        var after = val.substring(inputEl.selectionStart);
        inputEl.value = before + '@' + file + ' ' + after;
        var newPos = before.length + 1 + file.length + 1;
        inputEl.setSelectionRange(newPos, newPos);
        mentionedFiles.push(file);
        closeMentionDropdown();
        inputEl.focus();
    }

    function filterFiles(query) {
        if (!query) return workspaceFiles.slice(0, 12);
        var q = query.toLowerCase();
        return workspaceFiles.filter(function (f) {
            return f.toLowerCase().indexOf(q) !== -1;
        });
    }

    function getFileIcon(file) {
        var ext = file.split('.').pop().toLowerCase();
        var icons = {
            'py': '🐍', 'js': '📜', 'ts': '🔷', 'tsx': '⚛️',
            'jsx': '⚛️', 'css': '🎨', 'html': '🌐', 'json': '📋',
            'md': '📝', 'yaml': '⚙️', 'yml': '⚙️', 'toml': '⚙️',
            'txt': '📄', 'sh': '🖥️', 'bat': '🖥️', 'sql': '🗄️',
            'rs': '🦀', 'go': '🐹', 'java': '☕', 'rb': '💎'
        };
        return icons[ext] || '📄';
    }

    // ── Event Bindings ────────────────────────────────────────
    inputEl.addEventListener('keydown', function (e) {
        // Handle mention dropdown navigation
        if (mentionActive) {
            var items = mentionDropdown.querySelectorAll('.mention-item');
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                mentionSelectedIdx = Math.min(mentionSelectedIdx + 1, items.length - 1);
                highlightMentionItem(mentionSelectedIdx);
                return;
            }
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                mentionSelectedIdx = Math.max(mentionSelectedIdx - 1, 0);
                highlightMentionItem(mentionSelectedIdx);
                return;
            }
            if (e.key === 'Enter' || e.key === 'Tab') {
                e.preventDefault();
                var selected = items[mentionSelectedIdx];
                if (selected) {
                    var path = selected.querySelector('.mention-path').textContent;
                    insertMention(path);
                }
                return;
            }
            if (e.key === 'Escape') {
                e.preventDefault();
                closeMentionDropdown();
                return;
            }
        }

        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });

    inputEl.addEventListener('input', function () {
        autoResizeInput();

        // Check for @ mention trigger
        var val = inputEl.value;
        var cursorPos = inputEl.selectionStart;
        var textBefore = val.substring(0, cursorPos);

        // Find the last @ that starts a mention
        var atIdx = textBefore.lastIndexOf('@');
        if (atIdx !== -1) {
            // Check that @ is at start or preceded by whitespace
            var charBefore = atIdx > 0 ? textBefore[atIdx - 1] : ' ';
            if (charBefore === ' ' || charBefore === '\n' || atIdx === 0) {
                var query = textBefore.substring(atIdx + 1);
                // Only trigger if no spaces in query (we're still typing the filename)
                if (query.indexOf(' ') === -1 && workspaceFiles.length > 0) {
                    mentionStartPos = atIdx;
                    openMentionDropdown(query);
                    return;
                }
            }
        }
        closeMentionDropdown();
    });

    inputEl.addEventListener('blur', function () {
        // Delay to allow click on dropdown
        setTimeout(function () { closeMentionDropdown(); }, 200);
    });

    sendBtn.addEventListener('click', handleSend);

    // Cancel button
    if (cancelBtn) {
        cancelBtn.addEventListener('click', function () {
            vscode.postMessage({ type: 'CANCEL_REQUEST' });
        });
    }

    // New Chat
    if (newChatBtn) newChatBtn.addEventListener('click', function () {
        saveCurrentSession();
        currentSessionId = Date.now();
        showWelcome();
        toggleHistory(false);
        toggleSettings(false);
    });

    // History
    if (historyBtn) historyBtn.addEventListener('click', function () {
        toggleHistory();
        toggleSettings(false);
    });

    // Settings
    if (settingsBtn) settingsBtn.addEventListener('click', function () {
        toggleSettings();
        toggleHistory(false);
    });

    // Quick actions
    if (indexBtn) indexBtn.addEventListener('click', function () {
        vscode.postMessage({ type: 'INDEX_WORKSPACE' });
    });

    if (generateBtn) generateBtn.addEventListener('click', function () {
        var val = inputEl.value.trim();
        if (val) {
            addMessage('user', '/generate ' + val);
            vscode.postMessage({ type: 'GENERATE', request: val });
            inputEl.value = '';
        } else {
            inputEl.value = '/generate ';
            inputEl.focus();
        }
    });

    if (testsBtn) testsBtn.addEventListener('click', function () {
        var val = inputEl.value.trim();
        addMessage('user', 'Generate Tests' + (val ? ': ' + val : ''));
        vscode.postMessage({ type: 'GENERATE_TESTS', customRequest: val });
        inputEl.value = '';
    });

    // Export
    if (exportBtn) exportBtn.addEventListener('click', function () {
        var content = '# RepoPilot Chat Export\n\n';
        messagesContainer.querySelectorAll('.message').forEach(function (msg) {
            var role = msg.classList.contains('user') ? 'User' : msg.classList.contains('assistant') ? 'RepoPilot' : 'System';
            var contentEl = msg.querySelector('.msg-content');
            if (contentEl) content += '**' + role + ':** ' + contentEl.textContent + '\n\n---\n\n';
        });
        vscode.postMessage({ type: 'SAVE_CHAT', content: content });
        toggleSettings(false);
    });

    // Clear chat
    if (clearBtn) clearBtn.addEventListener('click', function () {
        showWelcome();
        vscode.postMessage({ type: 'MESSAGE_CLEAR' }); // Needed only for internal bookkeeping in chatPanel.ts
        toggleSettings(false);
    });

    // Welcome actions
    if (welcomeIndex) welcomeIndex.addEventListener('click', function () {
        vscode.postMessage({ type: 'INDEX_WORKSPACE' });
    });
    if (welcomeAsk) welcomeAsk.addEventListener('click', function () {
        inputEl.focus();
    });
    if (welcomeGenerate) welcomeGenerate.addEventListener('click', function () {
        inputEl.value = '/generate ';
        inputEl.focus();
    });

    // Close menus on outside click
    document.addEventListener('click', function (e) {
        if (settingsMenu.classList.contains('open') && !settingsMenu.contains(e.target) && e.target !== settingsBtn && !settingsBtn.contains(e.target)) {
            toggleSettings(false);
        }
    });

    // ── Error Toast ───────────────────────────────────────────
    function showErrorToast(message) {
        var existing = document.querySelector('.error-toast');
        if (existing) existing.remove();

        var toast = document.createElement('div');
        toast.className = 'error-toast';
        toast.textContent = '⚠ ' + message;
        document.body.appendChild(toast);
        setTimeout(function () { toast.remove(); }, 5000);
    }

    // ── Message Listener ──────────────────────────────────────
    window.addEventListener('message', function (event) {
        var msg = event.data;
        switch (msg.type) {
            case 'STATUS_UPDATE':
                updateStatus(msg.status, msg.repoName);
                break;
            case 'MESSAGE_APPEND':
                addMessage(msg.role, msg.content, msg.citations, msg.buttons);
                break;
            case 'MESSAGE_UPDATE':
                updateLastMessage(msg.content, msg.citations);
                break;
            case 'LOADING':
                setLoading(msg.loading);
                break;
            case 'MESSAGE_CLEAR':
                showWelcome();
                break;
            case 'ERROR_TOAST':
                showErrorToast(msg.message);
                break;
            case 'EXPORT_REQUEST':
                // Triggered by extension command
                if (exportBtn) exportBtn.click();
                break;
            case 'FILE_LIST':
                // Receive workspace file list for @ mentions
                if (msg.files && Array.isArray(msg.files)) {
                    workspaceFiles = msg.files;
                }
                break;
        }
    });

    // ── Init ──────────────────────────────────────────────────
    loadState();
    vscode.postMessage({ type: 'READY' });
})();
