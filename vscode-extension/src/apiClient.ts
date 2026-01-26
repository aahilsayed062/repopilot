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
    return config.get<string>('backendUrl', 'http://localhost:8001');
}

/**
 * Make a fetch request with proper error handling
 */
async function fetchJson<T>(
    path: string,
    options: RequestInit = {}
): Promise<T> {
    const baseUrl = getBackendUrl();
    const url = `${baseUrl}${path}`;

    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
        });

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
        throw new ApiError(
            `Cannot connect to RepoPilot backend at ${baseUrl}. Is it running?`,
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
    });
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

    return fetchJson<RepoStatusResponse>(`/repo/status?${params.toString()}`);
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
    });
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
    });
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
    });
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
