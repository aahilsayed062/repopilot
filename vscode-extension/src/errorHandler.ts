/**
 * RepoPilot VS Code Extension - Error Handler
 * 
 * User-friendly error message translations and handling.
 */

import * as vscode from 'vscode';
import { ApiError } from './apiClient';

/**
 * Translate API errors into user-friendly messages
 */
export function formatErrorMessage(error: unknown): string {
    if (error instanceof ApiError) {
        // Network errors
        if (error.isNetworkError) {
            return 'Cannot connect to RepoPilot backend. Make sure it\'s running at the configured URL.';
        }

        // HTTP status code errors
        switch (error.statusCode) {
            case 429:
                // Rate limit - extract wait time if available
                const waitTimeMatch = error.message.match(/(\d+)m(\d+)/);
                if (waitTimeMatch) {
                    const minutes = parseInt(waitTimeMatch[1]);
                    return `Rate limit exceeded. Please wait ${minutes} minutes before trying again.`;
                }
                return 'Rate limit exceeded. Please wait a few minutes and try again.';

            case 404:
                return 'Repository not found. Try re-indexing your workspace.';

            case 413:
                return 'Repository too large. Consider reducing the repository size or adjusting limits.';

            case 500:
                return `Backend error: ${error.message}. Check backend logs for details.`;

            case 503:
                return 'Backend service unavailable. Please restart the backend.';

            default:
                return `Error (${error.statusCode}): ${error.message}`;
        }
    }

    if (error instanceof Error) {
        return error.message;
    }

    return 'An unknown error occurred.';
}

/**
 * Show error with actionable suggestions
 */
export function showErrorWithActions(error: unknown): void {
    const message = formatErrorMessage(error);

    if (error instanceof ApiError) {
        if (error.isNetworkError) {
            vscode.window.showErrorMessage(
                message,
                'Open Settings',
                'Start Backend'
            ).then(action => {
                if (action === 'Open Settings') {
                    vscode.commands.executeCommand('workbench.action.openSettings', 'repopilot.backendUrl');
                } else if (action === 'Start Backend') {
                    vscode.commands.executeCommand('repopilot.startBackend');
                }
            });
            return;
        }

        if (error.statusCode === 429) {
            vscode.window.showWarningMessage(message, 'Dismiss');
            return;
        }

        if (error.statusCode === 404) {
            vscode.window.showErrorMessage(
                message,
                'Re-Index'
            ).then(action => {
                if (action === 'Re-Index') {
                    vscode.commands.executeCommand('repopilot.indexWorkspace');
                }
            });
            return;
        }
    }

    // Default error
    vscode.window.showErrorMessage(message);
}

/**
 * Show progress with cancellation support
 */
export async function withProgress<T>(
    title: string,
    task: (progress: vscode.Progress<{ message?: string; increment?: number }>) => Promise<T>,
    cancellable: boolean = false
): Promise<T | undefined> {
    return vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title,
            cancellable,
        },
        task
    );
}

/**
 * Show info message with optional actions
 */
export function showInfo(message: string, ...actions: string[]): Thenable<string | undefined> {
    return vscode.window.showInformationMessage(message, ...actions);
}

/**
 * Show warning message with optional actions
 */
export function showWarning(message: string, ...actions: string[]): Thenable<string | undefined> {
    return vscode.window.showWarningMessage(message, ...actions);
}
