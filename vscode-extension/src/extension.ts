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
    chatPanelProvider = new ChatPanelProvider(context);

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

    // Check backend health and auto-index
    await initializeExtension();


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
        const isHealthy = await api.isBackendHealthy();
        if (isHealthy) {
            // If it was offline, this will recover it
            const storedState = getStoredState();
            if (storedState.repoId) {
                // We don't want to spam status updates, so only update if needed or blindly
                // But statusBar.update handles duplicate states gracefully-ish
                // better to check current state from chatPanelProvider access if possible
                // For now, just a quiet check. If it comes back online, we could trigger validatin.
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
    // Check backend health
    const isHealthy = await api.isBackendHealthy();

    if (!isHealthy) {
        chatPanelProvider.updateStatus('not_connected');
        statusBar.update('not_connected');
        vscode.window.showWarningMessage(
            'RepoPilot backend is not running. Start it with: python backend/run.py',
            'Dismiss'
        );
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

    // Check if auto-index is enabled
    const config = vscode.workspace.getConfiguration('repopilot');
    const autoIndex = config.get<boolean>('autoIndexOnOpen', true);

    if (!autoIndex) {
        chatPanelProvider.updateStatus('not_indexed');
        statusBar.update('not_indexed');
        return;
    }

    // Auto-index the workspace
    await autoIndexWorkspace(workspacePath);
}

/**
 * Auto-index the current workspace
 */
async function autoIndexWorkspace(workspacePath: string): Promise<void> {
    chatPanelProvider.updateStatus('loading');
    statusBar.update('loading');

    try {
        // Try to get git remote origin
        let repoUrl = workspacePath;
        try {
            const gitExtension = vscode.extensions.getExtension('vscode.git');
            if (gitExtension && gitExtension.isActive) {
                const git = gitExtension.exports.getAPI(1);
                if (git.repositories.length > 0) {
                    const repo = git.repositories[0];
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

        // Load and index
        chatPanelProvider.updateStatus('indexing');

        const result = await api.loadAndIndexRepo(repoUrl, (status) => {
            console.log(`Indexing progress: ${status}`);
        });

        // Save state
        await saveRepoInfo(result.repoId, result.repoName, workspacePath);
        chatPanelProvider.setRepoInfo(result.repoId, result.repoName);
        chatPanelProvider.updateStatus('ready', result.repoId, result.repoName);

        vscode.window.showInformationMessage(
            `RepoPilot: Indexed ${result.repoName} successfully!`
        );
    } catch (error) {
        const message = error instanceof Error ? error.message : 'Auto-indexing failed';
        console.error('Auto-indexing failed:', message);
        chatPanelProvider.updateStatus('error');

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
