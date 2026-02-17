/**
 * RepoPilot VS Code Extension - Entry Point
 * 
 * Extension activation, auto-indexing, and registration.
 */

import * as vscode from 'vscode';
import { ChatPanelProvider } from './chatPanel';
import { registerCommands } from './commands';
import { registerCodeActions } from './codeActions';
import { initStorage, getStoredRepoId, getStoredState, saveRepoInfo } from './storage';
import * as api from './apiClient';
import { StatusBarManager } from './statusBar';
import { showErrorWithActions, withProgress } from './errorHandler';
import { RepoPilotCodeLensProvider } from './codeLens';

let chatPanelProvider: ChatPanelProvider;
let statusBar: StatusBarManager;
let healthCheckInterval: NodeJS.Timeout | undefined;
let isAutoIndexing = false;

/**
 * Extension activation
 */
export async function activate(context: vscode.ExtensionContext): Promise<void> {
    console.log('RepoPilot AI extension activating...');

    // Initialize storage
    initStorage(context);

    // Create status bar
    statusBar = new StatusBarManager();
    context.subscriptions.push(statusBar);

    // Create chat panel provider
    chatPanelProvider = new ChatPanelProvider(context, statusBar);

    // Register webview provider
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(
            ChatPanelProvider.viewType,
            chatPanelProvider,
            {
                webviewOptions: {
                    retainContextWhenHidden: true,
                },
            }
        )
    );

    // Register content provider for Copilot-style diff previews
    context.subscriptions.push(
        vscode.workspace.registerTextDocumentContentProvider('repopilot-proposed', {
            provideTextDocumentContent(uri: vscode.Uri): string {
                const key = uri.path.replace(/^\//, '');
                return ChatPanelProvider.proposedContents.get(key) || '';
            }
        })
    );

    // Register commands
    registerCommands(context, chatPanelProvider);
    registerCodeActions(context, chatPanelProvider);

    // Register Code Lens
    context.subscriptions.push(
        vscode.languages.registerCodeLensProvider(
            [{ scheme: 'file', language: 'python' }, { scheme: 'file', language: 'typescript' }, { scheme: 'file', language: 'javascript' }],
            new RepoPilotCodeLensProvider()
        )
    );

    // Check backend health and auto-index (non-blocking so extension host starts fast)
    initializeExtension().catch(err => {
        console.error('RepoPilot initialization error:', err);
    });

    // Start health check interval (every 30s)
    startHealthCheckInterval();

    console.log('RepoPilot AI extension activated');
}

/**
 * Start background health check interval
 */
function startHealthCheckInterval() {
    if (healthCheckInterval) {
        clearInterval(healthCheckInterval);
    }

    healthCheckInterval = setInterval(async () => {
        // Don't overwrite status while indexing is in progress
        const panelStatus = chatPanelProvider.getCurrentStatus();
        if (isAutoIndexing || panelStatus === 'loading' || panelStatus === 'indexing') {
            return;
        }

        const isHealthy = await api.isBackendHealthy();
        if (isHealthy) {
            const storedState = getStoredState();
            if (storedState.repoId) {
                chatPanelProvider.setRepoInfo(storedState.repoId, storedState.repoName || 'Ready');
                chatPanelProvider.updateStatus('ready', storedState.repoId, storedState.repoName || 'Ready');
                statusBar.update('ready', storedState.repoName || 'Ready');
            } else {
                chatPanelProvider.updateStatus('not_indexed');
                statusBar.update('not_indexed');
            }
        } else {
            chatPanelProvider.updateStatus('not_connected');
            statusBar.update('not_connected');
        }
    }, 30000); // 30 seconds
}

/**
 * Initialize extension: check health and auto-index
 */
async function initializeExtension(): Promise<void> {
    // Check backend health with retries
    let isHealthy = await api.isBackendHealthy();

    // Retry up to 3 times with 5s delay (backend may still be starting)
    if (!isHealthy) {
        for (let attempt = 1; attempt <= 3; attempt++) {
            console.log(`RepoPilot: Backend not ready, retry ${attempt}/3 in 5s...`);
            chatPanelProvider.updateStatus('not_connected');
            statusBar.update('not_connected');
            await new Promise(resolve => setTimeout(resolve, 5000));
            isHealthy = await api.isBackendHealthy();
            if (isHealthy) { break; }
        }
    }

    if (!isHealthy) {
        const backendUrl = vscode.workspace
            .getConfiguration('repopilot')
            .get<string>('backendUrl', 'http://localhost:8000');

        chatPanelProvider.updateStatus('not_connected');
        statusBar.update('not_connected');
        vscode.window.showWarningMessage(
            `RepoPilot backend is not reachable at ${backendUrl}. Start it with: RepoPilot: Start Backend`,
            'Start Backend',
            'Dismiss'
        ).then(action => {
            if (action === 'Start Backend') {
                vscode.commands.executeCommand('repopilot.startBackend');
            }
        });
        return;
    }

    // Check for workspace
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders || workspaceFolders.length === 0) {
        chatPanelProvider.updateStatus('not_indexed');
        statusBar.update('not_indexed');
        return;
    }

    const workspacePath = workspaceFolders[0].uri.fsPath;

    // Check for existing stored repo
    const storedState = getStoredState();
    if (storedState.workspacePath === workspacePath && storedState.repoId) {
        // Verify the repo still exists in backend
        try {
            const status = await api.getRepoStatus(storedState.repoId);
            if (status.indexed) {
                chatPanelProvider.setRepoInfo(storedState.repoId, storedState.repoName || 'Unknown');
                chatPanelProvider.updateStatus('ready', storedState.repoId, storedState.repoName);
                console.log(`Restored repo: ${storedState.repoName} (${storedState.repoId})`);
                return;
            }
        } catch {
            // Repo not found, will re-index
        }
    }

    // Don't auto-index — let user click "Index Workspace" when ready
    // This avoids race conditions with history replay and incomplete indexing
    chatPanelProvider.updateStatus('not_indexed');
    statusBar.update('not_indexed');
}

/**
 * Auto-index the current workspace
 */
async function autoIndexWorkspace(workspacePath: string): Promise<void> {
    isAutoIndexing = true;
    chatPanelProvider.updateStatus('loading');
    statusBar.update('loading');

    try {
        // Always use local workspace path — no GitHub cloning needed
        // The codebase is already on disk, cloning wastes ~30s
        const repoUrl = workspacePath;

        // Load and index -- update status bar with progress
        const result = await api.loadAndIndexRepo(repoUrl, (progressMsg) => {
            console.log(`Indexing progress: ${progressMsg}`);
            if (progressMsg.startsWith('Indexing')) {
                chatPanelProvider.updateStatus('indexing');
                statusBar.update('indexing');
            } else if (progressMsg.startsWith('Loading')) {
                chatPanelProvider.updateStatus('loading');
                statusBar.update('loading');
            }
        });

        // Save state
        await saveRepoInfo(result.repoId, result.repoName, workspacePath);
        chatPanelProvider.setRepoInfo(result.repoId, result.repoName);
        chatPanelProvider.updateStatus('ready', result.repoId, result.repoName);
        statusBar.update('ready', result.repoName);
        isAutoIndexing = false;

        vscode.window.showInformationMessage(
            `RepoPilot: Indexed ${result.repoName} successfully!`
        );
    } catch (error) {
        const message = error instanceof Error ? error.message : 'Auto-indexing failed';
        console.error('Auto-indexing failed:', message);

        // Distinguish between connectivity errors and actual indexing errors
        const isNetworkError = error instanceof api.ApiError && error.isNetworkError;
        if (isNetworkError) {
            chatPanelProvider.updateStatus('not_connected');
            statusBar.update('not_connected');
        } else {
            chatPanelProvider.updateStatus('error');
            statusBar.update('error');
        }
        isAutoIndexing = false;

        vscode.window.showWarningMessage(
            `RepoPilot auto-indexing failed: ${message}. Click Index in the chat panel to retry.`
        );
    }
}

/**
 * Extension deactivation
 */
export function deactivate(): void {
    if (healthCheckInterval) {
        clearInterval(healthCheckInterval);
    }
    console.log('RepoPilot AI extension deactivated');
}
