/**
 * RepoPilot VS Code Extension - Status Bar Manager
 * 
 * Manage status bar item showing indexing status and repo info.
 */

import * as vscode from 'vscode';
import { IndexingStatus } from './types';

export class StatusBarManager {
    private statusBarItem: vscode.StatusBarItem;

    constructor() {
        this.statusBarItem = vscode.window.createStatusBarItem(
            vscode.StatusBarAlignment.Right,
            100
        );
        this.statusBarItem.command = 'repopilot.openChat';
        this.statusBarItem.show();
    }

    /**
     * Update status bar with current state
     */
    public update(status: IndexingStatus, repoName?: string, chunkCount?: number): void {
        const icons: Record<IndexingStatus, string> = {
            not_connected: '$(warning)',
            not_indexed: '$(circle-outline)',
            loading: '$(loading~spin)',
            indexing: '$(sync~spin)',
            ready: '$(check)',
            error: '$(error)',
        };

        const labels: Record<IndexingStatus, string> = {
            not_connected: 'Backend Offline',
            not_indexed: 'Not Indexed',
            loading: 'Loading...',
            indexing: 'Indexing...',
            ready: repoName || 'Ready',
            error: 'Error',
        };

        const icon = icons[status];
        let label = labels[status];

        // Add chunk count for ready status
        if (status === 'ready' && chunkCount !== undefined) {
            label += ` (${chunkCount} chunks)`;
        }

        this.statusBarItem.text = `${icon} RepoPilot: ${label}`;

        // Update tooltip
        const tooltips: Record<IndexingStatus, string> = {
            not_connected: 'RepoPilot backend is not running. Click to open chat.',
            not_indexed: 'Workspace not indexed. Click to open chat and index.',
            loading: 'Loading repository...',
            indexing: 'Indexing repository in progress...',
            ready: `Repository ${repoName || 'ready'}. Click to open chat.`,
            error: 'An error occurred. Click for details.',
        };

        this.statusBarItem.tooltip = tooltips[status];

        // Update color
        const colors: Partial<Record<IndexingStatus, string>> = {
            not_connected: 'statusBarItem.errorBackground',
            error: 'statusBarItem.errorBackground',
            ready: undefined, // Default color
        };

        this.statusBarItem.backgroundColor = colors[status]
            ? new vscode.ThemeColor(colors[status]!)
            : undefined;
    }

    /**
     * Hide status bar item
     */
    public hide(): void {
        this.statusBarItem.hide();
    }

    /**
     * Show status bar item
     */
    public show(): void {
        this.statusBarItem.show();
    }

    /**
     * Dispose of status bar item
     */
    public dispose(): void {
        this.statusBarItem.dispose();
    }
}
