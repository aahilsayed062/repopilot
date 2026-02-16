/**
 * RepoPilot VS Code Extension - Response Formatter
 * 
 * Formats backend responses into a clean, simple template.
 */

import {
    ChatResponse,
    GenerationResponse,
    Citation,
    ImpactAnalysisResponse,
    EvaluationResponse,
    RefinementResponse,
} from './types';

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

    // Changes — per-file with +N/-M stats
    if (response.diffs && response.diffs.length > 0) {
        // Summary header
        const totalAdded = response.diffs.reduce((sum, d) => sum + countLines(d.diff, '+'), 0);
        const totalRemoved = response.diffs.reduce((sum, d) => sum + countLines(d.diff, '-'), 0);
        sections.push(`### 🔧 Changes — ${response.diffs.length} file(s)  \`+${totalAdded} -${totalRemoved}\``);
        sections.push('');

        response.diffs.forEach(diff => {
            const added = countLines(diff.diff, '+');
            const removed = countLines(diff.diff, '-');
            const stats = `\`+${added} -${removed}\``;
            sections.push(`#### 📁 ${diff.file_path}  ${stats}`);
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
 * Count + or - lines in a diff string
 */
function countLines(diff: string, prefix: '+' | '-'): number {
    if (!diff) { return 0; }
    return diff.split('\n').filter(line => line.startsWith(prefix) && !line.startsWith(prefix + prefix)).length;
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

/**
 * Format an impact analysis report — compact inline note
 */
export function formatImpactReport(report: ImpactAnalysisResponse): string {
    const riskEmoji: Record<string, string> = {
        'LOW': '🟢', 'MEDIUM': '🟡', 'HIGH': '🟠', 'CRITICAL': '🔴',
    };
    const emoji = riskEmoji[report.risk_level] || '⚪';

    const parts: string[] = [];
    parts.push(`**🛡️ Impact:** ${emoji} **${report.risk_level}**`);

    if (report.indirectly_affected.length > 0) {
        const affected = report.indirectly_affected
            .map(f => `\`${f.file_path}\``)
            .join(', ');
        parts.push(`**Affected:** ${affected}`);
    }

    if (report.risks.length > 0) {
        const topRisks = report.risks.slice(0, 2).map(r => `⚠️ ${r}`).join(' · ');
        parts.push(topRisks);
    }

    if (report.recommendations.length > 0) {
        const topRecs = report.recommendations.slice(0, 2).map(r => `💡 ${r}`).join(' · ');
        parts.push(topRecs);
    }

    return parts.join('\n');
}

/**
 * Format evaluator response (Feature 3) as markdown
 */
export function formatEvaluationReport(report: EvaluationResponse): string {
    const sections: string[] = [];

    sections.push('### 🧠 Evaluation');
    if (report.enabled === false) {
        sections.push(`Disabled: ${report.reason || report.error || 'No evaluator output.'}`);
        return sections.join('\n');
    }

    if (report.critic) {
        sections.push(
            `- **Critic (${report.critic.provider})**: ${report.critic.score}/10, issues: ${report.critic.issues.length}`
        );
    }
    if (report.defender) {
        sections.push(
            `- **Defender (${report.defender.provider})**: ${report.defender.score}/10, issues: ${report.defender.issues.length}`
        );
    }

    sections.push(
        `- **Controller**: ${report.controller.decision} (score ${report.controller.final_score}/10, confidence ${Math.round((report.controller.confidence || 0) * 100)}%)`
    );

    if (report.controller.priority_fixes?.length > 0) {
        sections.push('');
        sections.push('**Priority fixes:**');
        report.controller.priority_fixes.slice(0, 5).forEach((fix) => {
            sections.push(`- ${fix}`);
        });
    }

    if (report.controller.improved_code_by_file?.length > 0) {
        sections.push('');
        sections.push('**Improved code suggestions:**');
        report.controller.improved_code_by_file.slice(0, 3).forEach((item) => {
            sections.push(`- \`${item.file_path}\``);
        });
    }

    return sections.join('\n');
}

/**
 * Format iterative refinement response (Feature 2)
 */
export function formatRefinementReport(report: RefinementResponse): string {
    const sections: string[] = [];
    sections.push('### ♻️ Refinement Result');
    sections.push(`- **Success:** ${report.success ? 'Yes' : 'No'}`);
    sections.push(`- **Iterations:** ${report.total_iterations}`);
    sections.push('');

    if (report.iteration_log?.length > 0) {
        sections.push('**Iteration log:**');
        report.iteration_log.forEach((it) => {
            const status = it.tests_passed ? 'PASS' : 'FAIL';
            sections.push(`- Iteration ${it.iteration}: ${status}`);
            if (it.refinement_action) {
                sections.push(`  Action: ${it.refinement_action}`);
            }
        });
    }

    if (report.final_tests?.trim()) {
        sections.push('');
        sections.push('### 🧪 Final Tests');
        sections.push('```python');
        sections.push(report.final_tests);
        sections.push('```');
    }

    return sections.join('\n');
}
