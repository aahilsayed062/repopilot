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
    code?: string;
    diff: string;
}

export interface GenerationResponse {
    plan: string;
    diffs: FileDiff[];
    tests: string;
    citations: string[];
}

// ============================================================================
// Smart Chat / Evaluation / Refinement (Round 2)
// ============================================================================

export interface RoutingDecision {
    primary_action: string;
    secondary_actions?: string[];
    reasoning?: string;
    confidence?: number;
    should_decompose?: boolean;
    parallel_agents?: string[];
    skip_agents?: string[];
}

export interface ReviewerVerdict {
    provider: string;
    score: number;
    issues: string[];
    feedback: string;
    suggested_changes: string[];
}

export interface ImprovedCodeFile {
    file_path: string;
    code: string;
}

export interface ControllerVerdict {
    decision: 'ACCEPT_ORIGINAL' | 'REQUEST_REVISION' | 'MERGE_FEEDBACK' | string;
    reasoning: string;
    final_score: number;
    confidence: number;
    merged_issues: string[];
    priority_fixes: string[];
    improved_code_by_file: ImprovedCodeFile[];
}

export interface EvaluationResponse {
    enabled: boolean;
    reason?: string;
    error?: string;
    critic?: ReviewerVerdict | null;
    defender?: ReviewerVerdict | null;
    controller: ControllerVerdict;
}

export interface SmartChatResponse {
    answer?: string;
    confidence?: AnswerConfidence | string;
    citations?: Citation[];
    assumptions?: string[];
    routing?: RoutingDecision;
    agents_used?: string[];
    agents_skipped?: string[];
    explain?: ChatResponse;
    generate?: GenerationResponse;
    test?: PyTestResponse;
    evaluation?: EvaluationResponse;
    evaluation_action?: string;
    evaluation_improved_code?: ImprovedCodeFile[];
    impact?: ImpactAnalysisResponse;
}

export interface EvaluateRequest {
    request_text: string;
    generated_diffs: FileDiff[];
    tests_text?: string;
    context?: string;
}

export interface RefineRequest {
    repo_id: string;
    request: string;
    chat_history?: Array<{ role: string; content: string }>;
}

export interface RefinementIteration {
    iteration: number;
    code_snippet: string;
    tests_snippet: string;
    test_output: string;
    tests_passed: boolean;
    failures: string[];
    refinement_action: string;
}

export interface RefinementResponse {
    success: boolean;
    total_iterations: number;
    final_code: string;
    final_tests: string;
    iteration_log: RefinementIteration[];
    final_test_output: string;
}

// ============================================================================
// Impact Analysis Models (Feature 4)
// ============================================================================

export interface ImpactAnalysisRequest {
    repo_id: string;
    changed_files: string[];
    code_changes: string;
}

export interface ImpactFile {
    file_path: string;
    reason: string;
}

export interface ImpactAnalysisResponse {
    directly_changed: string[];
    indirectly_affected: ImpactFile[];
    risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    risks: string[];
    recommendations: string[];
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
    | { type: 'GENERATE_TESTS'; customRequest?: string }
    | { type: 'INDEX_WORKSPACE' }
    | { type: 'OPEN_CITATION'; file_path: string; start_line?: number; end_line?: number }
    | { type: 'READY' }
    | { type: 'SAVE_CHAT'; content: string }
    | { type: 'APPLY_CHANGES' }
    | { type: 'RUN_TESTS' }
    | { type: 'MESSAGE_CLEAR' }
    | { type: 'REQUEST_FILE_CONTEXT'; files: string[] }
    | { type: 'CANCEL_REQUEST' }
    | { type: 'ACCEPT_FILE'; file_path: string }
    | { type: 'REJECT_FILE'; file_path: string }
    | { type: 'ACCEPT_ALL' };


// Messages from Extension to Webview
export type ExtensionToWebviewMessage =
    | { type: 'STATUS_UPDATE'; status: IndexingStatus; repoId?: string; repoName?: string }
    | { type: 'MESSAGE_APPEND'; role: 'user' | 'assistant' | 'system'; content: string; citations?: Citation[]; buttons?: { label: string; action: string }[] }
    | { type: 'MESSAGE_UPDATE'; content: string; citations?: Citation[] }
    | { type: 'MESSAGE_CLEAR' }
    | { type: 'ERROR_TOAST'; message: string }
    | { type: 'LOADING'; loading: boolean }
    | { type: 'EXPORT_REQUEST' }
    | { type: 'FILE_LIST'; files: string[] };


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
