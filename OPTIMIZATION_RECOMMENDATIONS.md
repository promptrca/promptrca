# Token Waste & Noise Reduction Recommendations

## Executive Summary
Current investigation wastes **5,000-10,000 tokens (30-50% overhead)** per run through:
- Verbose agent prompts (~1,500-2,000 tokens/agent)
- Agent reasoning output in logs (~200-500 tokens/turn)
- Excessive debug logging (395 logger calls with emojis)
- Redundant resource discovery (4x AWS client creation)
- Large investigation context passed repeatedly (~2,000+ tokens/handoff)

## Recommendations by Impact

### 🔴 CRITICAL: Reduce Agent Prompt Verbosity (40% reduction)
**Token Savings:** ~2,000-3,000 tokens per investigation

**Changes:**
```python
# Use optimized prompts (70% size reduction)
# Before: trace_specialist.md = 76 lines
# After:  trace_specialist_optimized.md = 32 lines
```

**Action:**
1. Replace prompts in `/src/promptrca/prompts/` with `*_optimized.md` versions
2. Remove emojis, excessive examples, repetitive warnings
3. Keep only essential: role, workflow, handoff rules, one example

**Files to optimize:**
- `trace_specialist.md` → 32 lines (was 76)
- `stepfunctions_specialist.md` → 28 lines (was 69)
- `hypothesis_generator.md` → 35 lines (was 83)
- `lambda_specialist.md`
- `apigateway_specialist.md`
- `iam_specialist.md`
- `s3_specialist.md`
- `sqs_specialist.md`
- `sns_specialist.md`
- `root_cause_analyzer.md`

---

### 🟠 HIGH: Suppress Agent Reasoning Output (20% reduction)
**Token Savings:** ~1,000-2,000 tokens per investigation

**Problem:** Agents output verbose reasoning that gets logged:
```
We need to follow mandatory workflow: call trace_specialist_tool...
Now wait for response...
Let's call tool.
```

**Solution:** Configure agents to suppress intermediate reasoning.

**Changes to `swarm_orchestrator.py`:**
```python
def _create_trace_agent() -> Agent:
    return Agent(
        name="trace_specialist",
        model=create_orchestrator_model(),
        system_prompt=load_prompt("trace_specialist_optimized"),
        tools=[trace_specialist_tool],
        # Add these to reduce verbose output:
        response_format="minimal",  # if supported by Strands
        instructions_suffix="Respond only with tool calls and final handoff. Do not explain your reasoning step-by-step."
    )
```

**Alternative:** Add to each optimized prompt:
```markdown
## Output Rules
- Call tools immediately, no explanation
- No step-by-step reasoning
- Only final analysis and handoff
```

---

### 🟠 HIGH: Reduce Debug Logging (15% reduction)
**Token Savings:** Cleaner logs, ~10% less context pollution

**Problem:** 395 logger calls across 32 files with emoji spam:
```python
logger.info("🔍 [DEBUG] Extracted assume_role_arn: None")
logger.info("🔍 [DEBUG] Extracted external_id: None")
logger.info("🔍 Debug: Taking free_text_input path")
```

**Changes to logging:**

1. **Create log level configuration:**
```python
# src/promptrca/utils/logger.py
import os

def get_logger(name):
    logger = logging.getLogger(name)

    # Default to WARNING in production
    log_level = os.getenv('PROMPTRCA_LOG_LEVEL', 'WARNING')
    logger.setLevel(log_level)

    # Remove emoji formatter in production
    if log_level != 'DEBUG':
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))

    return logger
```

2. **Remove emoji spam from critical paths:**
```python
# Before:
logger.info("🔍 [DEBUG] Extracted assume_role_arn: None")

# After:
logger.debug("Extracted assume_role_arn: %s", assume_role_arn)
```

3. **Consolidate AWS client logging:**
```python
# src/promptrca/core/swarm_orchestrator.py:397-404

# Before (4 separate log statements):
logger.info(f"🔍 Creating AWS client for region: {region}")
logger.info(f"🔍 [DEBUG] AWSClient.__init__ called...")
logger.info(f"🔍 [DEBUG] _create_session called...")
logger.info(f"✅ AWS client initialized for region: {region}")

# After (1 log statement):
logger.debug("AWS client initialized: region=%s, account=%s", region, aws_client.account_id)
```

---

### 🟡 MEDIUM: Optimize Investigation Context (10% reduction)
**Token Savings:** ~500-1,000 tokens per investigation

**Problem:** Full investigation prompt (670 lines) passed to every agent in `invocation_state`.

**Changes to `swarm_orchestrator.py:426-443`:**
```python
# Before: Pass entire context dictionary
investigation_context = {
    "trace_ids": parsed_inputs.trace_ids,
    "region": region,
    "parsed_inputs": {
        "trace_ids": parsed_inputs.trace_ids,
        "primary_targets": [
            {
                "type": target.type,
                "name": target.name,
                "arn": target.arn,
                "region": target.region,
                "metadata": target.metadata
            }
            for target in parsed_inputs.primary_targets
        ]
    }
}

# After: Pass minimal required context
investigation_context = {
    "trace_ids": parsed_inputs.trace_ids,
    "region": region,
    "target_count": len(parsed_inputs.primary_targets)
}
```

**Modify investigation prompt creation (`swarm_orchestrator.py:606-669`):**
```python
# Before: 670-line prompt with full JSON dumps
prompt = f"""🔍 AWS INFRASTRUCTURE INVESTIGATION
...
📦 RESOURCES DATA:
{json.dumps(resources, indent=2, default=str)}
...
"""

# After: Minimal prompt, resources in invocation_state
prompt = f"""AWS INFRASTRUCTURE INVESTIGATION

MISSION: Investigate AWS infrastructure issue.

DISCOVERED RESOURCES: {len(resources)} resources
REGION: {region}
TRACES: {', '.join(parsed_inputs.trace_ids) if parsed_inputs.trace_ids else 'None'}

WORKFLOW:
1. trace_specialist: Analyze traces → hand off to service specialists
2. Service specialists: Analyze resources → hand off to hypothesis_generator
3. hypothesis_generator: Generate hypotheses (returns structured output)

START: trace_specialist
"""
```

---

### 🟡 MEDIUM: Eliminate Redundant AWS Client Creation (5% reduction)
**Token Savings:** Faster execution, reduced log noise

**Problem:** Creating 4 AWS clients for same account:
```
15:34:57 - ✅ AWS client initialized for region: eu-west-1
15:34:57 - 🔐 Authenticated as: arn:aws:iam::840181656986:user/chris
15:34:57 - ✅ AWS client initialized for region: eu-west-1
15:34:57 - 🔐 Authenticated as: arn:aws:iam::840181656986:user/chris
[2 more times]
```

**Root Cause:** Each specialist tool creates its own AWS client instead of using shared context.

**Changes to `swarm_tools.py`:**
```python
# Before: Each tool creates new client
def lambda_specialist_tool(resource_data: str, investigation_context: str) -> str:
    aws_client = AWSClient(region=context_dict.get('region', 'us-east-1'))
    ...

# After: Use shared client from context
from ..context import get_aws_client

def lambda_specialist_tool(resource_data: str, investigation_context: str) -> str:
    try:
        aws_client = get_aws_client()  # Reuse from context
    except RuntimeError:
        return json.dumps({"error": "AWS client not available in context"})
    ...
```

---

### 🟢 LOW: Use Structured Output for Hypothesis Generation (5% reduction)
**Token Savings:** ~200-500 tokens, cleaner parsing

**Problem:** Hypothesis generator returns markdown text that needs parsing.

**Solution:** Use Strands `structured_output` with Pydantic model.

**Changes to `swarm_agents.py`:**
```python
# Create hypothesis model
from pydantic import BaseModel, Field
from typing import List

class Hypothesis(BaseModel):
    description: str = Field(description="Hypothesis description")
    confidence: float = Field(description="Confidence score 0.0-1.0")
    evidence: List[str] = Field(description="Supporting evidence")

class HypothesisAnalysis(BaseModel):
    facts: List[str] = Field(description="Facts from specialists")
    hypotheses: List[Hypothesis] = Field(description="Generated hypotheses (1-3)")

def create_hypothesis_agent_standalone() -> Agent:
    """Hypothesis agent that returns structured Pydantic output."""
    return Agent(
        name="hypothesis_generator",
        model=create_hypothesis_agent_model(),
        system_prompt=load_prompt("hypothesis_generator_optimized"),
        structured_output=HypothesisAnalysis  # Use structured output
    )
```

---

## Implementation Priority

1. **Week 1:** Optimize agent prompts (40% reduction)
   - Replace all `*.md` files with optimized versions
   - Test with sample investigations

2. **Week 2:** Suppress agent reasoning + reduce logging (35% reduction)
   - Add output rules to prompts
   - Configure log levels
   - Remove emoji spam

3. **Week 3:** Optimize context passing (10% reduction)
   - Minimize investigation_context
   - Reduce prompt size

4. **Week 4:** Fix AWS client reuse + structured output (10% reduction)
   - Share AWS client via context
   - Implement structured hypothesis output

---

## Measurement

**Before optimization:**
```
Investigation 1761320097054.527.c16eb564.10:
- Duration: 54.5s
- Estimated tokens: ~15,000-20,000
- Log lines: 89
```

**After optimization (projected):**
```
Investigation:
- Duration: 45-50s (10% faster)
- Estimated tokens: ~8,000-12,000 (40-50% reduction)
- Log lines: ~30 (66% reduction)
```

---

## Files to Modify

### Prompts (10 files)
- `src/promptrca/prompts/*.md` → Use optimized versions

### Code (4 files)
- `src/promptrca/core/swarm_orchestrator.py` (context optimization, AWS client)
- `src/promptrca/core/swarm_tools.py` (AWS client reuse)
- `src/promptrca/agents/swarm_agents.py` (structured output, agent config)
- `src/promptrca/utils/logger.py` (log level configuration)

### Logging cleanup (32 files)
- Remove emoji spam from all logger calls
- Change `logger.info` → `logger.debug` for diagnostic info
- Consolidate multi-line log statements

---

## Bonus: Strands Best Practices

From Strands documentation on multi-agent patterns:

1. **Keep prompts minimal** - Agents should get just enough context to do their job
2. **Use invocation_state for data** - Don't pass large JSON in prompts
3. **Structured output for data extraction** - Use Pydantic models instead of text parsing
4. **Minimize handoff context** - Pass only essential findings, not full history
5. **Agent specialization** - Each agent should have narrow, clear responsibility

Your current implementation violates #1, #2, and #4, leading to token waste.
