from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

TrimmedString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
TrimmedShortString = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
]


class AiRelevantBlock(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    block_id: str = Field(alias="blockId")
    type: Literal["text", "code"]
    content: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)
    ]


class AiRequestContext(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    language: Literal["javascript"]
    scope: Literal["this", "notebook"] = "this"
    source_text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=12000)
    ] = Field(alias="sourceText")
    notebook_title: Annotated[
        str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ] = Field(default=None, alias="notebookTitle")
    globals_summary: list[TrimmedShortString] = Field(
        default_factory=list, alias="globalsSummary", max_length=50
    )
    relevant_blocks: list[AiRelevantBlock] = Field(
        default_factory=list, alias="relevantBlocks", max_length=20
    )


class AiCodeGenerateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    notebook_id: str = Field(alias="notebookId")
    source_block_id: str = Field(alias="sourceBlockId")
    mode: Literal["generate", "revise"]
    prompt: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)
    ]
    context: AiRequestContext
    insertion_strategy: Literal["next-empty-or-new-after-source"] = Field(
        alias="insertionStrategy"
    )

    @model_validator(mode="after")
    def validate_combined_budget(self) -> "AiCodeGenerateRequest":
        combined_text = len(self.prompt) + len(self.context.source_text)
        if self.context.notebook_title is not None:
            combined_text += len(self.context.notebook_title)
        combined_text += sum(len(item) for item in self.context.globals_summary)
        combined_text += sum(
            len(block.content) for block in self.context.relevant_blocks
        )
        if combined_text > 50000:
            raise ValueError("Combined AI payload exceeds the Version 1 budget.")
        return self


class AiProviderInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str
    model: str


class AiValidationSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    extraction_applied: bool = Field(alias="extractionApplied")
    syntax_ok: bool = Field(alias="syntaxOk")
    repair_attempts: Literal[0, 1] = Field(alias="repairAttempts")


class AiWarning(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    code: Literal["AI_CONTEXT_TRUNCATED", "AI_COMMENT_ONLY_CODE"]
    message: str


class AiCodeGenerateSuccessResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    request_id: str = Field(alias="requestId")
    status: Literal["success"]
    code: str
    provider: AiProviderInfo
    validation: AiValidationSummary
    warnings: list[AiWarning] = Field(default_factory=list)


class AiErrorResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    request_id: str | None = Field(default=None, alias="requestId")
    status: Literal["error"]
    error_code: str = Field(alias="errorCode")
    message: str
    retryable: bool
