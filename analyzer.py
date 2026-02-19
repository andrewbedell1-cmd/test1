"""
Transcript analyzer using Claude Opus 4.6 with adaptive thinking.
Produces structured notes, action items, and next steps from call transcripts.
"""

import os
from typing import Optional
from pydantic import BaseModel, Field
import anthropic

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """You are an expert meeting analyst and project manager. Your task is to analyze call transcripts and produce highly detailed, actionable output.

When analyzing a transcript, you must:
1. Write a comprehensive summary that captures all important context, not just high-level points
2. Extract every concrete decision that was made — no matter how small
3. Identify ALL action items with full context, even implied ones
4. List next steps in strict priority order
5. Note all participants and their roles where determinable
6. Identify the key topics discussed

For action items, always extract:
- A clear, specific title (start with a verb)
- Who is responsible (use "TBD" if unclear)
- A realistic due date in ISO format YYYY-MM-DD (infer from context clues like "by end of week", "next sprint", "by Friday", etc.; use null if completely unspecified)
- Priority: high (blocks others or has tight deadline), medium (important but flexible), low (nice to have)
- A detailed description with full context so anyone can pick it up cold

Be thorough. Missing an action item or next step is worse than being overly detailed."""


class ActionItem(BaseModel):
    title: str = Field(description="Specific action title starting with a verb, e.g. 'Schedule follow-up call with design team'")
    assignee: Optional[str] = Field(default=None, description="Person responsible; 'TBD' if unclear")
    due_date: Optional[str] = Field(default=None, description="ISO date YYYY-MM-DD or null if truly unspecified")
    priority: str = Field(description="high, medium, or low")
    description: str = Field(description="Full context so anyone can pick this up cold")


class TranscriptAnalysis(BaseModel):
    summary: str = Field(description="Comprehensive multi-paragraph summary capturing all key context, decisions, and outcomes")
    key_decisions: list[str] = Field(description="Every concrete decision made during the call, as clear statements")
    action_items: list[ActionItem] = Field(description="All action items, including implied ones")
    next_steps: list[str] = Field(description="Ordered list of next steps the group should take")
    participants: list[str] = Field(description="Participants identified in the transcript")
    topics: list[str] = Field(description="Key topics discussed")


def analyze_transcript(content: str) -> TranscriptAnalysis:
    """
    Analyze a call transcript and return structured notes using Claude Opus 4.6.
    Uses streaming + get_final_message to handle long transcripts without timeouts.
    """
    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=8192,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Please analyze this call transcript:\n\n{content}",
            }
        ],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": TranscriptAnalysis.model_json_schema(),
            }
        },
    ) as stream:
        final = stream.get_final_message()

    text = next(b.text for b in final.content if b.type == "text")

    import json
    data = json.loads(text)
    return TranscriptAnalysis(**data)
