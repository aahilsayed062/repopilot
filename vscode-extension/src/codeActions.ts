/**
 * RepoPilot VS Code Extension - Code Actions
 * 
 * Right-click context menu actions for selected code.
 */

import * as vscode from 'vscode';
import { ChatPanelProvider } from './chatPanel';

/**
 * Register code action commands
 */
export function registerCodeActions(
    context: vscode.ExtensionContext,
    chatPanel: ChatPanelProvider
): void {
    // Ask about selection
    context.subscriptions.push(
        vscode.commands.registerCommand('repopilot.askAboutSelection', async () => {
            await handleAskAboutSelection(chatPanel);
        })
    );

    // Explain selection
    context.subscriptions.push(
        vscode.commands.registerCommand('repopilot.explainSelection', async () => {
            await handleExplainSelection(chatPanel);
        })
    );
}

/**
 * Handle "Ask RepoPilot About Selection" command
 */
async function handleAskAboutSelection(chatPanel: ChatPanelProvider): Promise<void> {
    const editor = vscode.window.activeTextEditor;

    if (!editor) {
        vscode.window.showWarningMessage('No active editor');
        return;
    }

    const selection = editor.selection;
    if (selection.isEmpty) {
        vscode.window.showWarningMessage('No text selected. Select some code first.');
        return;
    }

    const selectedText = editor.document.getText(selection);
    const fileName = editor.document.fileName;
    const relativePath = vscode.workspace.asRelativePath(fileName);
    const startLine = selection.start.line + 1;
    const endLine = selection.end.line + 1;

    // Focus the chat panel
    await vscode.commands.executeCommand('repopilot.chatView.focus');

    // Build the question
    const question = `Explain this code from **${relativePath}** (lines ${startLine}-${endLine}):\n\n\`\`\`\n${selectedText}\n\`\`\`\n\nWhat does this code do and how does it fit into the overall codebase?`;

    // Inject the question
    await chatPanel.injectQuestion(question);
}

/**
 * Handle "Explain Selection" command
 */
async function handleExplainSelection(chatPanel: ChatPanelProvider): Promise<void> {
    const editor = vscode.window.activeTextEditor;

    if (!editor) {
        vscode.window.showWarningMessage('No active editor');
        return;
    }

    const selection = editor.selection;
    if (selection.isEmpty) {
        vscode.window.showWarningMessage('No text selected. Select some code first.');
        return;
    }

    const selectedText = editor.document.getText(selection);
    const fileName = editor.document.fileName;
    const relativePath = vscode.workspace.asRelativePath(fileName);
    const startLine = selection.start.line + 1;
    const endLine = selection.end.line + 1;

    // Focus the chat panel
    await vscode.commands.executeCommand('repopilot.chatView.focus');

    // Build the explanation question
    const question = `Provide a detailed explanation of this code from **${relativePath}** (lines ${startLine}-${endLine}):\n\n\`\`\`\n${selectedText}\n\`\`\`\n\nInclude:\n1. What this code does step by step\n2. Why it's implemented this way\n3. How it connects to other parts of the codebase\n4. Any potential issues or improvements`;

    // Inject the question
    await chatPanel.injectQuestion(question);
}
