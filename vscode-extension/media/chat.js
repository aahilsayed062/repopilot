/**
 * RepoPilot VS Code Extension - Fluid Terminal JS
 */

(function () {
    // @ts-ignore
    const vscode = acquireVsCodeApi();

    // Elements
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    const messagesContainer = document.getElementById('messages');
    const inputEl = document.getElementById('input');
    const sendBtn = document.getElementById('btn-send');

    // Chips
    const indexBtn = document.getElementById('btn-index');
    const testsBtn = document.getElementById('btn-tests');
    const generateBtn = document.getElementById('btn-generate');

    let isLoading = false;
    let currentStatus = 'not_connected';

    // Status Mapping
    const statusLabels = {
        'not_connected': 'Disconnected',
        'not_indexed': 'Not Indexed',
        'loading': 'Loading...',
        'indexing': 'Indexing...',
        'ready': 'Ready',
        'error': 'Error'
    };

    /**
     * Update UI Status
     */
    function updateStatus(status, repoName) {
        currentStatus = status;

        // Remove old classes
        statusDot.className = 'status-dot';

        // Add new class
        if (status === 'ready') statusDot.classList.add('active');
        if (status === 'indexing' || status === 'loading') statusDot.classList.add('active'); // Pulse animation handled by CSS if needed, or we can add a specific class

        let label = statusLabels[status] || status;
        if (status === 'ready' && repoName) {
            label = repoName;
        }
        statusText.textContent = label;

        const isReady = status === 'ready';
        setInputState(!isLoading && isReady);
    }

    function setInputState(enabled) {
        inputEl.disabled = !enabled;
        sendBtn.disabled = !enabled;

        // Update chips opacity/pointer-events via CSS or here
        const chips = document.querySelectorAll('.chip');
        chips.forEach(c => {
            c.style.opacity = enabled ? '1' : '0.5';
            c.style.pointerEvents = enabled ? 'auto' : 'none';
        });
    }

    function setLoading(loading) {
        isLoading = loading;
        setInputState(!loading && currentStatus === 'ready');

        if (loading) {
            addThinking();
            // Scroll to bottom
            setTimeout(scrollToBottom, 50);
        } else {
            removeThinking();
        }
    }

    function addThinking() {
        removeThinking();
        const div = document.createElement('div');
        div.id = 'thinking-indicator';
        div.className = 'message assistant';
        div.innerHTML = `
            <div class="message-bubble thinking">
                <div class="pulse-dot"></div>
                <span>Thinking...</span>
            </div>
        `;
        messagesContainer.appendChild(div);
    }

    function removeThinking() {
        const el = document.getElementById('thinking-indicator');
        if (el) el.remove();
    }

    /**
     * Add Message to Chat
     */
    function addMessage(role, content, citations, buttons) {
        removeThinking(); // Ensure thinking is gone

        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}`;

        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';

        // Parse Markdown
        bubble.innerHTML = parseMarkdown(content);

        // Add Citations (fluid chips)
        if (citations && citations.length > 0) {
            const citDiv = document.createElement('div');
            citDiv.className = 'citations';
            citations.forEach(cit => {
                const tag = document.createElement('span');
                tag.className = 'citation-tag';
                tag.textContent = `${cit.file_path}${cit.line_range ? ':' + cit.line_range : ''}`;
                tag.onclick = () => {
                    // Start/End line parsing
                    let startLine, endLine;
                    if (cit.line_range) {
                        const match = cit.line_range.match(/(\d+)(?:-(\d+))?/);
                        if (match) {
                            startLine = parseInt(match[1]);
                            endLine = match[2] ? parseInt(match[2]) : startLine;
                        }
                    }
                    vscode.postMessage({
                        type: 'OPEN_CITATION',
                        file_path: cit.file_path,
                        start_line: startLine,
                        end_line: endLine
                    });
                };
                citDiv.appendChild(tag);
            });
            bubble.appendChild(citDiv);
        }

        // Add Action Buttons (if any - e.g. from Generate)
        if (buttons && buttons.length > 0) {
            const btnDiv = document.createElement('div');
            btnDiv.className = 'action-buttons';
            btnDiv.style.marginTop = '10px';
            btnDiv.style.padding = '0'; // Override default padding

            buttons.forEach(btn => {
                const b = document.createElement('button');
                b.className = 'chip';
                b.textContent = btn.label;
                b.onclick = () => vscode.postMessage({ type: btn.action });
                btnDiv.appendChild(b);
            });
            bubble.appendChild(btnDiv);
        }

        msgDiv.appendChild(bubble);
        messagesContainer.appendChild(msgDiv);
        scrollToBottom();
    }

    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function parseMarkdown(text) {
        if (!text) return '';
        let html = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

        // Code Blocks
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
            return `<div class="code-block">
                <div class="code-header">
                    <span>${lang || 'text'}</span>
                </div>
                <pre class="code-content"><code>${code.trim()}</code></pre>
            </div>`;
        });

        // Inline Code
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Bold
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Headers
        html = html.replace(/^### (.+)$/gm, '<strong>$1</strong>'); // Map headers to bold for compactness

        // Lines
        html = html.replace(/\n/g, '<br>');

        return html;
    }

    // Input Handling
    function handleSend() {
        const text = inputEl.value.trim();
        if (!text) return;

        // Check commands
        if (text.startsWith('/generate ')) {
            addMessage('user', text);
            vscode.postMessage({ type: 'GENERATE', request: text.substring(10) });
        } else {
            addMessage('user', text);
            vscode.postMessage({ type: 'ASK', question: text });
        }

        inputEl.value = '';
    }

    inputEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });

    sendBtn.addEventListener('click', handleSend);

    // Chip Handlers
    if (indexBtn) indexBtn.addEventListener('click', () => vscode.postMessage({ type: 'INDEX_WORKSPACE' }));

    if (generateBtn) generateBtn.addEventListener('click', () => {
        const val = inputEl.value.trim();
        if (val) {
            addMessage('user', `/generate ${val}`);
            vscode.postMessage({ type: 'GENERATE', request: val });
            inputEl.value = '';
        } else {
            inputEl.value = '/generate ';
            inputEl.focus();
        }
    });

    if (testsBtn) testsBtn.addEventListener('click', () => {
        const val = inputEl.value.trim();
        addMessage('user', 'Run Tests' + (val ? `: ${val}` : ''));
        vscode.postMessage({ type: 'GENERATE_TESTS', customRequest: val });
        inputEl.value = '';
    });

    // Message Listener
    window.addEventListener('message', event => {
        const msg = event.data;
        switch (msg.type) {
            case 'STATUS_UPDATE':
                updateStatus(msg.status, msg.repoName);
                break;
            case 'MESSAGE_APPEND':
                addMessage(msg.role, msg.content, msg.citations, msg.buttons);
                break;
            case 'LOADING':
                setLoading(msg.loading);
                break;
            case 'MESSAGE_CLEAR':
                messagesContainer.innerHTML = '';
                break;
            case 'ERROR_TOAST':
                // Using addMessage for error as simplified toast
                // Actually maybe just an assistant message red?
                addMessage('assistant', `⚠️ **Error:** ${msg.message}`);
                break;
        }
    });

    // Ready signal
    vscode.postMessage({ type: 'READY' });

})();
