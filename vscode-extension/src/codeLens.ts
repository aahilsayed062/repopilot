/**
 * RepoPilot VS Code Extension - Code Lens Provider
 * 
 * Provides inline "Ask RepoPilot" actions above functions and classes.
 */

import * as vscode from 'vscode';

export class RepoPilotCodeLensProvider implements vscode.CodeLensProvider {

    public provideCodeLenses(document: vscode.TextDocument, token: vscode.CancellationToken): vscode.CodeLens[] | Thenable<vscode.CodeLens[]> {
        const lenses: vscode.CodeLens[] = [];

        // Simple regex to find functions and classes (supports Python, TS, JS)
        // This is a naive implementation for demonstration, a real one would use AST or VS Code symbols
        const functionRegex = /(?:function|class|def)\s+([a-zA-Z0-9_]+)/g;
        const text = document.getText();

        let match;
        while ((match = functionRegex.exec(text)) !== null) {
            const line = document.positionAt(match.index).line;
            const range = new vscode.Range(line, 0, line, 0);

            // "Ask RepoPilot" command
            const cmd: vscode.Command = {
                title: "$(comment-discussion) Ask RepoPilot",
                tooltip: "Ask RepoPilot about this code",
                command: "repopilot.askAboutCode", // We need to register this
                arguments: [document.getText(range), match[1]] // Pass snippet? No, better to select it.
                // Actually, let's just trigger selection and focus chat.
            };

            lenses.push(new vscode.CodeLens(range, cmd));
        }

        return lenses;
    }
}
