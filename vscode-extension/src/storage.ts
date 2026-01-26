/**
 * RepoPilot VS Code Extension - Storage
 * 
 * Persist repo_id and settings using VS Code globalState.
 */

import * as vscode from 'vscode';
import { StoredState } from './types';

const STORAGE_KEY = 'repopilot.state';
const HISTORY_KEY = 'repopilot.history';

let context: vscode.ExtensionContext | undefined;

/**
 * Initialize storage with extension context
 */
export function initStorage(ctx: vscode.ExtensionContext): void {
    context = ctx;
}

/**
 * Get the stored state
 */
export function getStoredState(): StoredState {
    if (!context) {
        return {};
    }
    return context.globalState.get<StoredState>(STORAGE_KEY, {});
}

/**
 * Update the stored state (merges with existing)
 */
export async function updateStoredState(updates: Partial<StoredState>): Promise<void> {
    if (!context) {
        return;
    }
    const current = getStoredState();
    const newState = { ...current, ...updates };
    await context.globalState.update(STORAGE_KEY, newState);
}

/**
 * Clear the stored state
 */
export async function clearStoredState(): Promise<void> {
    if (!context) {
        return;
    }
    await context.globalState.update(STORAGE_KEY, undefined);
}

/**
 * Check if stored state matches current workspace
 */
export function isStateValidForWorkspace(workspacePath: string): boolean {
    const state = getStoredState();
    return state.workspacePath === workspacePath && !!state.repoId;
}

/**
 * Save repo info after successful indexing
 */
export async function saveRepoInfo(
    repoId: string,
    repoName: string,
    workspacePath: string
): Promise<void> {
    await updateStoredState({
        repoId,
        repoName,
        workspacePath,
        lastIndexedTime: Date.now(),
    });
}

/**
 * Get stored repo ID if valid for current workspace
 */
export function getStoredRepoId(workspacePath: string): string | undefined {
    if (isStateValidForWorkspace(workspacePath)) {
        return getStoredState().repoId;
    }
    return undefined;
}


/**
 * Save chat history
 */
export async function saveChatHistory(history: any[]): Promise<void> {
    if (!context) return;
    await context.globalState.update(HISTORY_KEY, history);
}

/**
 * Load chat history
 */
export function loadChatHistory(): any[] {
    if (!context) return [];
    return context.globalState.get<any[]>(HISTORY_KEY, []);
}
