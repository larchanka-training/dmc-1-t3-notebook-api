from __future__ import annotations

import re
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from pathlib import Path

from app.features.ai.errors import build_ai_error
from app.features.ai.repository import AiRepository
from app.features.ai.schemas import (
    AiCodeGenerateRequest,
    AiCodeGenerateSuccessResponse,
    AiProviderInfo,
    AiValidationSummary,
    AiWarning,
)
from app.integrations.ai import (
    AiGenerationGateway,
    AiProviderGenerateRequest,
    AiProviderGenerateResponse,
    AiProviderInvalidResponseError,
    AiProviderTimeoutError,
    AiProviderUnavailableError,
)

logger = logging.getLogger("app.features.ai.service")

FENCED_BLOCK_RE = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)
COMMENT_BLOCK_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
LINE_COMMENT_RE = re.compile(r"^\s*//.*$", re.MULTILINE)
PREFERRED_FENCE_LANGS = ("javascript", "js", "jsx", "node", "ecmascript", "")
CODE_LINE_RE = re.compile(
    r"""
    ^\s*(
        (const|let|var|function|class|import|export|return|if|for|while|switch|try|catch|finally|async|await|throw)\b
        |[A-Za-z_$][\w$]*\s*=
        |[A-Za-z_$][\w$]*\([^)]*\)\s*\{
        |[}\])];?\s*$
        |[({[]\s*$
        |//|/\*
        |<[/A-Za-z]
    )
    """,
    re.VERBOSE,
)
CODE_TOKEN_RE = re.compile(
    r"\b(function|class|const|let|var|return|import|export|async|await|new)\b|=>|[;{}<>]"
)
CODE_ACTION_TERMS = (
    "write",
    "generate",
    "create",
    "implement",
    "build",
    "refactor",
    "revise",
    "update",
    "convert",
    "produce",
)
CODE_OBJECT_TERMS = (
    "code",
    "javascript",
    "js",
    "function",
    "class",
    "component",
    "script",
    "react",
    "hook",
)
UNSAFE_PATTERNS = (
    r"ignore (all |the )?(previous|prior) instructions",
    r"reveal (the )?(system|developer) prompt",
    r"show (the )?(hidden|internal) instructions",
    r"bypass (the )?(policy|guardrails|safety)",
    r"print (the )?(cookies?|secrets?|tokens?)",
)


@dataclass(slots=True)
class ExtractedCode:
    code: str
    extraction_applied: bool


@dataclass(slots=True)
class SyntaxValidationResult:
    ok: bool
    message: str | None = None


@dataclass(slots=True)
class ProviderAttemptResult:
    code: str
    extraction_applied: bool
    warnings: list[AiWarning]


def build_request_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return f"air_{timestamp}_{suffix}"


def _normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _iter_fenced_candidates(content: str) -> list[ExtractedCode]:
    candidates_by_lang: dict[str, list[ExtractedCode]] = {
        language: [] for language in PREFERRED_FENCE_LANGS
    }
    fallback_candidates: list[ExtractedCode] = []

    for match in FENCED_BLOCK_RE.finditer(content):
        language = match.group(1).strip().lower()
        code = match.group(2).strip()
        if not code:
            continue

        candidate = ExtractedCode(code=code, extraction_applied=True)
        if language in candidates_by_lang:
            candidates_by_lang[language].append(candidate)
        else:
            fallback_candidates.append(candidate)

    ordered: list[ExtractedCode] = []
    for language in PREFERRED_FENCE_LANGS:
        ordered.extend(candidates_by_lang[language])
    ordered.extend(fallback_candidates)
    return ordered


def _is_code_like_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if CODE_LINE_RE.match(line):
        return True
    return bool(
        CODE_TOKEN_RE.search(line)
        and stripped[-1:] in {";", "{", "}", ")", "]"}
    )


def _is_probably_code_snippet(text: str) -> bool:
    lines = _normalize_line_endings(text).split("\n")
    if any(_is_code_like_line(line) for line in lines):
        return True
    return len(CODE_TOKEN_RE.findall(text)) >= 2


def _extract_mixed_code_block(content: str) -> ExtractedCode | None:
    lines = _normalize_line_endings(content).split("\n")
    best_bounds: tuple[int, int] | None = None
    best_length = -1
    start: int | None = None
    code_like_seen = False

    def maybe_store(end: int) -> None:
        nonlocal best_bounds, best_length, start, code_like_seen
        if start is None or not code_like_seen:
            start = None
            code_like_seen = False
            return
        candidate = "\n".join(lines[start:end]).strip()
        if candidate and len(candidate) > best_length:
            best_bounds = (start, end)
            best_length = len(candidate)
        start = None
        code_like_seen = False

    for index, line in enumerate(lines):
        if _is_code_like_line(line):
            if start is None:
                start = index
            code_like_seen = True
            continue
        if start is not None and not line.strip():
            continue
        maybe_store(index)

    maybe_store(len(lines))
    if best_bounds is None:
        return None

    code = "\n".join(lines[best_bounds[0] : best_bounds[1]]).strip()
    if not code:
        return None
    return ExtractedCode(code=code, extraction_applied=True)


def extract_code_candidates(content: str) -> list[ExtractedCode]:
    normalized = _normalize_line_endings(content).strip()
    if not normalized:
        return []

    candidates = _iter_fenced_candidates(normalized)
    candidates.append(ExtractedCode(code=normalized, extraction_applied=False))

    mixed_candidate = _extract_mixed_code_block(normalized)
    if mixed_candidate is not None and mixed_candidate.code != normalized:
        candidates.append(mixed_candidate)

    unique: list[ExtractedCode] = []
    seen: set[tuple[str, bool]] = set()
    for candidate in candidates:
        key = (candidate.code, candidate.extraction_applied)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def extract_code_from_provider_content(content: str) -> tuple[str, bool]:
    candidates = extract_code_candidates(content)
    if not candidates:
        return "", False
    candidate = candidates[0]
    return candidate.code, candidate.extraction_applied


def strip_comments_and_whitespace(code: str) -> str:
    without_block_comments = COMMENT_BLOCK_RE.sub("", code)
    without_line_comments = LINE_COMMENT_RE.sub("", without_block_comments)
    return "".join(without_line_comments.split())


def is_comment_only_code(code: str) -> bool:
    return strip_comments_and_whitespace(code) == ""


def validate_javascript_syntax(code: str) -> SyntaxValidationResult:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".js",
            delete=False,
        ) as handle:
            handle.write(code)
            temp_path = Path(handle.name)

        completed = subprocess.run(
            ["node", "--check", str(temp_path)],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except FileNotFoundError:
        return SyntaxValidationResult(
            ok=False,
            message="JavaScript syntax validator is unavailable on the backend.",
        )
    except subprocess.TimeoutExpired:
        return SyntaxValidationResult(
            ok=False,
            message="JavaScript syntax validation timed out on the backend.",
        )
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    if completed.returncode == 0:
        return SyntaxValidationResult(ok=True)

    error_output = completed.stderr.strip() or completed.stdout.strip()
    if not error_output:
        return SyntaxValidationResult(
            ok=False,
            message="JavaScript syntax validation failed.",
        )

    lines = [line.strip() for line in error_output.splitlines() if line.strip()]
    for line in lines:
        if line.startswith("SyntaxError:"):
            return SyntaxValidationResult(ok=False, message=line)
    for line in lines:
        if line.startswith("Error:"):
            return SyntaxValidationResult(ok=False, message=line)
    filtered = [
        line
        for line in lines
        if not line.startswith("at ")
        and not line.startswith("Node.js v")
        and not line.endswith(".js:1")
        and line != "^"
    ]
    message = filtered[-1] if filtered else lines[-1]
    return SyntaxValidationResult(ok=False, message=message)


def build_repair_feedback(*, failure_kind: str, detail: str | None) -> str:
    parts = [
        "Return only plain JavaScript code.",
        "Do not include markdown fences, explanations, or prose.",
        "Return one complete corrected snippet, not a diff or partial fragment.",
        "Double-check that parentheses, braces, brackets, quotes, and template literals are balanced.",
    ]
    if failure_kind == "extraction":
        parts.append(
            "The previous response did not contain any extractable JavaScript code."
        )
    else:
        parts.append(
            "The previous response contained JavaScript syntax errors and could not be accepted."
        )
    if detail:
        parts.append(f"Validation detail: {detail}")
    return " ".join(parts)


def screen_prompt(prompt: str) -> str | None:
    lowered = prompt.lower()
    for pattern in UNSAFE_PATTERNS:
        if re.search(pattern, lowered):
            return "unsafe"

    has_action = any(term in lowered for term in CODE_ACTION_TERMS)
    has_object = any(term in lowered for term in CODE_OBJECT_TERMS)
    if has_action and has_object:
        return None
    return "rejected"


class AiService:
    def __init__(
        self,
        repository: AiRepository,
        gateway: AiGenerationGateway,
    ) -> None:
        self.repository = repository
        self.gateway = gateway
        self._last_failure_kind: str | None = None
        self._last_failure_detail: str | None = None
        self._last_repair_feedback: str | None = None
        self._last_provider_content: str | None = None

    async def generate_code(
        self, *, owner_id: uuid.UUID, payload: AiCodeGenerateRequest
    ) -> AiCodeGenerateSuccessResponse:
        request_id = build_request_id()
        logger.info(
            "AI generation request started request_id=%s notebook_id=%s source_block_id=%s mode=%s",
            request_id,
            payload.notebook_id,
            payload.source_block_id,
            payload.mode,
        )

        try:
            notebook_id = uuid.UUID(payload.notebook_id)
        except ValueError as exc:
            raise build_ai_error(
                status_code=422,
                error_code="AI_INVALID_REQUEST",
                message="The AI request is invalid.",
                retryable=False,
                request_id=request_id,
            ) from exc

        access = await self.repository.resolve_notebook_access(
            notebook_id=notebook_id, owner_id=owner_id
        )
        if access.status == "forbidden":
            raise build_ai_error(
                status_code=403,
                error_code="AI_FORBIDDEN",
                message="You do not have access to this notebook.",
                retryable=False,
                request_id=request_id,
            )
        if access.status == "missing" or access.notebook is None:
            raise build_ai_error(
                status_code=422,
                error_code="AI_INVALID_REQUEST",
                message="The AI request is invalid.",
                retryable=False,
                request_id=request_id,
            )

        snapshot = self.repository.parse_snapshot(access.notebook)
        source_block = self.repository.find_block(
            snapshot, block_id=payload.source_block_id
        )
        if source_block is None or source_block.type != "text":
            raise build_ai_error(
                status_code=422,
                error_code="AI_INVALID_REQUEST",
                message="The AI request is invalid.",
                retryable=False,
                request_id=request_id,
            )

        prompt_screening = screen_prompt(payload.prompt)
        if prompt_screening == "unsafe":
            raise build_ai_error(
                status_code=400,
                error_code="AI_PROMPT_UNSAFE",
                message="This request cannot be processed safely.",
                retryable=False,
                request_id=request_id,
            )
        if prompt_screening == "rejected":
            raise build_ai_error(
                status_code=400,
                error_code="AI_PROMPT_REJECTED",
                message=(
                    "This action accepts only code-generation or code-revision "
                    "requests."
                ),
                retryable=False,
                request_id=request_id,
            )

        provider_request = AiProviderGenerateRequest(
            request_id=request_id,
            notebook_id=payload.notebook_id,
            source_block_id=payload.source_block_id,
            mode=payload.mode,
            prompt=payload.prompt,
            context=payload.context.model_dump(by_alias=True),
            insertion_strategy=payload.insertion_strategy,
        )
        initial_response = await self._call_provider_or_raise(
            provider_request=provider_request,
            request_id=request_id,
        )
        initial_attempt = self._process_provider_attempt(
            provider_content=initial_response.content
        )

        final_response = initial_response
        repair_attempts = 0
        final_attempt = initial_attempt

        if final_attempt is None:
            repair_request = AiProviderGenerateRequest(
                request_id=request_id,
                notebook_id=payload.notebook_id,
                source_block_id=payload.source_block_id,
                mode=payload.mode,
                prompt=payload.prompt,
                context=payload.context.model_dump(by_alias=True),
                insertion_strategy=payload.insertion_strategy,
                attempt=1,
                repair_feedback=self._last_repair_feedback,
                previous_response_content=self._last_provider_content,
            )
            repair_response = await self._call_provider_or_raise(
                provider_request=repair_request,
                request_id=request_id,
            )
            final_response = repair_response
            final_attempt = self._process_provider_attempt(
                provider_content=repair_response.content
            )
            repair_attempts = 1

        if final_attempt is None:
            logger.warning(
                "AI generation request failed validation pipeline request_id=%s failure_kind=%s",
                request_id,
                self._last_failure_kind,
            )
            raise self._build_final_pipeline_error(request_id=request_id)

        logger.info(
            "AI generation request succeeded request_id=%s provider=%s model=%s repair_attempts=%s extraction_applied=%s warning_count=%s",
            request_id,
            final_response.provider_name,
            final_response.model,
            repair_attempts,
            final_attempt.extraction_applied,
            len(final_attempt.warnings),
        )
        return AiCodeGenerateSuccessResponse(
            request_id=request_id,
            status="success",
            code=final_attempt.code,
            provider=AiProviderInfo(
                name=final_response.provider_name,
                model=final_response.model,
            ),
            validation=AiValidationSummary(
                extraction_applied=final_attempt.extraction_applied,
                syntax_ok=True,
                repair_attempts=repair_attempts,
            ),
            warnings=final_attempt.warnings,
        )

    async def _call_provider_or_raise(
        self,
        *,
        provider_request: AiProviderGenerateRequest,
        request_id: str,
    ) -> AiProviderGenerateResponse:
        try:
            return await self.gateway.generate(provider_request)
        except AiProviderTimeoutError as exc:
            logger.warning(
                "AI provider timeout request_id=%s attempt=%s",
                request_id,
                provider_request.attempt,
            )
            raise build_ai_error(
                status_code=504,
                error_code="AI_PROVIDER_TIMEOUT",
                message="The AI provider did not respond in time. Try again.",
                retryable=True,
                request_id=request_id,
            ) from exc
        except AiProviderUnavailableError as exc:
            logger.warning(
                "AI provider unavailable request_id=%s attempt=%s",
                request_id,
                provider_request.attempt,
            )
            raise build_ai_error(
                status_code=503,
                error_code="AI_PROVIDER_UNAVAILABLE",
                message="The AI provider is temporarily unavailable. Try again.",
                retryable=True,
                request_id=request_id,
            ) from exc
        except AiProviderInvalidResponseError as exc:
            logger.warning(
                "AI provider invalid response request_id=%s attempt=%s",
                request_id,
                provider_request.attempt,
            )
            raise build_ai_error(
                status_code=502,
                error_code="AI_RESPONSE_INVALID",
                message="The AI response was invalid. Try again.",
                retryable=True,
                request_id=request_id,
            ) from exc

    def _process_provider_attempt(
        self,
        *,
        provider_content: str,
    ) -> ProviderAttemptResult | None:
        self._last_provider_content = provider_content

        candidates = extract_code_candidates(provider_content)
        if not candidates:
            self._last_failure_kind = "extraction"
            self._last_failure_detail = "No extractable JavaScript code was found."
            self._last_repair_feedback = build_repair_feedback(
                failure_kind=self._last_failure_kind,
                detail=self._last_failure_detail,
            )
            return None

        syntax_candidate_detected = False
        last_syntax_message: str | None = None

        for candidate in candidates:
            syntax = validate_javascript_syntax(candidate.code)
            if syntax.ok:
                warnings: list[AiWarning] = []
                if is_comment_only_code(candidate.code):
                    warnings.append(
                        AiWarning(
                            code="AI_COMMENT_ONLY_CODE",
                            message=(
                                "The generated code contains only comments or placeholder content."
                            ),
                        )
                    )
                return ProviderAttemptResult(
                    code=candidate.code,
                    extraction_applied=candidate.extraction_applied,
                    warnings=warnings,
                )

            last_syntax_message = syntax.message
            if _is_probably_code_snippet(candidate.code):
                syntax_candidate_detected = True

        self._last_failure_kind = "syntax" if syntax_candidate_detected else "extraction"
        self._last_failure_detail = last_syntax_message
        self._last_repair_feedback = build_repair_feedback(
            failure_kind=self._last_failure_kind,
            detail=self._last_failure_detail,
        )
        return None

    def _build_final_pipeline_error(self, *, request_id: str):
        if self._last_failure_kind == "syntax":
            return build_ai_error(
                status_code=502,
                error_code="AI_CODE_SYNTAX_INVALID",
                message=(
                    "The generated code was invalid and could not be repaired automatically. Try again."
                ),
                retryable=True,
                request_id=request_id,
            )
        return build_ai_error(
            status_code=502,
            error_code="AI_CODE_EXTRACTION_FAILED",
            message="The AI response did not contain usable code. Try again.",
            retryable=True,
            request_id=request_id,
        )
