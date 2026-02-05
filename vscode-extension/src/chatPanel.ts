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
            const response = await api.askQuestion(this._repoId, question);
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
     * Generate HTML for webview
     */
    private _getHtmlForWebview(webview: vscode.Webview): string {
        const scriptUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, 'media', 'chat.js')
        );
        const styleUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, 'media', 'chat.css')
        );
        const iconUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, 'media', 'icon.svg')
        );

        const nonce = getNonce();

        return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${webview.cspSource} data: https:; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
  <link href="${styleUri}" rel="stylesheet">
  <title>RepoPilot Chat</title>
</head>
<body>
  <div class="chat-container">
    <div class="header">
        <div class="title-group">
            <svg class="header-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM12 4C16.42 4 20 7.58 20 12C20 16.42 16.42 20 12 20C7.58 20 4 16.42 4 12C4 7.58 7.58 4 12 4Z" fill="currentColor" fill-opacity="0.3"/>
                <path d="M12 6C8.69 6 6 8.69 6 12C6 15.31 8.69 18 12 18C15.31 18 18 15.31 18 12C18 8.69 15.31 6 12 6ZM12 16C9.79 16 8 14.21 8 12C8 9.79 9.79 8 12 8C14.21 8 16 9.79 16 12C16 14.21 14.21 16 12 16Z" fill="currentColor"/>
                <path d="M10 11H8V13H10V11Z" fill="currentColor"/>
                <path d="M16 11H14V13H16V11Z" fill="currentColor"/>
            </svg>
            <span>RepoPilot AI</span>
        </div>
        <button id="btn-export" class="icon-btn" title="Export Chat">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M19 9H15V3H9V9H5L12 17L19 9ZM5 19V21H19V19H5Z" fill="currentColor"/>
            </svg>
        </button>
    </div>

    <div class="status-bar" id="status-bar">
      <span class="status-dot" id="status-dot"></span>
      <span class="status-text" id="status-text">Connecting...</span>
    </div>
    
    <div class="messages" id="messages">
      <div class="welcome-message">
        <h3>🚀 Welcome to RepoPilot AI</h3>
        <p>Ask questions about your codebase or generate code with repository-grounded answers.</p>
      </div>
    </div>
    
    <div class="input-area">
      <div class="button-row">
        <button id="btn-index" class="action-btn" title="Index Workspace">
          📁 Index
        </button>
        <button id="btn-tests" class="action-btn secondary" title="Generate PyTest Tests">
          🧪 Tests
        </button>
        <button id="btn-generate" class="action-btn secondary" title="Generate Code (prefix with /generate)">
          ⚡ Generate
        </button>
      </div>
      <div class="input-row">
        <textarea id="input" placeholder="Ask about your code..." rows="2"></textarea>
        <button id="btn-send" class="send-btn" title="Send">
          ➤
        </button>
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
