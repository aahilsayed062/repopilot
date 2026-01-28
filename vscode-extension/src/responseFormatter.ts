/**
 * RepoPilot VS Code Extension - Response Formatter
 * 
 * Formats backend responses into a clean, simple template.
 */

import { ChatResponse, GenerationResponse, Citation } from './types';

/**
 * Format a chat (ask) response - simplified version
 */
export function formatChatResponse(response: ChatResponse): string {
    const sections: string[] = [];

    // Clean the answer - sometimes LLM returns JSON in the answer field
    let answer = response.answer || '';

    // If answer looks like JSON, try to extract just the answer text
    if (answer.trim().startsWith('{')) {
        try {
            const parsed = JSON.parse(answer);
            if (parsed.answer) {
                answer = parsed.answer;
            }
        } catch {
            // Not valid JSON, use as-is
        }
    }

    // Answer first - what the user actually wants
    sections.push('### ✅ Answer');
    sections.push(answer);
    sections.push('');

    // Citations - if any
    if (response.citations && response.citations.length > 0) {
        sections.push('### 📎 Sources');
        response.citations.forEach(cit => {
            sections.push(`- **${cit.file_path}**${cit.line_range ? ` (lines ${cit.line_range})` : ''}`);
        });
        sections.push('');
    }

    // Only show warnings if confidence is low or no evidence
    if (response.confidence === 'low' || response.citations.length === 0) {
        sections.push('> **Note**: Limited evidence found in repository. Answer may be based on general knowledge.');
        sections.push('');
    }

    return sections.join('\n');
}

/**
 * Format a generation response - simplified version
 */
export function formatGenerationResponse(response: GenerationResponse): string {
    const sections: string[] = [];

    // Plan
    sections.push('### 📋 Plan');
    sections.push(response.plan);
    sections.push('');

    // Changes
    if (response.diffs && response.diffs.length > 0) {
        sections.push('### 🔧 Changes');
        response.diffs.forEach(diff => {
            sections.push(`#### 📁 ${diff.file_path}`);
            sections.push('```diff');
            sections.push(diff.diff);
            sections.push('```');
            sections.push('');
        });
    }

    // Tests
    if (response.tests && response.tests.trim().length > 0) {
        sections.push('### 🧪 Tests');
        sections.push('```python');
        sections.push(response.tests);
        sections.push('```');
        sections.push('');
    }

    // Warning if no evidence
    if (!response.citations || response.citations.length === 0) {
        sections.push('> **⚠️ Caution**: No repository evidence used. Review carefully before applying.');
        sections.push('');
    }

    return sections.join('\n');
}

/**
 * Format a safe refusal response
 */
export function formatSafeRefusal(reason: string, needed: string[]): string {
    const sections: string[] = [];

    sections.push('### ⚠️ I cannot answer this yet');
    sections.push('');
    sections.push(reason);
    sections.push('');

    if (needed.length > 0) {
        sections.push('**I need:**');
        needed.forEach(item => {
            sections.push(`- ${item}`);
        });
    }

    return sections.join('\n');
}

/**
 * Extract clickable citations from a response
 */
export function extractCitations(response: ChatResponse | GenerationResponse): Citation[] {
    if ('citations' in response && Array.isArray(response.citations)) {
        // ChatResponse has Citation objects
        if (response.citations.length > 0 && typeof response.citations[0] === 'object') {
            return response.citations as Citation[];
        }
        // GenerationResponse has string citations - convert them
        return (response.citations as string[]).map(path => ({
            file_path: path,
            line_range: '',
            snippet: '',
        }));
    }
    return [];
}
