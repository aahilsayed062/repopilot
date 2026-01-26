/**
 * RepoPilot VS Code Extension - File Opener
 * 
 * Open cited files in the editor with line range highlighting.
 */

import * as vscode from 'vscode';
import * as path from 'path';

/**
 * Open a file from a citation
 * 
 * @param filePath - Relative path from repo root or absolute path
 * @param startLine - Optional start line (1-indexed)
 * @param endLine - Optional end line (1-indexed)
 */
export async function openCitedFile(
    filePath: string,
    startLine?: number,
    endLine?: number
): Promise<void> {
    // Get workspace root
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders || workspaceFolders.length === 0) {
        vscode.window.showErrorMessage('No workspace folder open');
        return;
    }

    const workspaceRoot = workspaceFolders[0].uri.fsPath;

    // Resolve the file path
    let absolutePath: string;
    if (path.isAbsolute(filePath)) {
        absolutePath = filePath;
    } else {
        absolutePath = path.join(workspaceRoot, filePath);
    }

    const fileUri = vscode.Uri.file(absolutePath);

    // Check if file exists
    try {
        await vscode.workspace.fs.stat(fileUri);
    } catch {
        vscode.window.showWarningMessage(
            `File not found in workspace: ${filePath}`
        );
        return;
    }

    // Open the document
    const document = await vscode.workspace.openTextDocument(fileUri);
    const editor = await vscode.window.showTextDocument(document, {
        preview: false,
        preserveFocus: false,
    });

    // Reveal the line range if specified
    if (startLine !== undefined && startLine > 0) {
        const start = Math.max(0, startLine - 1); // Convert to 0-indexed
        const end = endLine !== undefined ? Math.max(start, endLine - 1) : start;

        const range = new vscode.Range(
            new vscode.Position(start, 0),
            new vscode.Position(end, Number.MAX_SAFE_INTEGER)
        );

        // Set selection and reveal
        editor.selection = new vscode.Selection(range.start, range.end);
        editor.revealRange(range, vscode.TextEditorRevealType.InCenter);
    }
}

/**
 * Parse a line range string like "10-25" or "10"
 */
export function parseLineRange(lineRange: string): { start?: number; end?: number } {
    if (!lineRange) {
        return {};
    }

    const match = lineRange.match(/(\d+)(?:-(\d+))?/);
    if (!match) {
        return {};
    }

    const start = parseInt(match[1], 10);
    const end = match[2] ? parseInt(match[2], 10) : start;

    return { start, end };
}

/**
 * Create a clickable file link for VS Code terminal
 */
export function createFileLink(filePath: string, lineRange?: string): string {
    if (lineRange) {
        const { start } = parseLineRange(lineRange);
        if (start) {
            return `${filePath}:${start}`;
        }
    }
    return filePath;
}
