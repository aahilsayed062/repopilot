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
import { formatChatResponse, formatGenerationResponse, formatSafeRefusal, formatImpactReport, formatEvaluationReport } from './responseFormatter';
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
    private _abortController?: AbortController;

    constructor(private readonly _context: vscode.ExtensionContext, private statusBar?: any) {
        this._extensionUri = _context.extensionUri;
        // Always start fresh — don't replay stale history
        this._history = [];
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

            case 'REFINE':
                await this._handleRefine((message as any).request);
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

            case 'CANCEL_REQUEST':
                this._handleCancelRequest();
                break;

            case 'ACCEPT_FILE':
                await this._handleAcceptFile((message as any).file_path);
                break;

            case 'REJECT_FILE':
                this._handleRejectFile((message as any).file_path);
                break;

            case 'ACCEPT_ALL':
                await this._handleAcceptAll();
                break;
        }
    }

    /**
     * Handle ask question — uses /chat/smart for dynamic multi-agent routing (Feature 1)
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
        this._abortController = new AbortController();

        try {
            // Include any pending file context
            let questionWithContext = question;
            const contextFileHints: string[] = [];
            if (this._pendingFileContext) {
                questionWithContext = question + '\n\n[Referenced Files]\n' + this._pendingFileContext;
                this._pendingFileContext = '';
            }

            // Heuristic: simple explain/question queries → stream for better UX
            const GEN_KEYWORDS = /\b(add|create|modify|implement|generate|write|build|fix|refactor|change|update|delete|remove|rename|move|extract|convert|replace|insert|make)\b/i;
            const isLikelyExplain = !GEN_KEYWORDS.test(question);

            if (isLikelyExplain) {
                // Stream token-by-token for explain-only queries
                this.postMessage({
                    type: 'MESSAGE_APPEND',
                    role: 'assistant',
                    content: '> 💬 **Route:** EXPLAIN (streaming)\n\n',
                });

                let accumulated = '> 💬 **Route:** EXPLAIN (streaming)\n\n';
                for await (const token of api.streamChat(this._repoId, questionWithContext)) {
                    if (this._abortController?.signal.aborted) break;
                    accumulated += token;
                    this.postMessage({ type: 'MESSAGE_UPDATE', content: accumulated });
                }

                this.postMessage({ type: 'LOADING', loading: false });
                return;
            }

            // Use /chat/smart for dynamic multi-agent routing (Feature 1)
            const smartResult = await api.smartChat(this._repoId, questionWithContext, undefined, contextFileHints);

            // Build routing badge
            const routing = smartResult.routing || {};
            const primaryAction = routing.primary_action || 'EXPLAIN';
            const agentsUsed = smartResult.agents_used || [];
            const agentsSkipped = smartResult.agents_skipped || [];

            let content = '';

            // Routing info header
            const routingEmoji: Record<string, string> = {
                'EXPLAIN': '💬', 'GENERATE': '⚙️', 'TEST': '🧪',
                'DECOMPOSE': '🔀', 'REFUSE': '🚫',
            };
            const emoji = routingEmoji[primaryAction] || '🤖';
            content += `> ${emoji} **Route:** ${primaryAction}`;
            if (agentsUsed.length > 1) {
                content += ` + ${agentsUsed.slice(1).join(', ')}`;
            }
            if (agentsSkipped.length > 0) {
                content += ` · Skipped: ${agentsSkipped.join(', ')}`;
            }
            content += '\n\n';

            // Main answer
            content += smartResult.answer || '';

            // If generation results exist, format them
            if (smartResult.generate && typeof smartResult.generate === 'object' && !smartResult.generate.error) {
                const genData = smartResult.generate;
                if (genData.plan) {
                    content += `\n\n### 📋 Plan\n${genData.plan}`;
                }
                if (genData.diffs && genData.diffs.length > 0) {
                    this._lastGeneratedDiffs = genData.diffs;
                    content += `\n\n### 🔧 Changes — ${genData.diffs.length} file(s)`;
                    for (const diff of genData.diffs) {
                        content += `\n\n#### 📁 ${diff.file_path}`;
                        if (diff.diff) {
                            content += `\n\`\`\`diff\n${diff.diff}\n\`\`\``;
                        }
                    }
                }
                if (genData.tests) {
                    this._lastGeneratedTests = genData.tests;
                    content += `\n\n### 🧪 Tests\n\`\`\`python\n${genData.tests}\n\`\`\``;
                }
            }

            // If test results exist, show them
            if (smartResult.test && typeof smartResult.test === 'object' && !smartResult.test.error) {
                const testData = smartResult.test;
                if (testData.tests) {
                    content += `\n\n### 🧪 Generated Tests\n\`\`\`python\n${testData.tests}\n\`\`\``;
                }
            }

            // Evaluation results (Feature 3)
            if (smartResult.evaluation && smartResult.evaluation.enabled) {
                const evalFormatted = formatEvaluationReport(smartResult.evaluation);
                if (evalFormatted) {
                    content += `\n\n---\n${evalFormatted}`;
                }

                // Auto-apply MERGE_FEEDBACK: swap original diffs with controller's improved code
                if (smartResult.evaluation.controller?.decision === 'MERGE_FEEDBACK'
                    && smartResult.evaluation_improved_code
                    && smartResult.evaluation_improved_code.length > 0) {
                    this._lastGeneratedDiffs = smartResult.evaluation_improved_code.map((ic: any) => ({
                        file_path: ic.file_path,
                        content: ic.code,
                        code: ic.code,
                        diff: ic.code,
                    }));
                    content += `\n\n> ✨ **Merged feedback applied** — Accept buttons now use the improved code.`;
                }
            }

            // Impact analysis on generated code
            if (this._lastGeneratedDiffs.length > 0 && this._repoId) {
                try {
                    const changedFiles = this._lastGeneratedDiffs.map((d: any) => d.file_path);
                    const codeChanges = this._lastGeneratedDiffs
                        .map((d: any) => `--- ${d.file_path} ---\n${d.diff || ''}`)
                        .join('\n');
                    const impact = await api.analyzeImpact(this._repoId, changedFiles, codeChanges);
                    const impactFormatted = formatImpactReport(impact);
                    content += `\n\n---\n${impactFormatted}`;
                } catch {
                    // Impact analysis is non-critical
                }
            }

            // Build buttons
            const buttons: { label: string; action: string }[] = [];
            if (this._lastGeneratedDiffs.length > 0) {
                buttons.push({ label: '✅ Accept All', action: 'ACCEPT_ALL' });
            }
            if (this._lastGeneratedTests && this._lastGeneratedTests.trim().length > 0) {
                buttons.push({ label: '🧪 Run Tests', action: 'RUN_TESTS' });
            }

            this.postMessage({
                type: 'MESSAGE_APPEND',
                role: 'assistant',
                content,
                citations: smartResult.citations?.map((c: any) => ({
                    file_path: c.file_path,
                    line_range: c.line_range || '',
                    snippet: c.snippet || '',
                    why: c.why || '',
                })),
                buttons: buttons.length > 0 ? buttons : undefined,
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
                content: refusal + `\n\nError details: ${message}`,
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
        this._abortController = new AbortController();

        try {
            // Include any pending @file context so LLM sees existing file content
            let requestWithContext = request;
            if (this._pendingFileContext) {
                requestWithContext = request + '\n\n[Existing File Content]\n' + this._pendingFileContext;
                this._pendingFileContext = '';
            }

            const response = await api.generateCode(this._repoId, requestWithContext);
            const formatted = formatGenerationResponse(response);

            // Store diffs and tests
            this._lastGeneratedDiffs = response.diffs || [];
            this._lastGeneratedTests = response.tests || '';

            const buttons: { label: string; action: string }[] = [];
            if (this._lastGeneratedDiffs.length > 0) {
                buttons.push({ label: '✅ Accept All', action: 'ACCEPT_ALL' });
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

            // Feature 4: Auto-run Impact Analysis (compact inline)
            if (this._lastGeneratedDiffs.length > 0 && this._repoId) {
                try {
                    const changedFiles = this._lastGeneratedDiffs.map((d: any) => d.file_path);
                    const codeChanges = this._lastGeneratedDiffs
                        .map((d: any) => `--- ${d.file_path} ---\n${d.diff || ''}`)
                        .join('\n');
                    const impact = await api.analyzeImpact(this._repoId, changedFiles, codeChanges);
                    const impactFormatted = formatImpactReport(impact);
                    // Append to the same message (not a separate bubble)
                    let updatedContent = formatted + '\n\n---\n' + impactFormatted;

                    // Feature 3: Auto-run LLM Evaluation
                    try {
                        const evalResult = await api.evaluateCode(
                            request,
                            this._lastGeneratedDiffs,
                            this._lastGeneratedTests,
                        );
                        if (evalResult.enabled) {
                            const evalFormatted = formatEvaluationReport(evalResult);
                            updatedContent += '\n\n---\n' + evalFormatted;
                        }
                    } catch (evalErr) {
                        console.warn('Evaluation failed (non-critical):', evalErr);
                    }

                    this.postMessage({
                        type: 'MESSAGE_UPDATE',
                        content: updatedContent,
                    });
                } catch (impactErr) {
                    // Impact analysis is non-critical — don't block on failure
                    console.warn('Impact analysis failed (non-critical):', impactErr);

                    // Still try evaluation even if impact fails
                    try {
                        const evalResult = await api.evaluateCode(
                            request,
                            this._lastGeneratedDiffs,
                            this._lastGeneratedTests,
                        );
                        if (evalResult.enabled) {
                            const evalFormatted = formatEvaluationReport(evalResult);
                            this.postMessage({
                                type: 'MESSAGE_UPDATE',
                                content: formatted + '\n\n---\n' + evalFormatted,
                            });
                        }
                    } catch {
                        // Both non-critical
                    }
                }
            }
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
     * Handle iterative refinement (Feature 2)
     */
    private async _handleRefine(request: string): Promise<void> {
        if (!this._repoId) {
            this.postMessage({
                type: 'ERROR_TOAST',
                message: 'No repository indexed. Click "Index Workspace" first.',
            });
            return;
        }

        this.postMessage({ type: 'LOADING', loading: true });

        try {
            const result = await api.refineCode(this._repoId, request);

            // Build summary
            let content = `## 🔄 Refinement Result\n\n`;
            content += `**Success:** ${result.success ? '✅ Yes' : '❌ No'}\n`;
            content += `**Iterations:** ${result.total_iterations}/4\n\n`;

            // Iteration log
            for (const it of result.iteration_log) {
                const icon = it.tests_passed ? '✅' : '❌';
                content += `**Iteration ${it.iteration}:** ${icon} — ${it.refinement_action || 'N/A'}\n`;
            }

            content += `\n### Final Test Output\n\`\`\`\n${(result.final_test_output || '').slice(0, 1000)}\n\`\`\`\n`;

            if (result.final_code) {
                content += `\n### Final Code\n\`\`\`python\n${result.final_code}\n\`\`\`\n`;
            }

            if (result.final_tests) {
                content += `\n### Final Tests\n\`\`\`python\n${result.final_tests}\n\`\`\`\n`;
            }

            this.postMessage({
                type: 'MESSAGE_APPEND',
                role: 'assistant',
                content,
            });
        } catch (error) {
            const message = error instanceof Error ? error.message : 'Refinement failed';
            this.postMessage({
                type: 'MESSAGE_APPEND',
                role: 'assistant',
                content: formatSafeRefusal('Refinement failed.', ['Check backend logs', 'Ensure pytest is installed']),
            });
            this.postMessage({ type: 'ERROR_TOAST', message });
        } finally {
            this.postMessage({ type: 'LOADING', loading: false });
        }
    }

    /**
     * Handle apply changes — directly writes files (like Copilot)
     */
    private async _handleApplyChanges(): Promise<void> {
        if (this._lastGeneratedDiffs.length === 0) {
            this.postMessage({ type: 'ERROR_TOAST', message: 'No changes to apply.' });
            return;
        }

        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) {
            this.postMessage({ type: 'ERROR_TOAST', message: 'No workspace open.' });
            return;
        }
        const rootUri = workspaceFolders[0].uri;

        try {
            const applied: string[] = [];

            for (const diff of this._lastGeneratedDiffs) {
                const cleanPath = diff.file_path.replace(/^[\/\\]/, '');
                const targetUri = path.isAbsolute(diff.file_path)
                    ? vscode.Uri.file(diff.file_path)
                    : vscode.Uri.joinPath(rootUri, cleanPath);

                const content = diff.code || diff.content;
                if (!content) {
                    continue;
                }

                // Write file directly (create or overwrite)
                await vscode.workspace.fs.writeFile(targetUri, Buffer.from(content, 'utf-8'));

                // Open file in editor
                const doc = await vscode.workspace.openTextDocument(targetUri);
                await vscode.window.showTextDocument(doc, { preview: false });

                // Count lines for summary
                const lineCount = content.split('\n').length;
                applied.push(`${cleanPath} (${lineCount} lines)`);
            }

            if (applied.length > 0) {
                // Show compact notification
                const summary = applied.join(', ');
                const msg = `✅ Applied: ${summary}`;
                this.postMessage({
                    type: 'MESSAGE_APPEND',
                    role: 'system',
                    content: msg,
                });
                vscode.window.showInformationMessage(
                    `✅ Applied changes to ${applied.length} file(s). Press Ctrl+Z in editor to undo.`
                );
            }

        } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to apply changes';
            this.postMessage({ type: 'ERROR_TOAST', message });
        }
    }

    /**
     * Handle cancel request — aborts in-flight API calls
     */
    private _handleCancelRequest(): void {
        if (this._abortController) {
            this._abortController.abort();
            this._abortController = undefined;
        }
        this.postMessage({ type: 'LOADING', loading: false });
        this.postMessage({
            type: 'MESSAGE_APPEND',
            role: 'system',
            content: '⏹️ Request cancelled.',
        });
    }

    /**
     * Accept a single file — write it to disk and open in editor
     */
    private async _handleAcceptFile(filePath: string): Promise<void> {
        const diff = this._lastGeneratedDiffs.find((d: any) => d.file_path === filePath);
        if (!diff) {
            this.postMessage({ type: 'ERROR_TOAST', message: `File not found: ${filePath}` });
            return;
        }

        const content = diff.code || diff.content || diff.diff;
        if (!content) {
            this.postMessage({ type: 'ERROR_TOAST', message: `No content to apply for ${filePath}` });
            return;
        }

        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) {
            this.postMessage({ type: 'ERROR_TOAST', message: 'No workspace open.' });
            return;
        }
        const rootUri = workspaceFolders[0].uri;
        const cleanPath = filePath.replace(/^[\/\\]/, '');
        const targetUri = path.isAbsolute(filePath)
            ? vscode.Uri.file(filePath)
            : vscode.Uri.joinPath(rootUri, cleanPath);

        try {
            await vscode.workspace.fs.writeFile(targetUri, Buffer.from(content, 'utf-8'));
            const doc = await vscode.workspace.openTextDocument(targetUri);
            await vscode.window.showTextDocument(doc, { preview: false });

            const lineCount = content.split('\n').length;
            this.postMessage({
                type: 'MESSAGE_APPEND',
                role: 'system',
                content: `✅ Applied \`${cleanPath}\` (${lineCount} lines). Ctrl+Z to undo.`,
            });
        } catch (error) {
            const msg = error instanceof Error ? error.message : 'Write failed';
            this.postMessage({ type: 'ERROR_TOAST', message: msg });
        }
    }

    /**
     * Reject a single file — skip it with a notification
     */
    private _handleRejectFile(filePath: string): void {
        const cleanPath = filePath.replace(/^[\/\\]/, '');
        this.postMessage({
            type: 'MESSAGE_APPEND',
            role: 'system',
            content: `❌ Skipped \`${cleanPath}\``,
        });
    }

    /**
     * Accept all files at once
     */
    private async _handleAcceptAll(): Promise<void> {
        if (this._lastGeneratedDiffs.length === 0) {
            this.postMessage({ type: 'ERROR_TOAST', message: 'No changes to apply.' });
            return;
        }

        for (const diff of this._lastGeneratedDiffs) {
            await this._handleAcceptFile(diff.file_path);
        }

        vscode.window.showInformationMessage(
            `✅ Applied changes to ${this._lastGeneratedDiffs.length} file(s). Press Ctrl+Z in editor to undo.`
        );
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
            // Always use local workspace path (no GitHub cloning)
            const repoUrl = workspacePath;

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
          <button id="btn-cancel" class="cancel-btn" style="display:none" title="Cancel request">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
              <rect x="3" y="3" width="10" height="10" rx="2" fill="currentColor"/>
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
