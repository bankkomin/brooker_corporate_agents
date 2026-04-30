"""Chain-of-thought prompting for complex multi-step queries."""
import logging
import re
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class ReasoningStep:
    step_num: int
    description: str
    result: str


@dataclass
class CoTResult:
    query: str
    query_type: str  # simple, analytical, comparison, calculation
    steps: list[ReasoningStep] = field(default_factory=list)
    final_answer: str = ""
    used_cot: bool = False


# Query complexity classifier
COMPLEX_PATTERNS = [
    (r"compare|versus|vs\b|difference between", "comparison"),
    (r"trend|over time|history|progression|quarter.over.quarter", "analytical"),
    (r"calculate|compute|what if|impact|headroom|ratio", "calculation"),
    (r"why|explain|reason|cause|because", "analytical"),
    (r"all .+ that|every .+ where|which .+ have", "analytical"),
]


def classify_complexity(query: str) -> str:
    """Determine if a query needs chain-of-thought reasoning."""
    query_lower = query.lower()
    for pattern, qtype in COMPLEX_PATTERNS:
        if re.search(pattern, query_lower):
            return qtype
    return "simple"


def build_cot_prompt(
    query: str,
    query_type: str,
    context: str,
    skill_content: str = "",
) -> str:
    """Build a chain-of-thought prompt that forces step-by-step reasoning."""
    if query_type == "simple":
        return _build_simple_prompt(query, context, skill_content)

    cot_instruction = COT_TEMPLATES.get(query_type, COT_TEMPLATES["analytical"])

    return f"""{skill_content}

{cot_instruction}

Context from knowledge base:
{context}

Question: {query}

Remember: Show your reasoning step by step. Use [N] citations. State your confidence in each step.
If any step lacks sufficient data, say so explicitly rather than guessing."""


def _build_simple_prompt(query: str, context: str, skill_content: str) -> str:
    return f"""{skill_content}

Answer the following question using the provided context. Cite sources with [N].
Be precise and factual. If the answer is not in the context, say so.

Context:
{context}

Question: {query}"""


COT_TEMPLATES = {
    "comparison": """You are answering a comparison question. Follow these steps:

Step 1: IDENTIFY what is being compared (entities, time periods, metrics)
Step 2: FIND the relevant data for each item being compared from the context
Step 3: COMPARE the values side by side, noting differences
Step 4: SYNTHESIZE a conclusion from the comparison
Step 5: STATE your final answer with citations

Format your response as:
**Step 1 - Identify:** ...
**Step 2 - Data:** ...
**Step 3 - Compare:** ...
**Step 4 - Synthesis:** ...
**Answer:** ...""",

    "analytical": """You are answering an analytical question that requires reasoning. Follow these steps:

Step 1: IDENTIFY the key question and what data is needed
Step 2: EXTRACT relevant facts from the context
Step 3: ANALYZE the facts — look for patterns, causes, or implications
Step 4: REASON through the analysis to reach a conclusion
Step 5: STATE your final answer with supporting evidence and citations

Format your response as:
**Step 1 - Question:** ...
**Step 2 - Facts:** ...
**Step 3 - Analysis:** ...
**Step 4 - Reasoning:** ...
**Answer:** ...""",

    "calculation": """You are answering a question that involves calculation. Follow these steps:

Step 1: IDENTIFY what needs to be calculated and the formula/method
Step 2: FIND the input values from the context (cite each source)
Step 3: SHOW the calculation step by step (DO NOT skip steps — show every operation)
Step 4: VERIFY the result makes sense (sanity check against known ranges)
Step 5: STATE the final result with units and confidence

IMPORTANT: Use a calculator for arithmetic. Do NOT do mental math.

Format your response as:
**Step 1 - Method:** ...
**Step 2 - Inputs:** ...
**Step 3 - Calculation:** ...
**Step 4 - Verification:** ...
**Answer:** ...""",
}


def parse_cot_response(response: str, query: str, query_type: str) -> CoTResult:
    """Parse a CoT response into structured steps."""
    result = CoTResult(query=query, query_type=query_type)

    if query_type == "simple":
        result.final_answer = response
        result.used_cot = False
        return result

    result.used_cot = True

    # Extract steps
    step_pattern = re.compile(r"\*\*Step (\d+)\s*[-—]\s*(\w+):\*\*\s*(.*?)(?=\*\*Step|\*\*Answer|\Z)", re.DOTALL)
    for match in step_pattern.finditer(response):
        result.steps.append(ReasoningStep(
            step_num=int(match.group(1)),
            description=match.group(2),
            result=match.group(3).strip(),
        ))

    # Extract final answer
    answer_match = re.search(r"\*\*Answer:\*\*\s*(.*?)$", response, re.DOTALL)
    if answer_match:
        result.final_answer = answer_match.group(1).strip()
    else:
        result.final_answer = response  # fallback to full response

    return result
