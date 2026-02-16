/**
 * RepoPilot VS Code Extension - Commands
 * 
 * VS Code command implementations.
 */

import * as vscode from 'vscode';
import { ChatPanelProvider } from './chatPanel';

/**
 * Register all extension commands
 */
export function registerCommands(
    context: vscode.ExtensionContext,
    chatPanel: ChatPanelProvider
): void {
    // Open Chat command
    context.subscriptions.push(
        vscode.commands.registerCommand('repopilot.openChat', async () => {
            await vscode.commands.executeCommand('repopilot.chatView.focus');
        })
    );

    // Index Workspace command
    context.subscriptions.push(
        vscode.commands.registerCommand('repopilot.indexWorkspace', async () => {
            // Focus chat panel and trigger indexing
            await vscode.commands.executeCommand('repopilot.chatView.focus');
            // The chat panel handles indexing via message
            chatPanel.postMessage({ type: 'MESSAGE_CLEAR' });
            chatPanel.postMessage({
                type: 'MESSAGE_APPEND',
                role: 'system',
                content: 'Starting workspace indexing...',
            });
            // Trigger index via internal call
            await vscode.commands.executeCommand('repopilot.triggerIndex');
        })
    );

    // Internal trigger for index (called from command)
    context.subscriptions.push(
        vscode.commands.registerCommand('repopilot.triggerIndex', async () => {
            // This sends a message to the webview which triggers indexing
            // Actually, we need to call the panel's index method directly
            // For now, we'll show a message telling user to click the button
            vscode.window.showInformationMessage('Click "Index" in the RepoPilot chat panel to index your workspace.');
        })
    );

    // Generate from Prompt command
    context.subscriptions.push(
        vscode.commands.registerCommand('repopilot.generateFromPrompt', async () => {
            const prompt = await vscode.window.showInputBox({
                prompt: 'What code would you like to generate?',
                placeHolder: 'e.g., Add a new API endpoint for user profiles',
            });

            if (prompt) {
                await vscode.commands.executeCommand('repopilot.chatView.focus');

                // Delegate to chat panel's smart routing pipeline.
                // injectQuestion shows the user message and routes through
                // Feature 1 (routing), Feature 3 (evaluation), Feature 4 (impact).
                await chatPanel.injectQuestion(prompt);
            }
        })
    );
    // Start Backend command
    context.subscriptions.push(
        vscode.commands.registerCommand('repopilot.startBackend', async () => {
            const workspaceFolders = vscode.workspace.workspaceFolders;
            let cwd = '';
            if (workspaceFolders && workspaceFolders.length > 0) {
                cwd = workspaceFolders[0].uri.fsPath;
            }

            const terminal = vscode.window.createTerminal({
                name: 'RepoPilot Backend',
                cwd: cwd || undefined,
            });

            // Use the start_backend.bat if on Windows, otherwise fallback
            const isWindows = process.platform === 'win32';
            if (isWindows) {
                terminal.sendText(`"${cwd}\\start_backend.bat"`);
            } else {
                terminal.sendText(`cd "${cwd}/backend" && python run.py`);
            }
            terminal.show();
            vscode.window.showInformationMessage('🚀 Starting RepoPilot backend...');
        })
    );

    // Export Chat command
    context.subscriptions.push(
        vscode.commands.registerCommand('repopilot.exportChat', () => {
            chatPanel.exportChat();
        })
    );

    // Ask About Code command (from Code Lens)
    context.subscriptions.push(
        vscode.commands.registerCommand('repopilot.askAboutCode', async (code: string, name: string) => {
            await vscode.commands.executeCommand('repopilot.chatView.focus');
            chatPanel.injectQuestion(`Explain the \`${name}\` function/class.`);
        })
    );
}
