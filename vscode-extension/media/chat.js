/**
 * RepoPilot VS Code Extension - Chat Webview JavaScript
 */

(function () {
    // @ts-ignore
    const vscode = acquireVsCodeApi();

    // DOM elements
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    const messagesContainer = document.getElementById('messages');
    const inputEl = document.getElementById('input');
    const sendBtn = document.getElementById('btn-send');
    const indexBtn = document.getElementById('btn-index');
    const generateBtn = document.getElementById('btn-generate');
    const testsBtn = document.getElementById('btn-tests');

    // State
    let isLoading = false;
    let currentStatus = 'not_connected';

    // Status text mapping
    const statusLabels = {
        'not_connected': '⚠️ Backend not connected',
        'not_indexed': '📁 Workspace not indexed',
        'loading': '⏳ Loading repository...',
        'indexing': '🔄 Indexing in progress...',
        'ready': '✅ Ready',
        'error': '❌ Error occurred'
    };

    /**
     * Update UI status
     */
    function updateStatus(status, repoName) {
        currentStatus = status;
        statusDot.className = 'status-dot ' + status;

        let label = statusLabels[status] || status;
        if (status === 'ready' && repoName) {
            label = `✅ ${repoName}`;
        }
        statusText.textContent = label;

        // Enable/disable buttons based on status
        const canAsk = status === 'ready';
        sendBtn.disabled = !canAsk || isLoading;
        generateBtn.disabled = !canAsk || isLoading;
        if (testsBtn) testsBtn.disabled = !canAsk || isLoading;
        indexBtn.disabled = isLoading;
    }

    /**
     * Set loading state
     */
    function setLoading(loading) {
        isLoading = loading;
        sendBtn.disabled = loading || currentStatus !== 'ready';
        generateBtn.disabled = loading || currentStatus !== 'ready';
        if (testsBtn) testsBtn.disabled = loading || currentStatus !== 'ready';
        indexBtn.disabled = loading;
        inputEl.disabled = loading;

        if (loading) {
            addLoadingIndicator();
        } else {
            removeLoadingIndicator();
        }
    }

    /**
     * Add loading indicator
     */
    function addLoadingIndicator() {
        removeLoadingIndicator();
        const el = document.createElement('div');
        el.className = 'loading-indicator';
        el.id = 'loading-indicator';
        el.innerHTML = '<div class="loading-spinner"></div><span>Thinking...</span>';
        messagesContainer.appendChild(el);
        scrollToBottom();
    }

    /**
     * Remove loading indicator
     */
    function removeLoadingIndicator() {
        const el = document.getElementById('loading-indicator');
        if (el) {
            el.remove();
        }
    }

    /**
     * Add a message to the chat
     */
    function addMessage(role, content, citations) {
        // Remove welcome message if present
        const welcome = messagesContainer.querySelector('.welcome-message');
        if (welcome) {
            welcome.remove();
        }

        const el = document.createElement('div');
        el.className = 'message ' + role;

        const contentEl = document.createElement('div');
        contentEl.className = 'message-content';
        contentEl.innerHTML = parseMarkdown(content);
        el.appendChild(contentEl);

        if (citations && citations.length > 0) {
            const citationsEl = document.createElement('div');
            citationsEl.className = 'citations';
            citationsEl.innerHTML = '<div class="citations-title">📎 Citations</div>';

            citations.forEach(cit => {
                const citBtn = document.createElement('button');
                citBtn.className = 'citation';
                citBtn.textContent = cit.file_path + (cit.line_range ? ` (${cit.line_range})` : '');
                citBtn.onclick = () => openCitation(cit);
                citationsEl.appendChild(citBtn);
            });

            el.appendChild(citationsEl);
        }

        // Add action buttons
        // @ts-ignore
        if (arguments[3] && Array.isArray(arguments[3])) { // buttons passed as 4th arg
            const buttons = arguments[3];
            const actionsEl = document.createElement('div');
            actionsEl.className = 'message-actions';

            buttons.forEach(btn => {
                const actionBtn = document.createElement('button');
                actionBtn.className = 'action-btn primary';
                actionBtn.textContent = btn.label;
                actionBtn.style.marginTop = '10px';
                actionBtn.onclick = () => {
                    vscode.postMessage({ type: btn.action });
                };
                actionsEl.appendChild(actionBtn);
            });
            el.appendChild(actionsEl);
        }

        messagesContainer.appendChild(el);
        scrollToBottom();
    }

    /**
     * Clear all messages
     */
    function clearMessages() {
        messagesContainer.innerHTML = '';
    }

    /**
     * Show toast notification
     */
    function showToast(message) {
        // Remove existing toast
        const existing = document.querySelector('.toast');
        if (existing) {
            existing.remove();
        }

        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.remove();
        }, 4000);
    }

    /**
     * Basic syntax highlighting for code
     */
    function highlightCode(code, lang) {
        if (!code) return '';

        // Language-specific keyword sets
        const pythonKeywords = /\b(def|class|if|elif|else|for|while|try|except|finally|with|as|import|from|return|yield|raise|break|continue|pass|async|await|lambda|and|or|not|in|is|None|True|False|self)\b/g;
        const jsKeywords = /\b(function|const|let|var|if|else|for|while|do|switch|case|break|continue|return|try|catch|finally|throw|class|extends|import|export|from|async|await|new|this|typeof|instanceof|null|undefined|true|false)\b/g;

        let highlighted = code;

        // Apply language-specific highlighting
        if (lang === 'python' || lang === 'py') {
            // Python comments
            highlighted = highlighted.replace(/(#.*)$/gm, '<span class="hl-comment">$1</span>');
            // Python keywords
            highlighted = highlighted.replace(pythonKeywords, '<span class="hl-keyword">$1</span>');
            // Decorators
            highlighted = highlighted.replace(/(@\w+)/g, '<span class="hl-decorator">$1</span>');
        } else if (lang === 'javascript' || lang === 'js' || lang === 'typescript' || lang === 'ts') {
            // JS comments
            highlighted = highlighted.replace(/(\/\/.*)$/gm, '<span class="hl-comment">$1</span>');
            // JS keywords
            highlighted = highlighted.replace(jsKeywords, '<span class="hl-keyword">$1</span>');
        }

        // Common patterns for all languages
        // Strings (double and single quotes) - simplified to avoid regex issues
        highlighted = highlighted.replace(/(&quot;[^&]*&quot;|'[^']*')/g, '<span class="hl-string">$1</span>');
        // Numbers
        highlighted = highlighted.replace(/\b(\d+\.?\d*)\b/g, '<span class="hl-number">$1</span>');

        return highlighted;
    }

    /**
     * Parse basic markdown to HTML
     */
    function parseMarkdown(text) {
        if (!text) return '';

        // Escape HTML
        let html = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Code blocks with copy button and syntax highlighting
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (match, lang, code) => {
            const escapedCode = code.trim();
            const highlightedCode = highlightCode(escapedCode, lang || 'code');
            return `<div class="code-block-wrapper">
        <div class="code-block-header">
          <span class="code-lang">${lang || 'code'}</span>
          <button class="copy-btn" data-code="${escapedCode.replace(/"/g, '&quot;')}" title="Copy code">📋 Copy</button>
        </div>
        <pre><code class="language-${lang}">${highlightedCode}</code></pre>
      </div>`;
        });

        // Inline code
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Bold
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Headers
        html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
        html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>');
        html = html.replace(/^# (.+)$/gm, '<h3>$1</h3>');

        // Lists
        html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

        // Line breaks
        html = html.replace(/\n\n/g, '</p><p>');
        html = html.replace(/\n/g, '<br>');

        // Wrap in paragraph
        if (!html.startsWith('<')) {
            html = '<p>' + html + '</p>';
        }

        return html;
    }

    /**
     * Open citation in editor
     */
    function openCitation(citation) {
        let startLine, endLine;

        if (citation.line_range) {
            const match = citation.line_range.match(/(\d+)(?:-(\d+))?/);
            if (match) {
                startLine = parseInt(match[1], 10);
                endLine = match[2] ? parseInt(match[2], 10) : startLine;
            }
        }

        vscode.postMessage({
            type: 'OPEN_CITATION',
            file_path: citation.file_path,
            start_line: startLine,
            end_line: endLine
        });
    }

    /**
     * Scroll to bottom of messages
     */
    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    /**
     * Send a question
     */
    function sendQuestion() {
        const text = inputEl.value.trim();
        if (!text) return;

        // Check for generate prefix
        if (text.toLowerCase().startsWith('/generate ')) {
            const request = text.substring(10).trim();
            addMessage('user', text);
            inputEl.value = '';
            vscode.postMessage({ type: 'GENERATE', request });
        } else {
            addMessage('user', text);
            inputEl.value = '';
            vscode.postMessage({ type: 'ASK', question: text });
        }
    }

    // Event listeners
    sendBtn.addEventListener('click', sendQuestion);

    inputEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendQuestion();
        }
    });

    indexBtn.addEventListener('click', () => {
        vscode.postMessage({ type: 'INDEX_WORKSPACE' });
    });

    generateBtn.addEventListener('click', () => {
        const text = inputEl.value.trim();
        if (text) {
            addMessage('user', '/generate ' + text);
            inputEl.value = '';
            vscode.postMessage({ type: 'GENERATE', request: text });
        } else {
            inputEl.placeholder = 'Describe the code to generate...';
            inputEl.focus();
        }
    });

    // Tests button handler
    if (testsBtn) {
        testsBtn.addEventListener('click', () => {
            const text = inputEl.value.trim();
            addMessage('user', '🧪 Generate tests' + (text ? `: ${text}` : ''));
            inputEl.value = '';
            vscode.postMessage({ type: 'GENERATE_TESTS', customRequest: text || undefined });
        });
    }

    // Copy button handler (event delegation)
    document.addEventListener('click', (e) => {
        if (e.target && e.target.classList.contains('copy-btn')) {
            const code = e.target.getAttribute('data-code');
            if (code) {
                // Create temporary textarea to copy
                const textarea = document.createElement('textarea');
                textarea.value = code.replace(/&quot;/g, '"').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);

                // Show feedback
                const originalText = e.target.textContent;
                e.target.textContent = '✓ Copied!';
                setTimeout(() => {
                    e.target.textContent = originalText;
                }, 2000);
            }
        }
    });

    // Handle messages from extension
    window.addEventListener('message', (event) => {
        const message = event.data;

        switch (message.type) {
            case 'STATUS_UPDATE':
                updateStatus(message.status, message.repoName);
                break;

            case 'MESSAGE_APPEND':
                addMessage(message.role, message.content, message.citations, message.buttons);
                break;

            case 'MESSAGE_CLEAR':
                clearMessages();
                break;

            case 'ERROR_TOAST':
                showToast(message.message);
                break;

            case 'LOADING':
                setLoading(message.loading);
                break;

            case 'EXPORT_REQUEST':
                exportChat();
                break;
        }
    });

    /**
     * Export chat history
     */
    function exportChat() {
        let content = '# RepoPilot Chat History\n\n';
        document.querySelectorAll('.message').forEach(msg => {
            const role = msg.classList.contains('user') ? 'User' : 'RepoPilot';
            const text = msg.querySelector('.message-content').innerText;
            content += `## ${role}\n${text}\n\n`;
        });
        vscode.postMessage({ type: 'SAVE_CHAT', content: content });
    }

    // Export button
    const exportBtn = document.getElementById('btn-export');
    if (exportBtn) {
        exportBtn.addEventListener('click', exportChat);
    }

    // Notify extension that webview is ready
    vscode.postMessage({ type: 'READY' });
})();
