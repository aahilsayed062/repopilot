/**
 * RepoPilot VS Code Extension - Shared Types
 * 
 * TypeScript interfaces matching backend models.
 */

// ============================================================================
// Health Check
// ============================================================================

export interface HealthResponse {
    status: string;
    version: string;
    mock_mode: boolean;
}

// ============================================================================
// Repository Models
// ============================================================================

export interface RepoStats {
    total_files: number;
    total_size_bytes: number;
    languages: Record<string, number>;
}

export interface RepoLoadRequest {
    repo_url: string;
    branch?: string;
}

export interface RepoLoadResponse {
    success: boolean;
    repo_id: string;
    repo_name: string;
    commit_hash: string;
    stats: RepoStats;
    message: string;
}

export interface RepoStatusResponse {
    repo_id: string;
    repo_name: string;
    exists: boolean;
    indexed: boolean;
    stats: RepoStats | null;
    chunk_count: number;
    files?: Array<{ path: string; size: number }>;
}

export interface RepoIndexRequest {
    repo_id: string;
    force?: boolean;
}

export interface RepoIndexResponse {
    success: boolean;
    repo_id: string;
    indexed: boolean;
    chunk_count: number;
    message: string;
}

// ============================================================================
// Chat Models
// ============================================================================

export interface Citation {
    file_path: string;
    line_range: string;
    snippet: string;
    why?: string;
}

export type AnswerConfidence = 'low' | 'medium' | 'high';

export interface ChatRequest {
    repo_id: string;
    question: string;
    decompose?: boolean;
}

export interface ChatResponse {
    answer: string;
    citations: Citation[];
    confidence: AnswerConfidence;
    assumptions: string[];
    subquestions?: string[];
}

// ============================================================================
// Code Generation Models
// ============================================================================

export interface GenerationRequest {
    repo_id: string;
    request: string;
}

export interface FileDiff {
    file_path: string;
    content?: string;
    diff: string;
}

export interface GenerationResponse {
    plan: string;
    diffs: FileDiff[];
    tests: string;
    citations: string[];
}

// ============================================================================
// PyTest Generation Models
// ============================================================================

export interface PyTestRequest {
    repo_id: string;
    target_file?: string;
    target_function?: string;
    custom_request?: string;
}

export interface PyTestResponse {
    success: boolean;
    tests: string;
    test_file_name: string;
    explanation: string;
    coverage_notes: string[];
    source_files: string[];
    error?: string;
}


// ============================================================================
// Webview Message Protocol
// ============================================================================

// Messages from Webview to Extension
export type WebviewToExtensionMessage =
    | { type: 'ASK'; question: string }
    | { type: 'GENERATE'; request: string }
    | { type: 'INDEX_WORKSPACE' }
    | { type: 'OPEN_CITATION'; file_path: string; start_line?: number; end_line?: number }
    | { type: 'READY' }
    | { type: 'SAVE_CHAT'; content: string }
    | { type: 'APPLY_CHANGES' }
    | { type: 'RUN_TESTS' };

// Messages from Extension to Webview
export type ExtensionToWebviewMessage =
    | { type: 'STATUS_UPDATE'; status: IndexingStatus; repoId?: string; repoName?: string }
    | { type: 'MESSAGE_APPEND'; role: 'user' | 'assistant' | 'system'; content: string; citations?: Citation[]; buttons?: { label: string; action: string }[] }
    | { type: 'MESSAGE_CLEAR' }
    | { type: 'ERROR_TOAST'; message: string }
    | { type: 'LOADING'; loading: boolean };

// ============================================================================
// Extension State
// ============================================================================

export type IndexingStatus =
    | 'not_connected'    // Backend unreachable
    | 'not_indexed'      // No repo loaded
    | 'loading'          // Loading repo
    | 'indexing'         // Indexing in progress
    | 'ready'            // Ready for queries
    | 'error';           // Error state

export interface StoredState {
    repoId?: string;
    repoName?: string;
    workspacePath?: string;
    lastIndexedTime?: number;
    backendUrl?: string;
}
