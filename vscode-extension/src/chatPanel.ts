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

            case 'EXPORT_CHAT':
                await this._handleExportFromHistory();
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

            case 'PYTEST_DEMO':
                await this._handlePytestDemo();
                break;

            default:
                console.warn(`[RepoPilot] Unknown webview message type: ${(message as any).type}`);
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

        // Save previous diffs so follow-up requests can reference the last generated code
        const previousDiffs = [...this._lastGeneratedDiffs];

        // Clear stale diffs/tests from previous requests to prevent
        // Accept buttons applying code from an old generation
        this._lastGeneratedDiffs = [];
        this._lastGeneratedTests = '';

        try {
            // Include any pending file context
            let questionWithContext = question;
            const contextFileHints: string[] = [];
            if (this._pendingFileContext) {
                questionWithContext = question + '\n\n[Referenced Files]\n' + this._pendingFileContext;
                this._pendingFileContext = '';
            }

            // If the user is asking to fix/correct/update code and we have previous diffs,
            // inject the previously generated code as context so the LLM updates the SAME file
            const FOLLOWUP_KEYWORDS = /\b(fix|correct|handle|improve|update|change|modify|error|bug|issue|wrong|mistake)\b/i;
            if (previousDiffs.length > 0 && FOLLOWUP_KEYWORDS.test(question)) {
                const prevContext = previousDiffs.map((d: any) => {
                    const code = d.code || d.content || '';
                    return `[Previously Generated File: ${d.file_path}]\n${code}`;
                }).join('\n\n');
                questionWithContext = question + '\n\n[Existing File Content]\n' + prevContext;
            }

            // Build chat_history from _history for context continuity
            const chatHistory = this._history
                .filter(m => m.type === 'MESSAGE_APPEND' && (m.role === 'user' || m.role === 'assistant'))
                .slice(-10)  // last 5 turns (user+assistant pairs)
                .map(m => ({ role: (m as any).role as string, content: ((m as any).content as string || '').slice(0, 500) }));

            // Heuristic: simple explain/question queries → stream for better UX
            // Also treat follow-ups with previous code as GENERATE (not streaming explain)
            const GEN_KEYWORDS = /\b(add|create|modify|implement|generate|write|build|fix|refactor|change|update|delete|remove|rename|move|extract|convert|replace|insert|make|correct|handle|improve|rewrite|optimize|sort|order)\b/i;
            // "Proceed", "yes", "go ahead" etc. after a code plan → should trigger GENERATE, not EXPLAIN
            const PROCEED_KEYWORDS = /^\s*(proceed|yes|go ahead|do it|go|continue|ok|okay|sure|start|begin|make it|let'?s go|confirm|approved?)\s*\.?\s*$/i;
            const PROCEED_PHRASES = /\b(proceed|go ahead|make the code|do it|start coding|write the code|generate the code|create the code|make the file|write it|create it)\b/i;
            const hasRecentCode = previousDiffs.length > 0 && FOLLOWUP_KEYWORDS.test(question);
            // Check if chat history contains a previous plan/generation context
            const historyHasCodeContext = chatHistory.some(h =>
                /\b(implement|generate|create|binary search|merge sort|quick sort|linked list|code|\.cpp|\.py|\.java|\.js|\.ts)\b/i.test(h.content)
            );
            const isProceedAfterPlan = (PROCEED_KEYWORDS.test(question) || PROCEED_PHRASES.test(question)) && historyHasCodeContext;
            const isLikelyExplain = !GEN_KEYWORDS.test(question) && !hasRecentCode && !isProceedAfterPlan;

            if (isLikelyExplain) {
                // Stream token-by-token for explain-only queries
                this.postMessage({
                    type: 'MESSAGE_APPEND',
                    role: 'assistant',
                    content: '> 💬 **Route:** EXPLAIN (streaming)\n\n',
                });

                let accumulated = '> 💬 **Route:** EXPLAIN (streaming)\n\n';
                for await (const token of api.streamChat(this._repoId, questionWithContext, chatHistory)) {
                    if (this._abortController?.signal.aborted) {
                        accumulated += '\n\n> ⏹️ *Response cancelled*';
                        this.postMessage({ type: 'MESSAGE_UPDATE', content: accumulated });
                        break;
                    }
                    accumulated += token;
                    // Strip [S1], [S2] etc. citation markers from streamed text for cleaner display
                    const cleanAccumulated = accumulated.replace(/\s*-?\s*\[S\d+\]/g, '');
                    this.postMessage({ type: 'MESSAGE_UPDATE', content: cleanAccumulated });
                }

                this.postMessage({ type: 'LOADING', loading: false });
                return;
            }

            // Use /chat/smart for dynamic multi-agent routing (Feature 1)
            // When user says "Proceed" after a plan, enrich the query so the router
            // and generator understand this is a code generation request
            if (isProceedAfterPlan) {
                const lastAssistant = chatHistory.filter(h => h.role === 'assistant').pop();
                const lastUser = chatHistory.filter(h => h.role === 'user').pop();
                const contextHint = lastUser?.content || lastAssistant?.content || '';
                questionWithContext = `Generate the code as discussed. Original request: ${contextHint}\nUser confirmation: ${question}`;
            }

            const smartResult = await api.smartChat(
                this._repoId, questionWithContext, chatHistory, contextFileHints,
                this._abortController?.signal
            );

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

            // Main answer — strip [S1], [S2] etc. citation markers for clean display
            const cleanAnswer = (smartResult.answer || '').replace(/\s*-?\s*\[S\d+\]/g, '');
            content += cleanAnswer;

            // If generation results exist, format them
            if (smartResult.generate && typeof smartResult.generate === 'object' && !('error' in smartResult.generate)) {
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
                    // Validate that improved code is actual code, not placeholder text
                    const validImproved = smartResult.evaluation_improved_code.filter((ic: any) => {
                        const code = (ic.code || '').trim();
                        if (code.length < 20) { return false; }
                        const placeholders = ['full improved file content', 'improved file content',
                            'actual fixed code', 'your improved code here'];
                        if (placeholders.includes(code.toLowerCase())) { return false; }
                        // Must contain code-like characters
                        return /[{(=;]|\bdef\b|\bclass\b|\bimport\b|#include/.test(code);
                    });
                    if (validImproved.length > 0) {
                        // Use original file_path from generated diffs when possible
                        // (controller may return different/wrong file paths)
                        const originalPaths = this._lastGeneratedDiffs.map((d: any) => d.file_path);
                        this._lastGeneratedDiffs = validImproved.map((ic: any, idx: number) => ({
                            file_path: originalPaths[idx] || ic.file_path,
                            content: ic.code,
                            code: ic.code,
                            diff: ic.code,
                        }));
                        content += `\n\n> ✨ **Merged feedback applied** — Accept buttons now use the improved code.`;
                    }
                }
            }

            // Show initial content with loading indicator for impact/eval
            const baseContent = content;
            if (this._lastGeneratedDiffs.length > 0 && this._repoId) {
                content += `\n\n---\n⏳ **Analyzing impact & evaluating code...**`;
            }

            // Build buttons
            const buttons: { label: string; action: string }[] = [];
            if (this._lastGeneratedDiffs.length > 0) {
                buttons.push({ label: '✅ Accept All', action: 'ACCEPT_ALL' });
            }
            if (this._isValidTestCode(this._lastGeneratedTests)) {
                buttons.push({ label: '▶️ Run Tests', action: 'RUN_TESTS' });
            } else if (this._lastGeneratedDiffs.length > 0) {
                buttons.push({ label: '🧪 Generate Tests', action: 'GENERATE_TESTS' });
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

            // Show inline diff preview in editor (Copilot-style green/red lines)
            if (this._lastGeneratedDiffs.length > 0) {
                await this._showInlineDiffPreview(this._lastGeneratedDiffs);
            }

            // Impact analysis on generated code (runs after message is shown)
            if (this._lastGeneratedDiffs.length > 0 && this._repoId) {
                let finalContent = baseContent;
                try {
                    const changedFiles = this._lastGeneratedDiffs.map((d: any) => d.file_path);
                    const codeChanges = this._lastGeneratedDiffs
                        .map((d: any) => `--- ${d.file_path} ---\n${d.diff || ''}`)
                        .join('\n');
                    const impact = await api.analyzeImpact(this._repoId, changedFiles, codeChanges);
                    const impactFormatted = formatImpactReport(impact);
                    finalContent += `\n\n---\n${impactFormatted}`;
                } catch {
                    // Impact analysis is non-critical
                }
                // Remove loading placeholder with final content
                this.postMessage({ type: 'MESSAGE_UPDATE', content: finalContent });
            }

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

    /** Check if test content looks like actual runnable Python code */
    private _isValidTestCode(code: string): boolean {
        if (!code || !code.trim()) { return false; }
        return /\b(def |import |class |assert )/.test(code.trim());
    }

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

        // Clear stale diffs/tests from previous requests
        this._lastGeneratedDiffs = [];
        this._lastGeneratedTests = '';

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
            if (this._isValidTestCode(this._lastGeneratedTests)) {
                buttons.push({ label: '▶️ Run Tests', action: 'RUN_TESTS' });
            } else if (this._lastGeneratedDiffs.length > 0) {
                buttons.push({ label: '🧪 Generate Tests', action: 'GENERATE_TESTS' });
            }

            // Show content immediately with loading indicator
            let displayContent = formatted;
            if (this._lastGeneratedDiffs.length > 0 && this._repoId) {
                displayContent += '\n\n---\n⏳ **Analyzing impact & evaluating code...**';
            }

            this.postMessage({
                type: 'MESSAGE_APPEND',
                role: 'assistant',
                content: displayContent,
                buttons: buttons.length > 0 ? buttons : undefined
            });

            // Show inline diff preview in editor (Copilot-style)
            if (this._lastGeneratedDiffs.length > 0) {
                await this._showInlineDiffPreview(this._lastGeneratedDiffs);
            }

            // Feature 4: Auto-run Impact Analysis (compact inline)
            if (this._lastGeneratedDiffs.length > 0 && this._repoId) {
                let updatedContent = formatted;
                try {
                    const changedFiles = this._lastGeneratedDiffs.map((d: any) => d.file_path);
                    const codeChanges = this._lastGeneratedDiffs
                        .map((d: any) => `--- ${d.file_path} ---\n${d.diff || ''}`)
                        .join('\n');
                    const impact = await api.analyzeImpact(this._repoId, changedFiles, codeChanges);
                    const impactFormatted = formatImpactReport(impact);
                    updatedContent += '\n\n---\n' + impactFormatted;
                } catch (impactErr) {
                    console.warn('Impact analysis failed (non-critical):', impactErr);
                }

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

                // Replace loading indicator with final results
                this.postMessage({
                    type: 'MESSAGE_UPDATE',
                    content: updatedContent,
                });
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

            // Populate _lastGeneratedDiffs so Accept/Apply buttons work
            if (result.final_code) {
                this._lastGeneratedDiffs = [{
                    file_path: 'refined_code.py',
                    content: result.final_code,
                    explanation: 'PyTest-driven refined code from iterative loop',
                }];
            }
            if (result.final_tests) {
                this._lastGeneratedDiffs.push({
                    file_path: 'test_refined.py',
                    content: result.final_tests,
                    explanation: 'Generated pytest tests for refined code',
                });
            }

            this.postMessage({
                type: 'MESSAGE_APPEND',
                role: 'assistant',
                content,
                buttons: [
                    { label: '✅ Apply Refined Code', action: 'APPLY_CHANGES' },
                    { label: '🧪 Run Tests', action: 'RUN_TESTS' },
                ],
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
     * Handle PyTest Demo — mock simulation showing the refinement loop in action
     * Shows: buggy code → pytest failure → LLM fix → tests pass
     */
    private async _handlePytestDemo(): Promise<void> {
        this.postMessage({ type: 'LOADING', loading: true });

        // Simulate the refinement loop with timed steps
        const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

        try {
            // Step 1: Show the "buggy" code
            this.postMessage({
                type: 'MESSAGE_APPEND',
                role: 'assistant',
                content: `## 🧪 PyTest Refinement Demo\n\nThis demonstrates how RepoPilot's **iterative refinement loop** works. We'll walk through a simulated cycle:\n\n> **Buggy Code → PyTest Failure → LLM Fix → Tests Pass**\n\n---\n\n### Step 1: Initial (Buggy) Code\n\n\`\`\`python\n# calculator.py\ndef add(a, b):\n    return a - b  # BUG: subtraction instead of addition\n\ndef multiply(a, b):\n    return a + b  # BUG: addition instead of multiplication\n\ndef divide(a, b):\n    return a / b  # BUG: no zero-division check\n\`\`\``,
            });

            await delay(1500);

            // Step 2: Show generated pytest and failure
            this.postMessage({
                type: 'MESSAGE_UPDATE',
                content: `## 🧪 PyTest Refinement Demo\n\nThis demonstrates how RepoPilot's **iterative refinement loop** works.\n\n> **Buggy Code → PyTest Failure → LLM Fix → Tests Pass**\n\n---\n\n### Step 1: Initial (Buggy) Code\n\n\`\`\`python\n# calculator.py\ndef add(a, b):\n    return a - b  # BUG: subtraction instead of addition\n\ndef multiply(a, b):\n    return a + b  # BUG: addition instead of multiplication\n\ndef divide(a, b):\n    return a / b  # BUG: no zero-division check\n\`\`\`\n\n### Step 2: Generated PyTests\n\n\`\`\`python\n# test_calculator.py\nimport pytest\nfrom calculator import add, multiply, divide\n\ndef test_add():\n    assert add(2, 3) == 5\n    assert add(-1, 1) == 0\n    assert add(0, 0) == 0\n\ndef test_multiply():\n    assert multiply(3, 4) == 12\n    assert multiply(-2, 5) == -10\n    assert multiply(0, 100) == 0\n\ndef test_divide():\n    assert divide(10, 2) == 5.0\n    assert divide(7, 2) == 3.5\n\ndef test_divide_by_zero():\n    with pytest.raises(ValueError):\n        divide(1, 0)\n\`\`\`\n\n### ❌ Iteration 1: PyTest Output (3 FAILED)\n\n\`\`\`\n$ pytest test_calculator.py -v\n\ntest_calculator.py::test_add FAILED\n  assert add(2, 3) == 5  →  got -1\ntest_calculator.py::test_multiply FAILED\n  assert multiply(3, 4) == 12  →  got 7\ntest_calculator.py::test_divide_by_zero FAILED\n  ZeroDivisionError: division by zero\n\nFAILED 3  |  PASSED 1\n\`\`\``,
            });

            await delay(2000);

            // Step 3: Show LLM fix
            this.postMessage({
                type: 'MESSAGE_UPDATE',
                content: `## 🧪 PyTest Refinement Demo\n\nThis demonstrates how RepoPilot's **iterative refinement loop** works.\n\n> **Buggy Code → PyTest Failure → LLM Fix → Tests Pass**\n\n---\n\n### Step 1: Initial (Buggy) Code\n\n\`\`\`python\n# calculator.py (original — 3 bugs)\ndef add(a, b):\n    return a - b  # BUG\ndef multiply(a, b):\n    return a + b  # BUG\ndef divide(a, b):\n    return a / b  # BUG: no zero check\n\`\`\`\n\n### ❌ Iteration 1: 3 tests failed\n\n### Step 3: 🤖 LLM Analyzes Failures & Fixes Code\n\nThe LLM reads the pytest output and applies targeted fixes:\n\n\`\`\`python\n# calculator.py (FIXED by LLM — iteration 2)\ndef add(a, b):\n    return a + b  # FIXED: changed - to +\n\ndef multiply(a, b):\n    return a * b  # FIXED: changed + to *\n\ndef divide(a, b):\n    if b == 0:\n        raise ValueError("Cannot divide by zero")\n    return a / b  # FIXED: added zero-division guard\n\`\`\`\n\n### ✅ Iteration 2: PyTest Output (ALL PASSED)\n\n\`\`\`\n$ pytest test_calculator.py -v\n\ntest_calculator.py::test_add PASSED\ntest_calculator.py::test_multiply PASSED\ntest_calculator.py::test_divide PASSED\ntest_calculator.py::test_divide_by_zero PASSED\n\nPASSED 4  |  FAILED 0  ✅\n\`\`\`\n\n---\n\n### 📊 Refinement Summary\n\n**Success:** ✅ Yes\n**Iterations:** 2/4\n**Bugs Fixed:**  3 (operator errors + missing guard)\n\n| Iteration | Status | Action |\n|-----------|--------|--------|\n| 1 | ❌ 3 failed | Detected: wrong operators, missing guard |\n| 2 | ✅ All pass | Fixed: \`-→+\`, \`+→*\`, added zero check |\n\n> This is how Feature 2 (Iterative PyTest Refinement) works in production. Use \`/refine <request>\` with a real codebase to try it live!`,
            });

            // Populate diffs so the Apply button works with the demo code
            this._lastGeneratedDiffs = [
                {
                    file_path: 'calculator.py',
                    content: `def add(a, b):\n    return a + b\n\ndef multiply(a, b):\n    return a * b\n\ndef divide(a, b):\n    if b == 0:\n        raise ValueError("Cannot divide by zero")\n    return a / b\n`,
                    explanation: 'Fixed calculator: corrected operators and added zero-division guard',
                },
                {
                    file_path: 'test_calculator.py',
                    content: `import pytest\nfrom calculator import add, multiply, divide\n\ndef test_add():\n    assert add(2, 3) == 5\n    assert add(-1, 1) == 0\n    assert add(0, 0) == 0\n\ndef test_multiply():\n    assert multiply(3, 4) == 12\n    assert multiply(-2, 5) == -10\n    assert multiply(0, 100) == 0\n\ndef test_divide():\n    assert divide(10, 2) == 5.0\n    assert divide(7, 2) == 3.5\n\ndef test_divide_by_zero():\n    with pytest.raises(ValueError):\n        divide(1, 0)\n`,
                    explanation: 'Generated pytest test suite for calculator',
                },
            ];

        } catch (error) {
            this.postMessage({
                type: 'ERROR_TOAST',
                message: 'PyTest demo simulation encountered an error.',
            });
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
     * Show Copilot-style inline diff preview in the editor.
     * Opens a diff editor for each file so the user can see green/red lines.
     */
    private async _showInlineDiffPreview(diffs: any[]): Promise<void> {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) { return; }
        const rootUri = workspaceFolders[0].uri;

        for (const diff of diffs) {
            let newContent = diff.code || diff.content;
            if (!newContent) { continue; }

            // Strip markdown code fences if LLM wrapped the code
            newContent = newContent.replace(/^```[a-zA-Z]*\n?/, '').replace(/\n?```\s*$/, '').trim();

            const cleanPath = diff.file_path.replace(/^[\/\\]/, '');
            const targetUri = path.isAbsolute(diff.file_path)
                ? vscode.Uri.file(diff.file_path)
                : vscode.Uri.joinPath(rootUri, cleanPath);

            try {
                // Store proposed content for the content provider
                ChatPanelProvider.proposedContents.set(cleanPath, newContent);

                // Build URI for proposed content (served by RepoPilotProposedContentProvider)
                const proposedUri = vscode.Uri.parse(
                    `repopilot-proposed:${cleanPath}`
                );

                // Check if original file exists
                let originalUri = targetUri;
                try {
                    await vscode.workspace.fs.stat(targetUri);
                } catch {
                    // File doesn't exist yet — use an empty untitled as original
                    ChatPanelProvider.proposedContents.set(`__empty__${cleanPath}`, '');
                    originalUri = vscode.Uri.parse(`repopilot-proposed:__empty__${cleanPath}`);
                }

                // Open the VS Code diff editor (green/red lines)
                const title = `${cleanPath} (RepoPilot Changes)`;
                await vscode.commands.executeCommand('vscode.diff',
                    originalUri,
                    proposedUri,
                    title,
                    { preview: true }
                );
            } catch (err) {
                // Diff preview is non-critical — fall back silently
                console.warn('Inline diff preview failed:', err);
            }
        }
    }

    /**
     * Static map to store proposed file contents for the content provider.
     * Shared between instances so the provider can access it.
     */
    public static proposedContents: Map<string, string> = new Map();

    /**
     * Accept a single file — write it to disk and open in editor
     */
    private async _handleAcceptFile(filePath: string): Promise<void> {
        const diff = this._lastGeneratedDiffs.find((d: any) => d.file_path === filePath);
        if (!diff) {
            this.postMessage({ type: 'ERROR_TOAST', message: `File not found: ${filePath}` });
            return;
        }

        let content = diff.code || diff.content;
        if (!content) {
            // Don't fall back to raw diff text (has +/- prefixes) — that would corrupt the file
            this.postMessage({ type: 'ERROR_TOAST', message: `No applicable code content for ${filePath}. Only a diff is available — cannot apply directly.` });
            return;
        }

        // Strip markdown code fences the LLM may have wrapped around the code
        content = content.replace(/^```[a-zA-Z]*\n?/, '').replace(/\n?```\s*$/, '').trim();

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

        let appliedCount = 0;
        for (const diff of this._lastGeneratedDiffs) {
            try {
                await this._handleAcceptFile(diff.file_path);
                appliedCount++;
            } catch {
                // Individual file errors are handled inside _handleAcceptFile
            }
        }

        if (appliedCount > 0) {
            vscode.window.showInformationMessage(
                `✅ Applied changes to ${appliedCount} file(s). Press Ctrl+Z in editor to undo.`
            );
        } else {
            this.postMessage({ type: 'ERROR_TOAST', message: 'Failed to apply any files.' });
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

        // Validate that the test content looks like actual Python code
        // (small LLMs sometimes echo placeholder text like "test code if applicable")
        const code = this._lastGeneratedTests.trim();
        const looksLikePython = /\b(def |import |class |assert )/.test(code);

        // Detect if test content is actually non-Python code (C++, Java, etc.)
        const looksLikeCpp = /\b(#include|int main|cout|cin|std::)/.test(code);
        const looksLikeJava = /\bpublic\s+static\s+void\s+main/.test(code);
        const looksLikeJs = /\b(require\(|describe\(|it\(|expect\()/.test(code);

        if (looksLikeCpp || looksLikeJava) {
            this.postMessage({
                type: 'MESSAGE_APPEND',
                role: 'system',
                content: '⚠️ Test content appears to be C++/Java code, not Python. '
                    + 'RepoPilot currently supports running PyTest only. '
                    + 'You can copy the test code and run it manually with your language\'s test framework.',
            });
            return;
        }

        if (!looksLikePython && !looksLikeJs) {
            this.postMessage({
                type: 'MESSAGE_APPEND',
                role: 'system',
                content: '⚠️ The generated test content does not appear to be valid Python code. '
                    + 'Try clicking the **🧪 Generate Tests** button to generate proper test cases, '
                    + 'or re-run the `/generate` command.',
            });
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
            // Pass generated code context so test generator knows what to test
            const generatedCode = this._lastGeneratedDiffs.map((d: any) => ({
                file_path: d.file_path || '',
                content: d.new_content || d.content || '',
            })).filter((g: any) => g.file_path && g.content);

            const response = await api.generatePyTest(this._repoId, {
                customRequest: customRequest || 'Generate tests for the main functionality',
                targetFile: generatedCode.length > 0 ? generatedCode[0].file_path : undefined,
                generatedCode: generatedCode.length > 0 ? generatedCode : undefined,
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
            } else if (response.success && !response.tests) {
                // Backend succeeded but no test code was produced
                this.postMessage({
                    type: 'MESSAGE_APPEND',
                    role: 'assistant',
                    content: '⚠️ Test generation completed but no valid test code was produced. '
                        + 'This can happen with small models or non-Python code. '
                        + 'Try asking with `/generate write pytest tests for <specific function>` instead.',
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
     * Public wrapper for indexing (called by commands.ts)
     */
    public async indexWorkspace(): Promise<void> {
        await this._handleIndexWorkspace();
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
     * Export chat from stored history (preserves markdown formatting)
     */
    private async _handleExportFromHistory(): Promise<void> {
        if (this._history.length === 0) {
            this.postMessage({ type: 'ERROR_TOAST', message: 'No chat history to export.' });
            return;
        }

        let markdown = '# RepoPilot Chat Export\n\n';
        markdown += `*Exported: ${new Date().toLocaleString()}*\n\n---\n\n`;

        for (const msg of this._history) {
            if (msg.type !== 'MESSAGE_APPEND') { continue; }
            const role = msg.role === 'user' ? '👤 **User**' : msg.role === 'assistant' ? '🤖 **RepoPilot**' : '⚙️ **System**';
            markdown += `### ${role}\n\n`;
            markdown += (msg.content || '') + '\n\n';

            // Include citations if present
            if (msg.citations && msg.citations.length > 0) {
                markdown += '**Sources:** ';
                markdown += msg.citations.map((c: any) =>
                    `\`${c.file_path}${c.line_range ? ':' + c.line_range : ''}\``
                ).join(', ');
                markdown += '\n\n';
            }

            markdown += '---\n\n';
        }

        await this._handleSaveChat(markdown);
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

        // Notify webview that file context is ready (resolves race condition)
        this._view?.webview.postMessage({ type: 'FILE_CONTEXT_READY' });
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
      <div class="settings-item" id="btn-pytest-demo">
        <svg viewBox="0 0 16 16" fill="currentColor">
          <path d="M5.75 7a.75.75 0 000 1.5h4.5a.75.75 0 000-1.5h-4.5zm-2.5 3a.75.75 0 000 1.5h9.5a.75.75 0 000-1.5h-9.5z"/>
          <path d="M2 1.75C2 .784 2.784 0 3.75 0h8.5C13.216 0 14 .784 14 1.75v12.5A1.75 1.75 0 0112.25 16h-8.5A1.75 1.75 0 012 14.25V1.75zM3.5 1.75v12.5c0 .138.112.25.25.25h8.5a.25.25 0 00.25-.25V1.75a.25.25 0 00-.25-.25h-8.5a.25.25 0 00-.25.25z"/>
        </svg>
        🧪 PyTest Demo
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
