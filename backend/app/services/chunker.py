"""
Chunker - Splits files into chunks with line range tracking.
"""

import hashlib
from pathlib import Path
from typing import Optional

from app.config import settings
from app.utils.logger import get_logger
from app.models.chunk import Chunk, ChunkMetadata, ChunkingStats

logger = get_logger(__name__)


# File types for chunking strategy
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".rb",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".swift", ".kt", ".scala",
    ".php", ".pl", ".lua", ".sh", ".bash", ".zsh", ".ps1", ".psm1",
}

DOC_EXTENSIONS = {
    ".md", ".rst", ".txt", ".adoc",
}

CONFIG_EXTENSIONS = {
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".xml",
}


def estimate_tokens(text: str) -> int:
    """Rough token estimation (1 token ≈ 4 chars for code)."""
    return len(text) // 4


def generate_chunk_id(repo_id: str, file_path: str, start_line: int) -> str:
    """Generate deterministic chunk ID."""
    combined = f"{repo_id}:{file_path}:{start_line}"
    return hashlib.sha256(combined.encode()).hexdigest()[:16]


class Chunker:
    """
    Chunking engine that splits files into searchable chunks.
    
    Strategies:
    - Code files: Chunk by lines with overlap
    - Doc files: Chunk by paragraphs/tokens
    - Config files: Keep whole or chunk by sections
    """
    
    def __init__(
        self,
        code_chunk_lines: int = None,
        code_overlap: int = None,
        doc_chunk_tokens: int = None,
        doc_overlap: int = None
    ):
        self.code_chunk_lines = code_chunk_lines or settings.code_chunk_lines
        self.code_overlap = code_overlap or settings.code_chunk_overlap
        self.doc_chunk_tokens = doc_chunk_tokens or settings.doc_chunk_tokens
        self.doc_overlap = doc_overlap or settings.doc_chunk_overlap
    
    def _get_chunk_type(self, file_path: str) -> str:
        """Determine chunk type based on file extension."""
        ext = Path(file_path).suffix.lower()
        if ext in CODE_EXTENSIONS:
            return "code"
        elif ext in DOC_EXTENSIONS:
            return "doc"
        elif ext in CONFIG_EXTENSIONS:
            return "config"
        else:
            # Default to code for unknown extensions
            return "code"
    
    def _get_language(self, file_path: str) -> str:
        """Get language from file extension."""
        ext = Path(file_path).suffix.lower()
        # Map extensions to language names
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "jsx",
            ".tsx": "tsx",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".php": "php",
            ".md": "markdown",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".xml": "xml",
            ".html": "html",
            ".css": "css",
            ".sql": "sql",
            ".sh": "bash",
        }
        return lang_map.get(ext, ext.lstrip(".") if ext else "text")
    
    def chunk_code_file(
        self,
        content: str,
        repo_id: str,
        file_path: str
    ) -> list[Chunk]:
        """
        Chunk a code file by lines with overlap.
        
        Args:
            content: File content
            repo_id: Repository ID
            file_path: Relative file path
            
        Returns:
            List of Chunk objects
        """
        lines = content.splitlines(keepends=True)
        if not lines:
            return []
        
        chunks = []
        language = self._get_language(file_path)
        
        i = 0
        while i < len(lines):
            # Determine chunk end
            end = min(i + self.code_chunk_lines, len(lines))
            
            # Get chunk lines
            chunk_lines = lines[i:end]
            chunk_content = "".join(chunk_lines)
            
            # Create chunk
            start_line = i + 1  # 1-indexed
            end_line = end  # 1-indexed (inclusive)
            
            chunk_id = generate_chunk_id(repo_id, file_path, start_line)
            
            chunk = Chunk(
                metadata=ChunkMetadata(
                    chunk_id=chunk_id,
                    repo_id=repo_id,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    language=language,
                    chunk_type="code",
                    token_count=estimate_tokens(chunk_content)
                ),
                content=chunk_content
            )
            chunks.append(chunk)
            
            # Move to next chunk with overlap
            i = end - self.code_overlap if end < len(lines) else end
            if i <= chunks[-1].metadata.start_line - 1:
                # Prevent infinite loop on very small files
                i = end
        
        return chunks
    
    def chunk_doc_file(
        self,
        content: str,
        repo_id: str,
        file_path: str
    ) -> list[Chunk]:
        """
        Chunk a documentation file by paragraphs/tokens.
        
        Args:
            content: File content
            repo_id: Repository ID
            file_path: Relative file path
            
        Returns:
            List of Chunk objects
        """
        lines = content.splitlines(keepends=True)
        if not lines:
            return []
        
        chunks = []
        language = self._get_language(file_path)
        
        current_chunk_lines = []
        current_start = 1
        current_tokens = 0
        
        for i, line in enumerate(lines):
            line_tokens = estimate_tokens(line)
            
            # Check if adding this line exceeds token limit
            if current_tokens + line_tokens > self.doc_chunk_tokens and current_chunk_lines:
                # Save current chunk
                chunk_content = "".join(current_chunk_lines)
                chunk_id = generate_chunk_id(repo_id, file_path, current_start)
                
                chunk = Chunk(
                    metadata=ChunkMetadata(
                        chunk_id=chunk_id,
                        repo_id=repo_id,
                        file_path=file_path,
                        start_line=current_start,
                        end_line=current_start + len(current_chunk_lines) - 1,
                        language=language,
                        chunk_type="doc",
                        token_count=current_tokens
                    ),
                    content=chunk_content
                )
                chunks.append(chunk)
                
                # Start new chunk with overlap
                overlap_lines = max(1, self.doc_overlap // 50)  # ~50 tokens per line
                overlap_start = max(0, len(current_chunk_lines) - overlap_lines)
                current_chunk_lines = current_chunk_lines[overlap_start:]
                current_start = i + 1 - len(current_chunk_lines)
                current_tokens = sum(estimate_tokens(l) for l in current_chunk_lines)
            
            current_chunk_lines.append(line)
            current_tokens += line_tokens
        
        # Save final chunk
        if current_chunk_lines:
            chunk_content = "".join(current_chunk_lines)
            chunk_id = generate_chunk_id(repo_id, file_path, current_start)
            
            chunk = Chunk(
                metadata=ChunkMetadata(
                    chunk_id=chunk_id,
                    repo_id=repo_id,
                    file_path=file_path,
                    start_line=current_start,
                    end_line=current_start + len(current_chunk_lines) - 1,
                    language=language,
                    chunk_type="doc",
                    token_count=current_tokens
                ),
                content=chunk_content
            )
            chunks.append(chunk)
        
        return chunks
    
    def chunk_config_file(
        self,
        content: str,
        repo_id: str,
        file_path: str
    ) -> list[Chunk]:
        """
        Chunk a config file. For small files, keep whole. For large ones, chunk by lines.
        """
        tokens = estimate_tokens(content)
        language = self._get_language(file_path)
        lines = content.splitlines(keepends=True)
        
        # If small enough, keep as single chunk
        if tokens < self.doc_chunk_tokens:
            chunk_id = generate_chunk_id(repo_id, file_path, 1)
            return [Chunk(
                metadata=ChunkMetadata(
                    chunk_id=chunk_id,
                    repo_id=repo_id,
                    file_path=file_path,
                    start_line=1,
                    end_line=len(lines) or 1,
                    language=language,
                    chunk_type="config",
                    token_count=tokens
                ),
                content=content
            )]
        
        # Otherwise, chunk like code
        return self.chunk_code_file(content, repo_id, file_path)
    
    def chunk_file(
        self,
        content: str,
        repo_id: str,
        file_path: str
    ) -> list[Chunk]:
        """
        Chunk a file based on its type.
        
        Args:
            content: File content
            repo_id: Repository ID
            file_path: Relative file path
            
        Returns:
            List of Chunk objects
        """
        chunk_type = self._get_chunk_type(file_path)
        
        if chunk_type == "code":
            return self.chunk_code_file(content, repo_id, file_path)
        elif chunk_type == "doc":
            return self.chunk_doc_file(content, repo_id, file_path)
        else:
            return self.chunk_config_file(content, repo_id, file_path)
    
    async def chunk_repository(
        self,
        repo_id: str,
        file_contents: dict[str, str]
    ) -> tuple[list[Chunk], ChunkingStats]:
        """
        Chunk all files in a repository.
        
        Args:
            repo_id: Repository ID
            file_contents: Dict mapping file paths to content
            
        Returns:
            Tuple of (chunks list, stats)
        """
        all_chunks = []
        stats = ChunkingStats()
        
        for file_path, content in file_contents.items():
            try:
                chunks = self.chunk_file(content, repo_id, file_path)
                all_chunks.extend(chunks)
                
                stats.total_files += 1
                for chunk in chunks:
                    stats.total_chunks += 1
                    stats.total_tokens += chunk.metadata.token_count
                    
                    # Track by type
                    ctype = chunk.metadata.chunk_type
                    stats.by_type[ctype] = stats.by_type.get(ctype, 0) + 1
                    
                    # Track by language
                    lang = chunk.metadata.language
                    stats.by_language[lang] = stats.by_language.get(lang, 0) + 1
                    
            except Exception as e:
                logger.warning("chunk_file_failed", file_path=file_path, error=str(e))
                continue
        
        logger.info(
            "chunking_complete",
            repo_id=repo_id,
            files=stats.total_files,
            chunks=stats.total_chunks,
            tokens=stats.total_tokens
        )
        
        return all_chunks, stats


# Global instance
chunker = Chunker()
