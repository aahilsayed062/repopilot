/**
 * RepoPilot VS Code Extension - API Client
 * 
 * Fetch wrapper for backend communication with health checking and error handling.
 */

import * as vscode from 'vscode';
import {
    HealthResponse,
    RepoLoadRequest,
    RepoLoadResponse,
    RepoStatusResponse,
    RepoIndexRequest,
    RepoIndexResponse,
    ChatRequest,
    ChatResponse,
    GenerationRequest,
    GenerationResponse,
    ImpactAnalysisRequest,
    ImpactAnalysisResponse,
    PyTestRequest,
    PyTestResponse,
    SmartChatRequest,
    SmartChatResponse,
    EvaluateRequest,
    EvaluationResult,
    RefineRequest,
    RefineResponse,
} from './types';

/**
 * Custom error for API failures
 */
export class ApiError extends Error {
    constructor(
        message: string,
        public statusCode?: number,
        public isNetworkError: boolean = false
    ) {
        super(message);
        this.name = 'ApiError';
    }
}

/**
 * Get the configured backend URL
 */
function getBackendUrl(): string {
    const config = vscode.workspace.getConfiguration('repopilot');
    return config.get<string>('backendUrl', 'http://localhost:8000');
}

function normalizeBackendUrl(url: string): string {
    return url.trim().replace(/\/+$/, '');
}

function buildFallbackUrls(currentUrl: string): string[] {
    const current = normalizeBackendUrl(currentUrl);
    const candidates = new Set<string>();

    const add = (url: string) => {
        const normalized = normalizeBackendUrl(url);
        if (normalized && normalized !== current) {
            candidates.add(normalized);
        }
    };

    add('http://localhost:8000');
    add('http://127.0.0.1:8000');

    if (current.includes('localhost')) {
        add(current.replace('localhost', '127.0.0.1'));
    }
    if (current.includes('127.0.0.1')) {
        add(current.replace('127.0.0.1', 'localhost'));
    }

    if (current.includes(':8001')) {
        add(current.replace(':8001', ':8000'));
    }

    return Array.from(candidates);
}

async function isHealthyAt(baseUrl: string): Promise<boolean> {
    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 3000);
        const response = await fetch(`${normalizeBackendUrl(baseUrl)}/health`, {
            signal: controller.signal,
        });
        clearTimeout(timeout);
        return response.ok;
    } catch {
        return false;
    }
}

async function updateBackendUrlSetting(nextUrl: string): Promise<void> {
    const config = vscode.workspace.getConfiguration('repopilot');
    const inspect = config.inspect<string>('backendUrl');

    let target = vscode.ConfigurationTarget.Global;
    if (inspect?.workspaceFolderValue !== undefined) {
        target = vscode.ConfigurationTarget.WorkspaceFolder;
    } else if (inspect?.workspaceValue !== undefined) {
        target = vscode.ConfigurationTarget.Workspace;
    }

    await config.update('backendUrl', normalizeBackendUrl(nextUrl), target);
}

/**
 * Make a fetch request with proper error handling
 */
async function fetchJson<T>(
    path: string,
    options: RequestInit = {},
    timeoutMs: number = 15000,
    externalSignal?: AbortSignal
): Promise<T> {
    const baseUrl = getBackendUrl();
    const url = `${baseUrl}${path}`;

    try {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), timeoutMs);

        // If an external signal is provided, abort our controller when it fires
        if (externalSignal) {
            if (externalSignal.aborted) {
                clearTimeout(timeout);
                throw new ApiError('Request cancelled', undefined, false);
            }
            externalSignal.addEventListener('abort', () => controller.abort(), { once: true });
        }

        const response = await fetch(url, {
            ...options,
            signal: controller.signal,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
        });
        clearTimeout(timeout);

        if (!response.ok) {
            const errorBody = await response.text();
            let message = `HTTP ${response.status}: ${response.statusText}`;
            try {
                const errorJson = JSON.parse(errorBody);
                message = errorJson.detail || message;
            } catch {
                // Use default message
            }
            throw new ApiError(message, response.status);
        }

        return await response.json() as T;
    } catch (error) {
        if (error instanceof ApiError) {
            throw error;
        }
        // Network error
        const msg = error instanceof Error ? error.message : String(error);
        throw new ApiError(
            `Connection failed (${msg}) to ${baseUrl}. Is backend running?`,
            undefined,
            true
        );
    }
}

// ============================================================================
// API Client Functions
// ============================================================================

/**
 * Check if the backend is healthy
 */
export async function checkHealth(): Promise<HealthResponse> {
    return fetchJson<HealthResponse>('/health');
}

/**
 * Check if backend is reachable (returns boolean)
 */
export async function isBackendHealthy(): Promise<boolean> {
    try {
        await checkHealth();
        return true;
    } catch {
        const configuredUrl = getBackendUrl();
        const fallbackUrls = buildFallbackUrls(configuredUrl);

        for (const url of fallbackUrls) {
            if (await isHealthyAt(url)) {
                try {
                    await updateBackendUrlSetting(url);
                } catch {
                    // Ignore settings update failures; health is still true.
                }
                return true;
            }
        }

        return false;
    }
}

/**
 * Load a repository from URL or local path
 */
export async function loadRepo(
    repoUrl: string,
    branch?: string
): Promise<RepoLoadResponse> {
    const body: RepoLoadRequest = { repo_url: repoUrl };
    if (branch) {
        body.branch = branch;
    }

    return fetchJson<RepoLoadResponse>('/repo/load', {
        method: 'POST',
        body: JSON.stringify(body),
    }, 150000); // 2.5 min -- cloning can be slow
}

/**
 * Get repository status
 */
export async function getRepoStatus(
    repoId: string,
    includeFiles: boolean = false
): Promise<RepoStatusResponse> {
    const params = new URLSearchParams({
        repo_id: repoId,
        include_files: includeFiles.toString(),
    });

    return fetchJson<RepoStatusResponse>(`/repo/status?${params.toString()}`, {}, 60000);
}

/**
 * Index a repository
 */
export async function indexRepo(
    repoId: string,
    force: boolean = false
): Promise<RepoIndexResponse> {
    const body: RepoIndexRequest = { repo_id: repoId, force };

    return fetchJson<RepoIndexResponse>('/repo/index', {
        method: 'POST',
        body: JSON.stringify(body),
    }, 300000); // 5 min -- indexing can be slow
}

/**
 * Ask a question about the repository
 */
export async function askQuestion(
    repoId: string,
    question: string
): Promise<ChatResponse> {
    const body: ChatRequest = {
        repo_id: repoId,
        question,
        decompose: true,
    };

    return fetchJson<ChatResponse>('/chat/ask', {
        method: 'POST',
        body: JSON.stringify(body),
    }, 120000); // 2 min -- LLM can be slow
}

/**
 * Generate code changes
 */
export async function generateCode(
    repoId: string,
    request: string
): Promise<GenerationResponse> {
    const body: GenerationRequest = { repo_id: repoId, request };

    return fetchJson<GenerationResponse>('/chat/generate', {
        method: 'POST',
        body: JSON.stringify(body),
    }, 120000); // 2 min -- LLM can be slow
}

/**
 * Analyze impact of code changes (Feature 4)
 */
export async function analyzeImpact(
    repoId: string,
    changedFiles: string[],
    codeChanges: string
): Promise<ImpactAnalysisResponse> {
    const body: ImpactAnalysisRequest = {
        repo_id: repoId,
        changed_files: changedFiles,
        code_changes: codeChanges,
    };

    return fetchJson<ImpactAnalysisResponse>('/chat/impact', {
        method: 'POST',
        body: JSON.stringify(body),
    }, 60000); // 1 min
}

/**
 * Generate PyTest test cases
 */
export async function generatePyTest(
    repoId: string,
    options: {
        targetFile?: string;
        targetFunction?: string;
        customRequest?: string;
    } = {}
): Promise<PyTestResponse> {
    const body: PyTestRequest = {
        repo_id: repoId,
        target_file: options.targetFile,
        target_function: options.targetFunction,
        custom_request: options.customRequest,
    };

    return fetchJson<PyTestResponse>('/chat/pytest', {
        method: 'POST',
        body: JSON.stringify(body),
    }, 120000); // 2 min -- LLM can be slow
}


/**
 * Smart chat — dynamic multi-agent routing (Feature 1)
 */
export async function smartChat(
    repoId: string,
    question: string,
    chatHistory?: Array<{ role: string; content: string }>,
    contextFileHints?: string[],
    signal?: AbortSignal
): Promise<SmartChatResponse> {
    const body: SmartChatRequest = {
        repo_id: repoId,
        question,
        chat_history: chatHistory,
        context_file_hints: contextFileHints,
    };

    return fetchJson<SmartChatResponse>('/chat/smart', {
        method: 'POST',
        body: JSON.stringify(body),
    }, 180000, signal); // 3 min — may run multiple agents
}

/**
 * Evaluate generated code using Critic-Defender-Controller (Feature 3)
 */
export async function evaluateCode(
    requestText: string,
    generatedDiffs: Array<{ file_path: string; diff: string; code?: string; content?: string }>,
    testsText: string = '',
    context: string = ''
): Promise<EvaluationResult> {
    const body: EvaluateRequest = {
        request_text: requestText,
        generated_diffs: generatedDiffs,
        tests_text: testsText,
        context,
    };

    return fetchJson<EvaluationResult>('/chat/evaluate', {
        method: 'POST',
        body: JSON.stringify(body),
    }, 120000); // 2 min
}

/**
 * Iterative PyTest-driven refinement (Feature 2)
 */
export async function refineCode(
    repoId: string,
    request: string,
    chatHistory?: Array<{ role: string; content: string }>
): Promise<RefineResponse> {
    const body: RefineRequest = {
        repo_id: repoId,
        request,
        chat_history: chatHistory,
    };

    return fetchJson<RefineResponse>('/chat/refine', {
        method: 'POST',
        body: JSON.stringify(body),
    }, 300000); // 5 min — multiple iterations
}

/**
 * Full workflow: Load repo, index if needed, return repo_id
 */
export async function loadAndIndexRepo(
    repoUrl: string,
    onProgress?: (status: string) => void
): Promise<{ repoId: string; repoName: string }> {
    // Step 1: Load repository
    onProgress?.('Loading repository...');
    const loadResult = await loadRepo(repoUrl);
    const repoId = loadResult.repo_id;
    const repoName = loadResult.repo_name;

    // Step 2: Check if already indexed
    onProgress?.('Checking index status...');
    const status = await getRepoStatus(repoId);

    if (status.indexed) {
        onProgress?.('Repository already indexed');
        return { repoId, repoName };
    }

    // Step 3: Trigger indexing
    onProgress?.('Indexing repository...');
    await indexRepo(repoId);

    // Step 4: Poll until indexed (max 60 attempts, 2s each = 2 minutes)
    const maxAttempts = 60;
    for (let i = 0; i < maxAttempts; i++) {
        await new Promise(resolve => setTimeout(resolve, 2000));
        const currentStatus = await getRepoStatus(repoId);

        if (currentStatus.indexed) {
            onProgress?.(`Indexed ${currentStatus.chunk_count} chunks`);
            return { repoId, repoName };
        }

        onProgress?.(`Indexing... (${i + 1}/${maxAttempts})`);
    }

    throw new ApiError('Indexing timeout. Please try again.');
}

/**
 * Stream a question about the repository
 */
export async function* streamChat(
    repoId: string,
    question: string,
    chatHistory?: Array<{ role: string; content: string }>
): AsyncGenerator<string, void, unknown> {
    const baseUrl = getBackendUrl();
    const url = `${baseUrl}/chat/stream`;

    // We can't use the generic fetchJson because we need the raw stream
    const body: ChatRequest = {
        repo_id: repoId,
        question,
        decompose: true,
        chat_history: chatHistory,
    };

    const controller = new AbortController();
    // const timeout = setTimeout(() => controller.abort(), 120000); 

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(body),
            signal: controller.signal,
        });

        // clearTimeout(timeout);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        if (!response.body) throw new Error('No response body');

        // Node.js fetch (v18+) returns a ReadableStream (Web Streams API)
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6); // Do not trim! Preserves leading spaces.
                    if (data.trim() === '[DONE]') return; // Check trimmed for protocol messages
                    if (data.startsWith('[ERROR]')) throw new Error(data.slice(7));
                    // Unescape newlines
                    yield data.replace(/\\n/g, '\n');
                }
            }
        }

    } catch (error) {
        throw error;
    }
}
