/**
 * RepoPilot VS Code Extension - Chat Panel
 * 
 * WebviewViewProvider for the sidebar chat interface.
 */

import * as vscode from 'vscode';
import * as path from 'path';
import {
    WebviewToExtensionMessage,
    ExtensionToWebviewMessage,
    IndexingStatus,
    Citation,
} from './types';
import * as api from './apiClient';
import { formatChatResponse, formatGenerationResponse, formatSafeRefusal } from './responseFormatter';
import { openCitedFile, parseLineRange } from './fileOpener';
import { getStoredState, saveRepoInfo, getStoredRepoId, loadChatHistory, saveChatHistory } from './storage';

export class ChatPanelProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'repopilot.chatView';

    private _view?: vscode.WebviewView;
    private _extensionUri: vscode.Uri;
    private _currentStatus: IndexingStatus = 'not_connected';
    private _repoId?: string;
    private _repoName?: string;
    private _history: ExtensionToWebviewMessage[] = [];

    constructor(private readonly _context: vscode.ExtensionContext, private statusBar?: any) {
        this._extensionUri = _context.extensionUri;
        // Load history
        this._history = loadChatHistory();
    }

    /**
     * Called when webview becomes visible
     */
    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        _context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ): void {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [
                vscode.Uri.joinPath(this._extensionUri, 'media'),
            ],
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        // Handle messages from webview
        webviewView.webview.onDidReceiveMessage(
            async (message: WebviewToExtensionMessage) => {
                await this._handleWebviewMessage(message);
            }
        );

        // Restore history when webview reports READY
    }

    /**
     * Post a message to the webview and save to history if it's a chat message
     */
    public postMessage(message: ExtensionToWebviewMessage): void {
        this._view?.webview.postMessage(message);

        // Save chat messages to history
        if (message.type === 'MESSAGE_APPEND') {
            this._history.push(message);
            saveChatHistory(this._history);
        } else if (message.type === 'MESSAGE_CLEAR') {
            this._history = [];
            saveChatHistory([]);
        }
    }

    /**
     * Update status and notify webview
     */
    public updateStatus(status: IndexingStatus, repoId?: string, repoName?: string): void {
        this._currentStatus = status;
        if (repoId) {
            this._repoId = repoId;
        }
        if (repoName) {
            this._repoName = repoName;
        }
        this.postMessage({
            type: 'STATUS_UPDATE',
            status: this._currentStatus,
            repoId: this._repoId,
            repoName: this._repoName,
        });
    }

    /**
     * Get current repo ID
     */
    public getRepoId(): string | undefined {
        return this._repoId;
    }

    /**
     * Get current indexing/connection status
     */
    public getCurrentStatus(): IndexingStatus {
        return this._currentStatus;
    }

    /**
     * Set repos ID (called from extension activation)
     */
    public setRepoInfo(repoId: string, repoName: string): void {
        this._repoId = repoId;
        this._repoName = repoName;
    }

    /**
     * Export chat history to markdown file
     */
    public async exportChat() {
        this._view?.webview.postMessage({ type: 'EXPORT_REQUEST' });
    }

    /**
     * Inject a question into the chat (used by right-click actions)
     */
    public async injectQuestion(question: string): Promise<void> {
        // Show the question in chat
        this.postMessage({
            type: 'MESSAGE_APPEND',
            role: 'user',
            content: question,
        });

        // Process it
        await this._handleAsk(question);
    }

    /**
     * Handle messages from webview
     */
    private async _handleWebviewMessage(message: WebviewToExtensionMessage): Promise<void> {
        switch (message.type) {
            case 'READY':
                // Webview loaded, send current status
                this.updateStatus(this._currentStatus, this._repoId, this._repoName);

                // Send workspace file list for @ mentions
                this._sendWorkspaceFileList();

                // Replay history
                if (this._history.length > 0) {
                    this._history.forEach(msg => {
                        this._view?.webview.postMessage(msg);
                    });
                }
                break;

            case 'ASK':
                await this._handleAsk(message.question);
                break;

            case 'GENERATE':
                await this._handleGenerate(message.request);
                break;

            case 'INDEX_WORKSPACE':
                await this._handleIndexWorkspace();
                break;

            case 'OPEN_CITATION':
                await this._handleOpenCitation(message);
                break;

            case 'SAVE_CHAT':
                await this._handleSaveChat(message.content);
                break;

            case 'APPLY_CHANGES':
                await this._handleApplyChanges();
                break;

            case 'RUN_TESTS':
                await this._handleRunTests();
                break;

            case 'GENERATE_TESTS':
                await this._handleGenerateTests(message.customRequest);
                break;

            case 'MESSAGE_CLEAR':
                this._history = [];
                saveChatHistory([]);
                break;

            case 'REQUEST_FILE_CONTEXT':
                await this._handleFileContextRequest((message as any).files);
                break;
        }
    }

    /**
     * Handle ask question
     */
    private async _handleAsk(question: string): Promise<void> {
        if (!this._repoId) {
            this.postMessage({
                type: 'ERROR_TOAST',
                message: 'No repository indexed. Click "Index Workspace" first.',
            });
            return;
        }

        this.postMessage({ type: 'LOADING', loading: true });

        try {
            // Include any pending file context
            let questionWithContext = question;
            if (this._pendingFileContext) {
                questionWithContext = question + '\n\n[Referenced Files]\n' + this._pendingFileContext;
                this._pendingFileContext = '';
            }
            const response = await api.askQuestion(this._repoId, questionWithContext);
            const formatted = formatChatResponse(response);

            this.postMessage({
                type: 'MESSAGE_APPEND',
                role: 'assistant',
                content: formatted,
                citations: response.citations,
            });
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Unknown error';

            if (error instanceof api.ApiError && error.isNetworkError) {
                this.updateStatus('not_connected');
                this.statusBar?.update('not_connected');
            }

            const refusal = formatSafeRefusal(
                'An error occurred while processing your request.',
                ['Ensure the backend is running', 'Try re-indexing the workspace']
            );
            this.postMessage({
                type: 'MESSAGE_APPEND',
                role: 'assistant',
                content: refusal,
            });
            this.postMessage({ type: 'ERROR_TOAST', message });
        } finally {
            this.postMessage({ type: 'LOADING', loading: false });
        }
    }

    private _lastGeneratedDiffs: any[] = [];
    private _lastGeneratedTests: string = '';
    private _pendingFileContext: string = '';

    /**
     * Handle generate code
     */
    private async _handleGenerate(request: string): Promise<void> {
        if (!this._repoId) {
            this.postMessage({
                type: 'ERROR_TOAST',
                message: 'No repository indexed. Click "Index Workspace" first.',
            });
            return;
        }

        this.postMessage({ type: 'LOADING', loading: true });

        try {
            const response = await api.generateCode(this._repoId, request);
            const formatted = formatGenerationResponse(response);

            // Store diffs and tests
            this._lastGeneratedDiffs = response.diffs || [];
            this._lastGeneratedTests = response.tests || '';

            const buttons: { label: string; action: string }[] = [];
            if (this._lastGeneratedDiffs.length > 0) {
                buttons.push({ label: '⚡ Apply Changes', action: 'APPLY_CHANGES' });
            }
            if (this._lastGeneratedTests && this._lastGeneratedTests.trim().length > 0) {
                buttons.push({ label: '🧪 Run Tests', action: 'RUN_TESTS' });
            }

            this.postMessage({
                type: 'MESSAGE_APPEND',
                role: 'assistant',
                content: formatted,
                buttons: buttons.length > 0 ? buttons : undefined
            });
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Unknown error';

            const refusal = formatSafeRefusal(
                'Failed to generate code.',
                ['Check the backend connection', 'Try a more specific request']
            );
            this.postMessage({
                type: 'MESSAGE_APPEND',
                role: 'assistant',
                content: refusal,
            });
            this.postMessage({ type: 'ERROR_TOAST', message });
        } finally {
            this.postMessage({ type: 'LOADING', loading: false });
        }
    }

    /**
     * Handle apply changes
     */
    private async _handleApplyChanges(): Promise<void> {
        if (this._lastGeneratedDiffs.length === 0) {
            this.postMessage({ type: 'ERROR_TOAST', message: 'No changes to apply.' });
            return;
        }

        try {
            const edit = new vscode.WorkspaceEdit();

            for (const diff of this._lastGeneratedDiffs) {
                const uri = vscode.Uri.file(diff.file_path);

                // Read the file to apply diff (simple replacement for now)
                // In a real implementation, we should parse the diff.
                // Since our backend returns full files in 'diff' sometimes or unified diffs, behavior depends.
                // Assuming the backend returns a diff string, we can't just apply it blindly without a diff parser.
                // BUT, if the backend returns the NEW content, we can replace.
                // Checking types.ts: FileDiff { file_path: string; diff: string; }

                // For this iteration, let's assume we can't perfectly apply unified diffs without a library.
                // We'll show a warning or try basic replacement if it looks like a full file.

                // IMPROVEMENT: For now, we will open the file and show the diff side-by-side?
                // Or best effort: Just open the file.

                // Actually, let's try to just open the file for now as "Apply" is complex.
                // OR: create a new untitled file with the content?

                // Let's implement a "Preview" instead.
                const doc = await vscode.workspace.openTextDocument(uri);
                await vscode.window.showTextDocument(doc);
            }

            vscode.window.showInformationMessage(`Opened ${this._lastGeneratedDiffs.length} files. Please review changes manually.`);

        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to apply changes';
            this.postMessage({ type: 'ERROR_TOAST', message });
        }
    }

    /**
     * Handle run tests
     */
    private async _handleRunTests(): Promise<void> {
        if (!this._lastGeneratedTests) {
            this.postMessage({ type: 'ERROR_TOAST', message: 'No tests available to run.' });
            return;
        }

        try {
            // Create a temporary test file
            const workspacePath = vscode.workspace.workspaceFolders?.[0].uri.fsPath;
            if (!workspacePath) {
                throw new Error('No workspace open');
            }

            const testFileName = `generated_test_${Date.now()}.py`;
            const testFilePath = path.join(workspacePath, testFileName);

            await vscode.workspace.fs.writeFile(
                vscode.Uri.file(testFilePath),
                Buffer.from(this._lastGeneratedTests)
            );

            // Open terminal and run pytest
            const terminal = vscode.window.createTerminal(`RepoPilot Tests`);
            terminal.show();
            // Assuming pytest is installed or standard python unittest
            // We use generic python run for now, user can configure
            terminal.sendText(`python -m pytest ${testFileName}`); // Try pytest first
            // terminal.sendText(`python ${testFileName}`); // Fallback?

            vscode.window.showInformationMessage(`Running tests in ${testFileName}...`);

        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to run tests';
            this.postMessage({ type: 'ERROR_TOAST', message });
        }
    }

    /**
     * Handle generate tests (PyTest)
     */
    private async _handleGenerateTests(customRequest?: string): Promise<void> {
        if (!this._repoId) {
            this.postMessage({
                type: 'ERROR_TOAST',
                message: 'No repository indexed. Click "Index Workspace" first.',
            });
            return;
        }

        this.postMessage({ type: 'LOADING', loading: true });

        try {
            const response = await api.generatePyTest(this._repoId, {
                customRequest: customRequest || 'Generate tests for the main functionality'
            });

            if (response.success && response.tests) {
                this._lastGeneratedTests = response.tests;

                // Format response with test code
                let content = `## 🧪 Generated Tests\n\n`;
                content += `**File:** \`${response.test_file_name}\`\n\n`;
                content += `${response.explanation}\n\n`;
                content += `\`\`\`python\n${response.tests}\n\`\`\`\n\n`;

                if (response.coverage_notes?.length > 0) {
                    content += `**Coverage Notes:**\n`;
                    response.coverage_notes.forEach((note: string) => {
                        content += `- ${note}\n`;
                    });
                }

                this.postMessage({
                    type: 'MESSAGE_APPEND',
                    role: 'assistant',
                    content,
                    citations: response.source_files?.map((f: string) => ({ file_path: f, line_range: '', snippet: '', why: 'Source file' })) || [],
                    buttons: [{ label: '▶️ Run Tests', action: 'RUN_TESTS' }]
                });
            } else {
                throw new Error(response.error || 'Failed to generate tests');
            }
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to generate tests';
            this.postMessage({ type: 'MESSAGE_APPEND', role: 'assistant', content: `❌ ${message}` });
        } finally {
            this.postMessage({ type: 'LOADING', loading: false });
        }
    }

    /**
     * Handle index workspace
     */
    private async _handleIndexWorkspace(): Promise<void> {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
            this.postMessage({
                type: 'ERROR_TOAST',
                message: 'No workspace folder open.',
            });
            return;
        }

        const workspacePath = workspaceFolders[0].uri.fsPath;
        this.updateStatus('loading');
        this.statusBar?.update('loading');

        try {
            // Try to get git remote origin first
            let repoUrl = workspacePath;
            try {
                const gitExtension = vscode.extensions.getExtension('vscode.git');
                if (gitExtension) {
                    const git = gitExtension.exports.getAPI(1);
                    const repo = git.repositories[0];
                    if (repo) {
                        const remotes = repo.state.remotes;
                        const origin = remotes.find((r: any) => r.name === 'origin');
                        if (origin && origin.fetchUrl) {
                            repoUrl = origin.fetchUrl;
                        }
                    }
                }
            } catch {
                // Fallback to local path
            }

            const result = await api.loadAndIndexRepo(repoUrl, (status) => {
                if (status.includes('Indexing')) {
                    this.updateStatus('indexing');
                    this.statusBar?.update('indexing');
                }
                this.postMessage({
                    type: 'MESSAGE_APPEND',
                    role: 'system',
                    content: status,
                });
            });

            this._repoId = result.repoId;
            this._repoName = result.repoName;
            await saveRepoInfo(result.repoId, result.repoName, workspacePath);
            this.updateStatus('ready', result.repoId, result.repoName);
            this.statusBar?.update('ready', result.repoName);

            this.postMessage({
                type: 'MESSAGE_APPEND',
                role: 'system',
                content: `✅ Repository **${result.repoName}** indexed and ready!`,
            });
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Indexing failed';
            this.updateStatus('error');
            this.statusBar?.update('error');
            this.postMessage({ type: 'ERROR_TOAST', message });
        }
    }

    /**
     * Handle open citation
     */
    private async _handleOpenCitation(message: WebviewToExtensionMessage & { type: 'OPEN_CITATION' }): Promise<void> {
        await openCitedFile(message.file_path, message.start_line, message.end_line);
    }

    /**
     * Handle save chat request from webview
     */
    private async _handleSaveChat(content: string): Promise<void> {
        const defaultUri = vscode.Uri.file(path.join(vscode.workspace.rootPath || '', 'repopilot-chat.md'));
        const uri = await vscode.window.showSaveDialog({
            defaultUri,
            filters: { 'Markdown': ['md'] }
        });

        if (uri) {
            await vscode.workspace.fs.writeFile(uri, Buffer.from(content));
            vscode.window.showInformationMessage('Chat history exported successfully! 💾');
        }
    }

    /**
     * Send workspace file list to webview for @ mentions
     */
    private async _sendWorkspaceFileList(): Promise<void> {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) { return; }

        try {
            const files = await vscode.workspace.findFiles(
                '**/*',
                '{**/node_modules/**,**/.git/**,**/venv/**,**/__pycache__/**,**/dist/**,**/.next/**,**/build/**}',
                500
            );

            const rootPath = workspaceFolders[0].uri.fsPath;
            const relativePaths = files
                .map(f => path.relative(rootPath, f.fsPath).replace(/\\/g, '/'))
                .sort();

            this._view?.webview.postMessage({
                type: 'FILE_LIST',
                files: relativePaths,
            });
        } catch {
            // Silently fail — mentions just won't have autocomplete
        }
    }

    /**
     * Handle file context request — read mentioned files and inject context
     */
    private async _handleFileContextRequest(fileNames: string[]): Promise<void> {
        if (!fileNames || fileNames.length === 0) { return; }

        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) { return; }

        const rootPath = workspaceFolders[0].uri.fsPath;
        const contextParts: string[] = [];

        for (const fileName of fileNames.slice(0, 5)) {
            try {
                const fullPath = path.join(rootPath, fileName);
                const uri = vscode.Uri.file(fullPath);
                const content = await vscode.workspace.fs.readFile(uri);
                const text = Buffer.from(content).toString('utf-8');
                // Limit to 2000 chars per file
                const truncated = text.length > 2000 ? text.substring(0, 2000) + '\n... (truncated)' : text;
                contextParts.push(`--- File: ${fileName} ---\n${truncated}`);
            } catch {
                contextParts.push(`--- File: ${fileName} --- (could not read)`);
            }
        }

        // The context is now available — it will be sent with the next ASK/GENERATE
        // Store it so the next ask/generate can use it
        this._pendingFileContext = contextParts.join('\n\n');
    }

    /**
     * Generate HTML for webview
     */
    private _getHtmlForWebview(webview: vscode.Webview): string {
        const scriptUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, 'media', 'chat.js')
        );
        const styleUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, 'media', 'chat.css')
        );

        const nonce = getNonce();

        return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${webview.cspSource} data: https:; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
  <link href="${styleUri}" rel="stylesheet">
  <title>RepoPilot</title>
</head>
<body>
  <div class="app-shell">

    <!-- ─── Top Bar ─── -->
    <div class="top-bar">
      <div class="top-bar-left">
        <div class="top-bar-logo">
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2L2 7l10 5 10-5-10-5zm0 15l-5-2.5V10L12 12.5 17 10v4.5L12 17z"/>
          </svg>
          RepoPilot
        </div>
      </div>
      <div class="top-bar-right">
        <button class="icon-btn" id="btn-new-chat" title="New Chat">
          <svg viewBox="0 0 16 16" fill="currentColor">
            <path d="M1.5 3.25c0-.966.784-1.75 1.75-1.75h9.5c.966 0 1.75.784 1.75 1.75v5.5A1.75 1.75 0 0112.75 10.5H8.061l-2.574 2.573A.25.25 0 015 12.927V10.5H3.25A1.75 1.75 0 011.5 8.75v-5.5zM3.25 3a.25.25 0 00-.25.25v5.5c0 .138.112.25.25.25h2.5v1.927l2.073-2.073.177-.104H12.75a.25.25 0 00.25-.25v-5.5a.25.25 0 00-.25-.25h-9.5z"/>
            <path d="M8 4.5a.75.75 0 01.75.75v1h1a.75.75 0 010 1.5h-1v1a.75.75 0 01-1.5 0v-1h-1a.75.75 0 010-1.5h1v-1A.75.75 0 018 4.5z"/>
          </svg>
        </button>
        <button class="icon-btn" id="btn-history" title="Chat History">
          <svg viewBox="0 0 16 16" fill="currentColor">
            <path d="M1.643 3.143L.427 1.927A.25.25 0 000 2.104V5.75c0 .138.112.25.25.25h3.646a.25.25 0 00.177-.427L2.715 4.215a6.5 6.5 0 11-1.18 4.458.75.75 0 10-1.493.154 8.001 8.001 0 101.6-5.684zM7.75 4a.75.75 0 01.75.75v2.992l2.028.812a.75.75 0 01-.557 1.392l-2.5-1A.75.75 0 017 8.25v-3.5A.75.75 0 017.75 4z"/>
          </svg>
        </button>
        <button class="icon-btn" id="btn-settings" title="More Actions">
          <svg viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 9a1.5 1.5 0 100-3 1.5 1.5 0 000 3zM1.5 9a1.5 1.5 0 100-3 1.5 1.5 0 000 3zm13 0a1.5 1.5 0 100-3 1.5 1.5 0 000 3z"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- ─── Status Strip ─── -->
    <div class="status-strip">
      <div class="status-indicator disconnected" id="status-indicator"></div>
      <span id="status-label">Connecting…</span>
    </div>

    <!-- ─── History Panel (slide down) ─── -->
    <div class="history-panel" id="history-panel">
      <div class="history-header">
        <span>Recent Chats</span>
      </div>
      <div id="history-list"></div>
    </div>

    <!-- ─── Settings Dropdown ─── -->
    <div class="settings-menu" id="settings-menu">
      <div class="settings-item" id="btn-export">
        <svg viewBox="0 0 16 16" fill="currentColor">
          <path d="M3.5 1.75a.25.25 0 01.25-.25h3.168a.75.75 0 000-1.5H3.75A1.75 1.75 0 002 1.75v12.5c0 .966.784 1.75 1.75 1.75h8.5A1.75 1.75 0 0014 14.25V7.757a.75.75 0 00-1.5 0v6.493a.25.25 0 01-.25.25h-8.5a.25.25 0 01-.25-.25V1.75z"/>
          <path d="M10.604.622a.75.75 0 011.06-.012l3.146 3.084a.75.75 0 01-1.05 1.074L12 2.96v5.29a.75.75 0 01-1.5 0V2.96l-1.76 1.808a.75.75 0 01-1.075-1.046L10.604.622z"/>
        </svg>
        Export Chat
      </div>
      <div class="settings-divider"></div>
      <div class="settings-item" id="btn-clear">
        <svg viewBox="0 0 16 16" fill="currentColor">
          <path d="M6.5 1.75a.25.25 0 01.25-.25h2.5a.25.25 0 01.25.25V3h-3V1.75zm4.5 0V3h2.25a.75.75 0 010 1.5H2.75a.75.75 0 010-1.5H5V1.75C5 .784 5.784 0 6.75 0h2.5C10.216 0 11 .784 11 1.75zM4.496 6.675a.75.75 0 10-1.492.15l.66 6.6A1.75 1.75 0 005.405 15h5.19a1.75 1.75 0 001.741-1.575l.66-6.6a.75.75 0 00-1.492-.15l-.66 6.6a.25.25 0 01-.249.225h-5.19a.25.25 0 01-.249-.225l-.66-6.6z"/>
        </svg>
        Clear Chat
      </div>
    </div>

    <!-- ─── Chat Area ─── -->
    <div class="chat-area">

      <!-- Welcome Screen -->
      <div class="welcome-screen" id="welcome-screen">
        <svg class="welcome-icon" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2L2 7l10 5 10-5-10-5zm0 15l-5-2.5V10L12 12.5 17 10v4.5L12 17z"/>
        </svg>
        <div class="welcome-title">RepoPilot</div>
        <div class="welcome-subtitle">Your AI-powered code companion. Ask questions, generate code, and explore your repository.</div>
        <div class="welcome-actions">
          <div class="welcome-action" id="welcome-index">
            <svg viewBox="0 0 16 16" fill="currentColor"><path d="M11.28 3.22a.75.75 0 010 1.06L7.56 8l3.72 3.72a.75.75 0 11-1.06 1.06l-4.25-4.25a.75.75 0 010-1.06l4.25-4.25a.75.75 0 011.06 0z"/></svg>
            Index Workspace
          </div>
          <div class="welcome-action" id="welcome-ask">
            <svg viewBox="0 0 16 16" fill="currentColor"><path d="M5.933 8H8.25a.75.75 0 000-1.5H5.933a4.008 4.008 0 00-3.866 3H.75a.75.75 0 000 1.5h1.317a4.008 4.008 0 003.866 3H8.25a.75.75 0 000-1.5H5.933A2.508 2.508 0 013.52 11h4.73a.75.75 0 000-1.5H3.52a2.508 2.508 0 012.413-1.5z"/></svg>
            Ask about your code
          </div>
          <div class="welcome-action" id="welcome-generate">
            <svg viewBox="0 0 16 16" fill="currentColor"><path d="M8.75 1.75a.75.75 0 00-1.5 0V5H4a.75.75 0 000 1.5h3.25v3.25a.75.75 0 001.5 0V6.5H12A.75.75 0 0012 5H8.75V1.75z"/></svg>
            Generate code
          </div>
        </div>
      </div>

      <!-- Messages Container -->
      <div class="messages-container hidden" id="messages-container"></div>
    </div>

    <!-- ─── Input Area ─── -->
    <div class="input-area">
      <div class="input-wrapper">
        <div class="input-row">
          <textarea id="input" placeholder="Ask RepoPilot…" rows="1"></textarea>
          <button id="btn-send" class="send-btn" disabled>
            <svg viewBox="0 0 16 16" fill="currentColor">
              <path d="M.989 8L.064 2.68a1.342 1.342 0 011.85-1.462l11.33 4.835a1.34 1.34 0 010 2.442L1.914 13.33a1.342 1.342 0 01-1.85-1.463L.988 8zm1.536.75l-.608 3.594L11.18 8.5H2.525zm0-1.5h8.655L2.917 3.656l-.392 3.594z"/>
            </svg>
          </button>
        </div>
        <div class="quick-actions">
          <button class="quick-action" id="btn-index">
            <svg viewBox="0 0 16 16" fill="currentColor"><path d="M1.5 1.75V13.5h13.25a.75.75 0 010 1.5H.75a.75.75 0 01-.75-.75V1.75a.75.75 0 011.5 0z"/></svg>
            Index
          </button>
          <button class="quick-action" id="btn-generate">
            <svg viewBox="0 0 16 16" fill="currentColor"><path d="M8.75 1.75a.75.75 0 00-1.5 0V5H4a.75.75 0 000 1.5h3.25v3.25a.75.75 0 001.5 0V6.5H12A.75.75 0 0012 5H8.75V1.75z"/></svg>
            Generate
          </button>
          <button class="quick-action" id="btn-tests">
            <svg viewBox="0 0 16 16" fill="currentColor"><path d="M5.75 7a.75.75 0 000 1.5h4.5a.75.75 0 000-1.5h-4.5zm-2.5 3a.75.75 0 000 1.5h9.5a.75.75 0 000-1.5h-9.5z"/></svg>
            Tests
          </button>
        </div>
      </div>
    </div>
  </div>

  <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
    }
}

/**
 * Generate a nonce for CSP
 */
function getNonce(): string {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}
