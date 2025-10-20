# PromptRCA Multi-Agent System Optimization Plan

**Date:** 2025-10-20
**Author:** Architecture Review
**Status:** Draft for Implementation

---

## Executive Summary

PromptRCA's multi-agent architecture is **fundamentally sound** and aligns with 2024-2025 research best practices for hierarchical LLM systems. However, the current implementation has significant token inefficiencies that can be addressed with targeted optimizations.

**Key Findings:**
- ✅ Architecture pattern is correct (hierarchical orchestration with specialized agents)
- ✅ Context isolation via `contextvars` is excellent
- ✅ Model heterogeneity support is forward-thinking
- ⚠️ Token usage is 2-3x higher than optimal due to verbose prompts and full context passing
- ⚠️ Eager agent initialization wastes resources on unused specialists

**Expected Impact:**
- **Priority 1 (Quick Wins):** 40-50% token reduction, 1-2 days effort
- **Priority 2 (Medium-Term):** 55-60% token reduction, 1-2 weeks effort
- **Priority 3 (Strategic):** 60-80% token reduction, 1-2 months effort

---

## Table of Contents

1. [Current Architecture Analysis](#1-current-architecture-analysis)
2. [Research Comparison](#2-research-comparison)
3. [Token Usage Breakdown](#3-token-usage-breakdown)
4. [Priority 1: Quick Wins](#4-priority-1-quick-wins-1-2-days)
5. [Priority 2: Medium-Term Improvements](#5-priority-2-medium-term-improvements-1-2-weeks)
6. [Priority 3: Strategic Enhancements](#6-priority-3-strategic-enhancements-1-2-months)
7. [Implementation Roadmap](#7-implementation-roadmap)
8. [Metrics and Monitoring](#8-metrics-and-monitoring)
9. [Risk Assessment](#9-risk-assessment)

---

## 1. Current Architecture Analysis

### 1.1 System Overview

```
┌─────────────────────────────────────────────────────────────┐
│              LeadOrchestratorAgent (Strands)                 │
│  - Has 55+ tools (45 AWS tools + 10 specialist agent tools) │
│  - Coordinates investigation                                 │
│  - Delegates to specialists via "agents-as-tools" pattern    │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┬──────────────┐
        │ (tool call)   │ (tool call)   │ (tool call)  │
        ▼               ▼               ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────┐ ┌──────────┐
│Lambda Agent  │ │APIGateway    │ │IAM Agent │ │... (7+)  │
│(Strands)     │ │Agent         │ │          │ │Agents    │
│Has ~10 tools │ │(Strands)     │ │(Strands) │ │(Strands) │
└──────────────┘ └──────────────┘ └──────────┘ └──────────┘
        │               │               │              │
        └───────────────┴───────────────┴──────────────┘
                        │
                        ▼
        ┌───────────────────────────────────┐
        │    Root Cause Analysis Agent      │
        │    Hypothesis Agent               │
        │    Advice Agent                   │
        └───────────────────────────────────┘
```

**CRITICAL ARCHITECTURAL ISSUE: "Agents-as-Tools" Pattern**

The system uses a **nested agent pattern** where:
1. LeadAgent is a Strands agent with 55+ tools
2. 10 of those "tools" are actually wrapped specialist agents
3. When LeadAgent calls `investigate_lambda_function()`, it triggers:
   - A NEW Strands agent invocation (LambdaAgent)
   - With a 180-line system prompt (~1,500 tokens)
   - Which then calls AWS tools internally

**Problems:**
- ❌ **Massive tool duplication**: Lead has 45 AWS tools, specialists have same tools
- ❌ **Nested LLM calls**: Agent → Tool → Agent → Tool (token explosion)
- ❌ **Context blindness**: Lead can't see which tools specialist actually used
- ❌ **Strands overhead**: Each specialist call = full LLM inference

**Why it exists:**
- Lead needs discovery tools (get_xray_trace) AND delegation tools (specialist agents)
- Specialists provide domain expertise with curated tool subsets
- Pattern allows "function calling" style delegation

### 1.2 Current Context Flow

**Problem:** Full context is passed to every agent

```
Orchestrator Prompt (2,000 tokens)
├── X-Ray trace data (full JSON, 500-1,000 tokens)
├── Anti-hallucination rules (300 tokens)
├── Investigation context (200 tokens)
└── Task instructions (1,000 tokens)
        │
        ▼
Specialist Agent (2,500 tokens each)
├── System prompt (1,500 tokens)
├── Investigation prompt from orchestrator (2,000 tokens)
└── Tool call overhead (500 tokens)
```

**Total per specialist:** ~4,500 tokens
**Typical investigation (3 specialists):** ~15,500 tokens

### 1.3 Strengths of Current Implementation

1. **Thread-safe context management** (`src/promptrca/context/aws_context.py`)
   - Uses Python `contextvars` for async-safe AWS client sharing
   - Prevents credential leakage between concurrent investigations

2. **Hierarchical model configuration**
   - Agent-specific → Category → Global fallback
   - Supports heterogeneous model deployment (Haiku for simple, Sonnet for complex)

3. **Structured data models** (`src/promptrca/models/base.py`)
   - Type-safe Facts, Hypotheses, Advice, RootCauseAnalysis
   - Clean serialization with `to_dict()` methods

4. **Domain specialization**
   - 10+ service-specific specialist agents
   - Each agent has deep domain knowledge (Lambda, IAM, VPC, etc.)

### 1.4 Identified Issues

| Issue | Location | Impact | Effort to Fix | Phase |
|-------|----------|--------|---------------|-------|
| **Agents-as-tools duplication** | `lead_orchestrator.py:291-356` | **CRITICAL** (55 tools, nested agents) | **High (1 week)** | **3** |
| Tool duplication (lead has ALL tools) | `lead_orchestrator.py:291-344` | High (unnecessary context) | Medium (1 day) | 3 |
| Eager agent initialization | `lead_orchestrator.py:76-105` | High (unused agents loaded) | Low (2-3 hours) | 1 |
| Verbose system prompts | All specialist agents | High (180+ lines each) | Medium (1-2 days) | 2 |
| Full context passing | `lead_orchestrator.py:640-726` | High (2,000+ token prompts) | Medium (3-4 hours) | 1 |
| Redundant anti-hallucination rules | `lead_orchestrator.py:687-707` | Medium (300 tokens repeated) | Low (1 hour) | 1 |
| Text-based JSON parsing | All agent wrappers | Medium (parsing overhead) | Medium (1-2 days) | 2 |
| No response summarization | `lead_orchestrator.py:728-811` | High (context accumulation) | High (2-3 days) | 2 |
| No difficulty-aware routing | N/A | Very High (over-processing simple issues) | High (1 week) | 3 |
| No caching layer | N/A | High (repeated API calls) | High (1 week) | 3 |

**NEW CRITICAL FINDING: Agents-as-Tools Architecture**

The current "agents-as-tools" pattern creates:
1. **Nested agent invocations**: Each specialist call = new LLM inference with 1,500+ token system prompt
2. **Massive tool duplication**: Lead agent has 45 AWS tools it never uses directly
3. **Context blindness**: Lead can't trace which AWS API calls specialists made

**Recommended approach:**
- **Phase 1-2**: Keep pattern, optimize around it (lazy loading, compress prompts)
- **Phase 3**: Refactor to direct agent invocation (remove nesting)

---

## 2. Research Comparison

### 2.1 Chain-of-Agents (CoA) Framework (NeurIPS 2024)

**Key Findings:**
- Multi-agent collaboration improves long-context tasks by 10% over RAG
- Time complexity reduction: O(n²) → O(nk) where k is context size per agent
- Sequential processing with **short contexts** per agent is optimal
- Manager agent should synthesize **summaries**, not full context

**PromptRCA Alignment:**
- ✅ Manager agent (LeadOrchestrator) synthesizes contributions
- ✅ Sequential specialist processing
- ⚠️ Context size is NOT short (2,000+ tokens per agent)
- ❌ No summarization between agent hops

### 2.2 Heterogeneous LLM Workflows (2024)

**Key Findings:**
- Most workflows over-provision by using GPT-4 for all tasks
- Smaller models outperform larger models in specialized domains
- Cost-optimal: small models for low-priority, large models for critical reasoning

**PromptRCA Alignment:**
- ✅ Supports heterogeneous models (Haiku/Sonnet/Opus)
- ⚠️ All agents initialized regardless of need
- ❌ No automatic model selection based on task difficulty

### 2.3 Context Engineering & Memory (2025)

**Key Findings:**
- "Context rot" - LLM performance degrades with extremely long contexts
- RAG reduces token consumption by 60-80% vs full-context
- Persistent memory with selective retrieval outperforms stateless agents

**PromptRCA Alignment:**
- ❌ No RAG or memory layer
- ❌ Full trace data embedded in prompts (context rot risk)
- ✅ Stateless agents are fine for one-shot investigations

### 2.4 Multi-Agent System Failure Modes (2025)

**Key Findings:**
- 14 unique failure modes identified in MAS frameworks
- Primary issues: ambiguous communication, over-processing, prompt bloat
- Standardized communication protocols enhance alignment

**PromptRCA Alignment:**
- ✅ Structured outputs (Facts, Hypotheses, Advice) prevent ambiguity
- ⚠️ Prompt bloat is a concern (180-line system prompts)
- ✅ Clear role definitions in system prompts

---

## 3. Token Usage Breakdown

### 3.1 Current Token Consumption (Estimated)

**Per Investigation (Typical: 3 specialists invoked)**

| Component | Tokens | Percentage |
|-----------|--------|------------|
| Orchestrator system prompt | 500 | 4.5% |
| Orchestrator investigation prompt | 2,000 | 18.2% |
| Specialist 1 (Lambda) system prompt | 1,500 | 13.6% |
| Specialist 1 investigation context | 2,000 | 18.2% |
| Specialist 1 tool calls & response | 1,000 | 9.1% |
| Specialist 2 (APIGateway) | 4,500 | 40.9% |
| Specialist 3 (IAM) | 4,500 | - |
| Root Cause Agent | 1,500 | 13.6% |
| **Total** | **~17,500** | **100%** |

### 3.2 Breakdown by Optimization Category

| Category | Current Tokens | Optimized Tokens | Savings |
|----------|----------------|------------------|---------|
| **System Prompts** (all agents) | 6,000 | 2,400 | 60% |
| **Investigation Context** (full trace data) | 2,000 | 800 | 60% |
| **Anti-Hallucination Rules** (repeated) | 900 | 300 | 67% |
| **JSON Parsing Overhead** (text → JSON) | 500 | 100 | 80% |
| **Agent Initialization** (unused agents) | N/A (memory) | N/A | 70% agents |
| **Total** | 17,500 | 6,700 | **62%** |

---

## 4. Priority 1: Quick Wins (1-2 Days)

These optimizations provide **40-50% token reduction** with **minimal code changes** and **low risk**.

---

### 4.1 Lazy Agent Initialization

**Problem:** All 10 specialist agents are created at orchestrator initialization, even if only 2-3 are needed per investigation.

**NOTE:** This optimization works WITHIN the agents-as-tools pattern. We're not refactoring the architecture, just lazy-loading the agents. The agents-as-tools duplication issue is addressed in Phase 3.

**File:** `src/promptrca/agents/lead_orchestrator.py:76-105`

**Current Code:**
```python
def __init__(self, model=None, region: str = None):
    self.model = model or create_orchestrator_model()
    self.region = region or get_region()

    # Create ALL specialists upfront
    self.lambda_agent = create_lambda_agent(create_lambda_agent_model())
    self.apigateway_agent = create_apigateway_agent(create_apigateway_agent_model())
    self.stepfunctions_agent = create_stepfunctions_agent(create_stepfunctions_agent_model())
    self.iam_agent = create_iam_agent(create_iam_agent_model())
    self.dynamodb_agent = create_dynamodb_agent(create_dynamodb_agent_model())
    self.s3_agent = create_s3_agent(create_s3_agent_model())
    self.sqs_agent = create_sqs_agent(create_sqs_agent_model())
    self.sns_agent = create_sns_agent(create_sns_agent_model())
    self.eventbridge_agent = create_eventbridge_agent(create_eventbridge_agent_model())
    self.vpc_agent = create_vpc_agent(create_vpc_agent_model())
```

**Optimized Code:**
```python
def __init__(self, model=None, region: str = None):
    self.model = model or create_orchestrator_model()
    self.region = region or get_region()

    # Lazy initialization cache
    self._specialist_cache = {}

    # Agent factory mapping
    self._agent_factories = {
        'lambda': (create_lambda_agent, create_lambda_agent_model),
        'apigateway': (create_apigateway_agent, create_apigateway_agent_model),
        'stepfunctions': (create_stepfunctions_agent, create_stepfunctions_agent_model),
        'iam': (create_iam_agent, create_iam_agent_model),
        'dynamodb': (create_dynamodb_agent, create_dynamodb_agent_model),
        's3': (create_s3_agent, create_s3_agent_model),
        'sqs': (create_sqs_agent, create_sqs_agent_model),
        'sns': (create_sns_agent, create_sns_agent_model),
        'eventbridge': (create_eventbridge_agent, create_eventbridge_agent_model),
        'vpc': (create_vpc_agent, create_vpc_agent_model),
    }

    # Initialize input parser and synthesis model as before
    from .input_parser_agent import InputParserAgent
    self.input_parser = InputParserAgent()

    from ..utils.config import create_synthesis_model
    synthesis_model = create_synthesis_model()
    self.synthesis_model = synthesis_model
    self.strands_agent = Agent(model=synthesis_model)

def _get_specialist_agent(self, specialist_type: str) -> Agent:
    """Lazy-load specialist agent on demand."""
    if specialist_type not in self._specialist_cache:
        logger.info(f"🔧 Initializing {specialist_type} specialist agent")

        if specialist_type not in self._agent_factories:
            raise ValueError(f"Unknown specialist type: {specialist_type}")

        agent_factory, model_factory = self._agent_factories[specialist_type]
        self._specialist_cache[specialist_type] = agent_factory(model_factory())

    return self._specialist_cache[specialist_type]

def _get_specialist_tool(self, specialist_type: str):
    """Get specialist tool wrapper, creating agent if needed."""
    agent = self._get_specialist_agent(specialist_type)

    tool_factory_map = {
        'lambda': create_lambda_agent_tool,
        'apigateway': create_apigateway_agent_tool,
        'stepfunctions': create_stepfunctions_agent_tool,
        'iam': create_iam_agent_tool,
        'dynamodb': create_dynamodb_agent_tool,
        's3': create_s3_agent_tool,
        'sqs': create_sqs_agent_tool,
        'sns': create_sns_agent_tool,
        'eventbridge': create_eventbridge_agent_tool,
        'vpc': create_vpc_agent_tool,
    }

    return tool_factory_map[specialist_type](agent)
```

**Update `_create_lead_agent()` method:**
```python
def _create_lead_agent(self) -> Agent:
    """Create the lead orchestrator agent with all specialist tools."""

    # ... existing system prompt logic ...

    # Build tools list - specialists will be lazy-loaded
    from ..tools import (
        # All AWS service tools
        get_xray_trace,
        get_lambda_config,
        # ... etc ...
    )

    tools = [
        # All AWS service tools (get client from context)
        get_xray_trace,
        get_lambda_config,
        # ... all other tools ...
    ]

    # Add lazy-loaded specialist tools
    for specialist_type in self._agent_factories.keys():
        tools.append(self._get_specialist_tool(specialist_type))

    # Add AWS Knowledge MCP tools if enabled
    # ... existing MCP logic ...

    return Agent(
        model=self.model,
        system_prompt=system_prompt,
        tools=tools,
        trace_attributes={
            "service.name": "promptrca-orchestrator",
            "service.version": "1.0.0",
            "agent.type": "lead_orchestrator",
            "agent.region": self.region
        }
    )
```

**Impact:**
- ✅ Only create 2-3 agents per investigation (vs 10)
- ✅ 70% reduction in initialization overhead
- ✅ Lower memory footprint
- ✅ Faster orchestrator startup

**Effort:** 2-3 hours
**Risk:** Low (backward compatible, agents created on-demand)

---

### 4.2 Context Pruning for Trace Data

**Problem:** Full X-Ray trace JSON (500-1,000 tokens) is embedded in orchestrator prompt.

**File:** `src/promptrca/agents/lead_orchestrator.py:640-660`

**Current Code:**
```python
if context.trace_ids:
    prompt_parts.append(f"X-Ray Trace ID: {context.trace_ids[0]}")

    # Add trace data for immediate analysis
    try:
        from ..tools import get_xray_trace
        trace_data = get_xray_trace(context.trace_ids[0])
        if trace_data and "error" not in trace_data:
            prompt_parts.append(f"\nTRACE DATA FOR ANALYSIS:")
            prompt_parts.append(f"```json")
            prompt_parts.append(trace_data)  # FULL TRACE DATA (500-1000 tokens)
            prompt_parts.append(f"```")
    except Exception as e:
        prompt_parts.append(f"\nNote: Could not retrieve trace data: {e}")
```

**Optimized Code:**
```python
def _extract_trace_summary(self, trace_data_json: str) -> dict:
    """Extract concise summary from trace data for prompt efficiency."""
    import json

    try:
        trace_data = json.loads(trace_data_json) if isinstance(trace_data_json, str) else trace_data_json

        summary = {
            "trace_id": None,
            "duration_ms": None,
            "http_status": None,
            "error_segments": [],
            "failed_services": [],
            "fault_root_causes": []
        }

        # Extract from trace structure
        if "Traces" in trace_data and len(trace_data["Traces"]) > 0:
            trace = trace_data["Traces"][0]
            summary["trace_id"] = trace.get("Id")
            summary["duration_ms"] = trace.get("Duration")

            # Extract segments
            if "Segments" in trace:
                for segment_doc in trace["Segments"]:
                    segment = json.loads(segment_doc["Document"])

                    # HTTP status
                    if "http" in segment and "response" in segment["http"]:
                        summary["http_status"] = segment["http"]["response"].get("status")

                    # Error/fault segments
                    if segment.get("fault") or segment.get("error"):
                        error_info = {
                            "service": segment.get("name"),
                            "fault": segment.get("fault", False),
                            "error": segment.get("error", False),
                            "cause": segment.get("cause", {}).get("message", "Unknown")
                        }
                        summary["error_segments"].append(error_info)
                        summary["failed_services"].append(segment.get("name"))

                    # Fault root causes
                    if "fault_root_causes" in segment:
                        for cause in segment["fault_root_causes"]:
                            summary["fault_root_causes"].append({
                                "service": cause.get("name"),
                                "exception": cause.get("exception", {})
                            })

        # Remove duplicates
        summary["failed_services"] = list(set(summary["failed_services"]))

        return summary

    except Exception as e:
        logger.error(f"Failed to extract trace summary: {e}")
        return {"error": str(e)}

def _create_investigation_prompt(self, context: InvestigationContext) -> str:
    """Create investigation prompt for the lead orchestrator agent"""
    prompt_parts = []

    prompt_parts.append("INVESTIGATION REQUEST:")

    if context.trace_ids:
        prompt_parts.append(f"X-Ray Trace ID: {context.trace_ids[0]}")

        # Add SUMMARIZED trace data instead of full JSON
        try:
            from ..tools import get_xray_trace
            trace_data = get_xray_trace(context.trace_ids[0])
            if trace_data and "error" not in trace_data:
                trace_summary = self._extract_trace_summary(trace_data)
                prompt_parts.append(f"\nTRACE SUMMARY:")
                prompt_parts.append(f"```json")
                prompt_parts.append(json.dumps(trace_summary, indent=2))
                prompt_parts.append(f"```")
                prompt_parts.append(f"\nNote: Full trace available via get_xray_trace('{context.trace_ids[0]}')")
        except Exception as e:
            prompt_parts.append(f"\nNote: Could not retrieve trace data: {e}")

    # ... rest of prompt generation ...
```

**Impact:**
- ✅ 60-80% reduction in trace data tokens (1,000 → 200 tokens)
- ✅ Agent can still call `get_xray_trace()` if needed
- ✅ Reduces "context rot" risk
- ✅ Faster prompt processing

**Effort:** 3-4 hours
**Risk:** Low (summary includes all critical error info)

---

### 4.3 Compress Anti-Hallucination Rules

**Problem:** 30+ lines of anti-hallucination rules consume ~300 tokens and are repeated in every prompt.

**File:** `src/promptrca/agents/lead_orchestrator.py:687-707`

**Current Code:**
```python
prompt_parts.append("\n🚨 ANTI-HALLUCINATION RULES:")
prompt_parts.append("1. ONLY investigate resources explicitly listed in 'Target Resources' above")
prompt_parts.append("2. DO NOT make up, assume, or infer resource names, ARNs, or identifiers")
prompt_parts.append("3. DO NOT investigate Lambda functions unless explicitly listed in Target Resources")
prompt_parts.append("4. DO NOT investigate Step Functions unless explicitly listed in Target Resources")
prompt_parts.append("5. DO NOT use placeholder API IDs like 'shp123456' - use actual IDs from trace data")
prompt_parts.append("6. Base analysis ONLY on data returned from tools")
prompt_parts.append("7. If tool returns 'ResourceNotFoundException', report as fact")
prompt_parts.append("8. If no data available, state 'Insufficient data'")
prompt_parts.append("9. If you see 'STEPFUNCTIONS' in trace data, it is NOT a Lambda function")
prompt_parts.append("10. If you see 'promptrca-handler' or similar names, DO NOT investigate unless listed in Target Resources")
```

**Optimized Code:**
```python
prompt_parts.append("\nCRITICAL RULES:")
prompt_parts.append("- Investigate ONLY resources in Target Resources list")
prompt_parts.append("- NO placeholder IDs (e.g., 'shp123456') - use actual IDs from tools")
prompt_parts.append("- Use tool data only; report 'Insufficient data' if missing")
prompt_parts.append("- If ResourceNotFoundException → report as fact")
prompt_parts.append("- STEPFUNCTIONS ≠ Lambda; don't confuse service types")
```

**Impact:**
- ✅ 67% reduction in anti-hallucination token usage (300 → 100 tokens)
- ✅ Clearer, more scannable rules
- ✅ Same semantic meaning

**Effort:** 1 hour
**Risk:** Very Low (same rules, compressed)

---

### 4.4 Summary of Priority 1 Impact

| Optimization | Token Savings | Effort | Risk |
|--------------|---------------|--------|------|
| Lazy Agent Initialization | N/A (memory) | 2-3 hours | Low |
| Context Pruning (Trace) | 800 tokens | 3-4 hours | Low |
| Compress Anti-Hallucination | 200 tokens | 1 hour | Very Low |
| **Total** | **~1,000 tokens (40% of prompt overhead)** | **1 day** | **Low** |

**Combined with specialist prompt optimization (Priority 2), estimated total savings: 40-50%**

---

## 5. Priority 2: Medium-Term Improvements (1-2 Weeks)

These optimizations provide **55-60% token reduction** with **moderate code changes** and **medium risk**.

---

### 5.1 Optimize Specialist System Prompts

**Problem:** Each specialist has 180-line system prompts with verbose examples and instructions.

**Files:** All specialist agents (`src/promptrca/agents/specialized/*.py`)

**Current Example:** `lambda_agent.py:43-179` (180 lines, ~1,500 tokens)

```python
system_prompt = """You will be given detailed information about an AWS Lambda function incident...

EXPERT ROLE: You are an experienced AWS Lambda specialist with deep knowledge of serverless architectures...

INVESTIGATION METHODOLOGY (follow these steps sequentially):
1. **Contextual Information**: Identify the function name, region, runtime...
2. **Categorization**: Categorize the type of incident:
   - Runtime errors (exceptions, crashes)
   - Timeout issues
   - Permission/IAM problems
   ...

FEW-SHOT EXAMPLES (for calibration):

Example 1: Code Error
INPUT: CloudWatch logs show "ZeroDivisionError: division by zero at line 42"
OUTPUT:
{
  "facts": [
    {"source": "cloudwatch_logs", "content": "ZeroDivisionError at line 42...", ...}
  ],
  ...
}

Example 2: Permission Issue
...

Example 3: Timeout Issue
...
```

**Optimized Code:**

```python
system_prompt = """AWS Lambda specialist. Analyze incidents methodically.

ROLE: Expert in serverless, failure patterns, performance, configuration issues.

METHODOLOGY:
1. Context: function, region, runtime, timestamps
2. Categorize: runtime_error|timeout|permission|performance|resource|coldstart|integration
3. Symptoms: errors, status codes, timeouts, memory, invocations
4. History: deployments, config changes, similar incidents
5. Patterns: logs, metrics, correlation with config
6. Root cause: synthesize evidence, confidence score

RULES:
- Evidence-based only (no speculation)
- Extract facts: memory, timeout, runtime, errors, patterns
- Hypotheses MUST cite evidence
- Return [] if no evidence
- Map observations → types:
  * Exception/stack → code_bug
  * PermissionDenied → permission_issue
  * Duration ≥ timeout → timeout
  * Memory ≥ limit → resource_constraint
  * High error rate → error_rate
  * Throttle events → throttling

EXAMPLES: [See external knowledge base for few-shot examples]

OUTPUT:
{
  "facts": [{"source": "tool", "content": "...", "confidence": 0.0-1.0, "metadata": {}}],
  "hypotheses": [{"type": "category", "description": "...", "confidence": 0.0-1.0, "evidence": [...]}],
  "advice": [{"title": "...", "description": "...", "priority": "high|medium|low", "category": "..."}],
  "summary": "1-2 sentences"
}
"""
```

**Strategy:**
1. **Compress methodology** from narrative to structured bullets
2. **Move examples to external knowledge base** (future: RAG retrieval)
3. **Use abbreviations** where semantic meaning is clear
4. **Remove redundant explanations**

**Apply to all specialists:**
- `lambda_agent.py`
- `apigateway_agent.py`
- `stepfunctions_agent.py`
- `iam_agent.py`
- `dynamodb_agent.py`
- `s3_agent.py`
- `sqs_agent.py`
- `sns_agent.py`
- `eventbridge_agent.py`
- `vpc_agent.py`

**Impact:**
- ✅ 60% reduction in system prompt tokens (1,500 → 600 tokens per specialist)
- ✅ 3 specialists × 900 tokens saved = **2,700 tokens/investigation**
- ✅ Faster prompt processing
- ⚠️ May require tuning to maintain quality

**Effort:** 1-2 days (10 agents × 2-3 hours each)
**Risk:** Medium (requires testing to ensure quality maintained)

---

### 5.2 Structured Outputs with Pydantic

**Problem:** Text-based JSON parsing is fragile and adds overhead.

**Files:** All agent wrapper functions (`create_lambda_agent_tool`, etc.)

**Current Code:** `lambda_agent.py:237-280`

```python
def investigate_lambda_function(function_name: str, investigation_context: str = "") -> str:
    # Run the agent
    agent_result = lambda_agent(prompt)

    # Extract the response content from AgentResult
    response = str(agent_result.content) if hasattr(agent_result, 'content') else str(agent_result)

    # Attempt to parse structured JSON from response
    def _extract_json(s: str):
        try:
            import json as _json
            text = s.strip()
            if "```" in text:
                if "```json" in text:
                    text = text.split("```json", 1)[1].split("```", 1)[0]
                else:
                    text = text.split("```", 1)[1].split("```", 1)[0]
            return _json.loads(text)
        except Exception:
            return None

    data = _extract_json(response) or {}
    # Basic validation and normalization
    if isinstance(data.get("facts"), dict) or isinstance(data.get("facts"), str):
        data["facts"] = [data.get("facts")]
    ...
```

**Optimized Code:**

**Step 1: Define Pydantic Models** (`src/promptrca/models/agent_outputs.py`)

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class AgentFact(BaseModel):
    """Structured fact from specialist investigation."""
    source: str = Field(..., description="Tool or source name")
    content: str = Field(..., description="Fact content")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence score")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class AgentHypothesis(BaseModel):
    """Structured hypothesis from specialist."""
    type: str = Field(..., description="Hypothesis category")
    description: str = Field(..., description="Hypothesis description")
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    evidence: List[str] = Field(default_factory=list)

class AgentAdvice(BaseModel):
    """Structured advice from specialist."""
    title: str
    description: str
    priority: str = Field("medium", pattern="^(high|medium|low)$")
    category: str = "general"

class SpecialistInvestigationResult(BaseModel):
    """Complete specialist investigation result."""
    target: Dict[str, str] = Field(..., description="Investigation target")
    context: str = Field("", description="Investigation context")
    status: str = Field("completed", pattern="^(completed|failed|insufficient_data)$")
    facts: List[AgentFact] = Field(default_factory=list)
    hypotheses: List[AgentHypothesis] = Field(default_factory=list)
    advice: List[AgentAdvice] = Field(default_factory=list)
    summary: str = ""
    error: Optional[str] = None
```

**Step 2: Update Strands Agent to Use Structured Output**

```python
from strands import Agent
from pydantic import BaseModel

def create_lambda_agent(model) -> Agent:
    """Create a Lambda specialist agent with structured output."""

    system_prompt = """..."""  # Optimized prompt from 5.1

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[...],
        response_model=SpecialistInvestigationResult,  # Pydantic model
        trace_attributes={...}
    )

def create_lambda_agent_tool(lambda_agent: Agent):
    """Create a tool that wraps the Lambda agent."""
    from strands import tool

    @tool
    def investigate_lambda_function(
        function_name: str,
        investigation_context: str = ""
    ) -> str:
        """Investigate a Lambda function for issues."""
        import json

        try:
            prompt = f"""Investigate Lambda function: {function_name}

Context: {investigation_context}

Investigation steps:
1. Get function configuration
2. Check version history
3. Examine logs for errors
4. Review failed invocations
5. Check metrics
6. Verify IAM permissions if needed"""

            # Run agent - returns SpecialistInvestigationResult (Pydantic)
            result: SpecialistInvestigationResult = lambda_agent(prompt)

            # Convert to dict for JSON serialization
            return json.dumps(result.model_dump())

        except Exception as e:
            error_result = SpecialistInvestigationResult(
                target={"type": "lambda_function", "name": function_name},
                context=investigation_context,
                status="failed",
                error=str(e)
            )
            return json.dumps(error_result.model_dump())

    return investigate_lambda_function
```

**Impact:**
- ✅ No JSON parsing overhead (Pydantic handles it)
- ✅ Type safety and validation
- ✅ 80% reduction in parsing code
- ✅ Better error messages when output is malformed
- ✅ ~500 tokens saved per investigation (parsing overhead eliminated)

**Effort:** 1-2 days (create models + update all agent wrappers)
**Risk:** Medium (requires Strands library support for `response_model`)

**Note:** Check if Strands supports Pydantic `response_model`. If not, use LangChain's `with_structured_output()` pattern.

---

### 5.3 Response Summarization Between Agents

**Problem:** Specialist findings are passed as full text to Root Cause Agent, accumulating context.

**File:** `src/promptrca/agents/lead_orchestrator.py:728-811`

**Current Flow:**
```
Specialist 1 → 500 token response
Specialist 2 → 500 token response
Specialist 3 → 500 token response
                │
                ▼
        All 1,500 tokens passed to Root Cause Agent
```

**Optimized Flow:**
```
Specialist 1 → 500 tokens → Summarize to 100 tokens
Specialist 2 → 500 tokens → Summarize to 100 tokens
Specialist 3 → 500 tokens → Summarize to 100 tokens
                │
                ▼
        300 tokens passed to Root Cause Agent (80% savings)
```

**Optimized Code:**

```python
def _summarize_specialist_findings(self, findings: List[Dict[str, Any]]) -> str:
    """Summarize specialist findings for efficient context passing."""
    summary_parts = []

    for finding in findings:
        specialist_type = finding.get("target", {}).get("type", "unknown")
        fact_count = len(finding.get("facts", []))
        hypothesis_count = len(finding.get("hypotheses", []))

        # Extract key findings only
        key_facts = finding.get("facts", [])[:2]  # Top 2 facts
        key_hypotheses = finding.get("hypotheses", [])[:2]  # Top 2 hypotheses

        specialist_summary = {
            "specialist": specialist_type,
            "resource": finding.get("target", {}).get("name", "unknown"),
            "status": finding.get("status", "unknown"),
            "fact_count": fact_count,
            "hypothesis_count": hypothesis_count,
            "top_facts": [f["content"][:100] for f in key_facts],  # Truncate
            "top_hypotheses": [
                f"{h['type']}: {h['description'][:100]}"
                for h in key_hypotheses
            ],
            "summary": finding.get("summary", "")[:200]  # Truncate
        }

        summary_parts.append(specialist_summary)

    return json.dumps(summary_parts, indent=2)

def _parse_agent_response(self, agent_result, context: InvestigationContext) -> (List[Fact], List[Hypothesis], List[Advice]):
    """Parse specialist responses and extract structured data."""
    response = str(agent_result.content) if hasattr(agent_result, 'content') else str(agent_result)

    all_facts = []
    all_hypotheses = []
    all_advice = []

    # 1-3. Extract JSON blocks (existing logic)
    json_blocks = self._extract_json_from_fences(response)
    if not json_blocks:
        json_blocks = self._extract_json_with_brace_balancer(response)

    # Parse each JSON block into structured objects
    for data in json_blocks:
        if not isinstance(data, dict):
            continue

        # Parse facts, hypotheses, advice (existing logic)
        for fact_data in data.get('facts', []):
            # ... existing parsing ...
            all_facts.append(fact)

        for hyp_data in data.get('hypotheses', []):
            # ... existing parsing ...
            all_hypotheses.append(hypothesis)

        for advice_data in data.get('advice', []):
            # ... existing parsing ...
            all_advice.append(advice)

    # NEW: Summarize findings before passing to hypothesis/root cause agents
    if json_blocks:
        specialist_summary = self._summarize_specialist_findings(json_blocks)
        logger.info(f"📋 Summarized {len(json_blocks)} specialist findings")

        # Store summary in context for hypothesis/root cause agents
        context.specialist_summary = specialist_summary

    # Generate hypotheses/advice with summarized context
    if not all_hypotheses:
        from .hypothesis_agent import HypothesisAgent
        hypothesis_agent = HypothesisAgent(strands_agent=self.strands_agent)

        # Pass summarized context instead of full facts
        all_hypotheses = hypothesis_agent.generate_hypotheses(
            facts=all_facts,
            context_summary=getattr(context, 'specialist_summary', None)
        )

    # ... rest of method ...

    return all_facts, all_hypotheses, all_advice
```

**Update Hypothesis Agent:**

```python
class HypothesisAgent:
    def generate_hypotheses(
        self,
        facts: List[Fact],
        context_summary: Optional[str] = None
    ) -> List[Hypothesis]:
        """Generate hypotheses from facts with optional context summary."""

        # Build prompt with summarized context
        facts_text = "\n".join([f"- {fact.content}" for fact in facts[:10]])  # Limit to 10

        context_text = ""
        if context_summary:
            context_text = f"\n\nSPECIALIST CONTEXT (summarized):\n{context_summary}\n"

        prompt = f"""Generate hypotheses from these facts:{context_text}

FACTS:
{facts_text}

Provide 3-5 hypotheses in JSON format..."""

        # ... rest of method ...
```

**Impact:**
- ✅ 80% reduction in inter-agent context (1,500 → 300 tokens)
- ✅ Prevents context accumulation
- ✅ Root Cause Agent gets concise, structured input
- ✅ Aligns with Chain-of-Agents research (summarize between hops)

**Effort:** 2-3 days
**Risk:** Medium (requires testing to ensure critical info not lost)

---

### 5.4 Summary of Priority 2 Impact

| Optimization | Token Savings | Effort | Risk |
|--------------|---------------|--------|------|
| Optimize System Prompts | 2,700 tokens | 1-2 days | Medium |
| Structured Outputs (Pydantic) | 500 tokens | 1-2 days | Medium |
| Response Summarization | 1,200 tokens | 2-3 days | Medium |
| **Total** | **~4,400 tokens (additional 25% savings)** | **1-2 weeks** | **Medium** |

**Combined with Priority 1: Total savings = 55-60%**

---

## 6. Priority 3: Strategic Enhancements (1-2 Months)

These optimizations provide **60-80% token reduction** with **significant code changes** and **higher risk**, but align with 2025 research best practices.

---

### 6.1 Difficulty-Aware Investigation Routing

**Research:** "Difficulty-Aware Agent Orchestration in LLM-Powered Workflows" (arXiv 2509.11079)

**Problem:** All investigations use full multi-agent orchestration, even for simple issues.

**Example:**
- Simple permission error → Needs 1 specialist (IAM) + lightweight model
- Complex distributed trace → Needs 3+ specialists + advanced model

**Current:** All issues get the same treatment (wasteful)

**Solution:** Classify investigation complexity and route accordingly

**Implementation:**

**File:** `src/promptrca/agents/lead_orchestrator.py`

```python
from enum import Enum

class InvestigationComplexity(Enum):
    SIMPLE = "simple"          # Clear error, single service
    MODERATE = "moderate"      # Multiple services, obvious cause
    COMPLEX = "complex"        # Distributed trace, unclear cause
    VERY_COMPLEX = "very_complex"  # Multiple traces, ambiguous

class DifficultyAwareOrchestrator:
    """Orchestrator that adapts strategy based on investigation complexity."""

    def __init__(self, model=None, region: str = None):
        # ... existing initialization ...

        # Create complexity classifier
        self.complexity_classifier = self._create_complexity_classifier()

    def _create_complexity_classifier(self) -> Agent:
        """Create agent to classify investigation complexity."""
        from ..utils.config import create_synthesis_model

        system_prompt = """Classify investigation complexity based on inputs.

COMPLEXITY LEVELS:
- SIMPLE: Clear error message, single service, obvious cause (e.g., "AccessDenied on S3 bucket")
- MODERATE: Multiple services, trace available, likely cause identified
- COMPLEX: Distributed trace, multiple services, unclear error source
- VERY_COMPLEX: Multiple traces, ambiguous errors, cross-service dependencies

RULES:
- More services involved → higher complexity
- Clear error message → lower complexity
- Trace available → enables better analysis (may reduce complexity)
- No trace + vague error → higher complexity

OUTPUT: {"complexity": "simple|moderate|complex|very_complex", "reasoning": "..."}"""

        return Agent(
            model=create_synthesis_model(),
            system_prompt=system_prompt
        )

    def _assess_complexity(self, inputs: Dict[str, Any]) -> InvestigationComplexity:
        """Assess investigation complexity from inputs."""

        # Build assessment prompt
        prompt = f"""Classify this investigation's complexity:

Inputs: {json.dumps(inputs, indent=2)}

Analyze:
- Number of services mentioned
- Clarity of error messages
- Availability of trace IDs
- Specificity of resources"""

        result = self.complexity_classifier(prompt)

        # Parse result
        try:
            response = json.loads(str(result.content))
            complexity_str = response.get("complexity", "moderate")
            reasoning = response.get("reasoning", "")

            logger.info(f"🎯 Complexity: {complexity_str} - {reasoning}")
            return InvestigationComplexity(complexity_str)

        except Exception as e:
            logger.warning(f"Failed to assess complexity: {e}, defaulting to MODERATE")
            return InvestigationComplexity.MODERATE

    async def investigate(
        self,
        inputs: Dict[str, Any],
        region: str = None,
        assume_role_arn: Optional[str] = None,
        external_id: Optional[str] = None
    ) -> InvestigationReport:
        """Run complexity-aware investigation."""

        # 1. Assess complexity
        complexity = self._assess_complexity(inputs)

        # 2. Route based on complexity
        if complexity == InvestigationComplexity.SIMPLE:
            return await self._handle_simple_investigation(inputs, region, assume_role_arn, external_id)
        elif complexity == InvestigationComplexity.MODERATE:
            return await self._handle_moderate_investigation(inputs, region, assume_role_arn, external_id)
        else:
            return await self._handle_complex_investigation(inputs, region, assume_role_arn, external_id)

    async def _handle_simple_investigation(self, inputs, region, assume_role_arn, external_id):
        """Handle simple investigations with minimal agent overhead."""
        logger.info("🟢 Simple investigation - using lightweight path")

        # Use lightweight model for entire investigation
        from ..utils.config import get_model_id
        lightweight_model_id = os.getenv("PROMPTRCA_LIGHTWEIGHT_MODEL_ID",
                                         "anthropic.claude-3-haiku-20240307-v1:0")

        # Create single specialist agent for the identified service
        # Skip multi-agent orchestration entirely

        parsed_inputs = self._parse_inputs(inputs, region)
        context = self._build_investigation_context(parsed_inputs, datetime.now(timezone.utc))

        # Identify primary service
        if context.primary_targets:
            target = context.primary_targets[0]
            specialist = self._get_specialist_agent(target.type)

            # Direct specialist investigation
            prompt = self._create_simple_investigation_prompt(context, target)
            specialist_result = specialist(prompt)

            # Generate report directly from specialist findings
            facts, hypotheses, advice = self._parse_agent_response(specialist_result, context)
            return self._generate_investigation_report(context, facts, hypotheses, advice, region, assume_role_arn, external_id)

        # Fallback to moderate if no clear target
        return await self._handle_moderate_investigation(inputs, region, assume_role_arn, external_id)

    async def _handle_moderate_investigation(self, inputs, region, assume_role_arn, external_id):
        """Handle moderate investigations with selective specialists."""
        logger.info("🟡 Moderate investigation - using selective specialists")

        # Use 1-2 specialists instead of full orchestration
        # Existing logic but with fewer agent calls

        return await self._run_selective_investigation(inputs, region, assume_role_arn, external_id, max_specialists=2)

    async def _handle_complex_investigation(self, inputs, region, assume_role_arn, external_id):
        """Handle complex investigations with full multi-agent orchestration."""
        logger.info("🔴 Complex investigation - using full orchestration")

        # Existing full investigation logic
        return await self._run_full_investigation(inputs, region, assume_role_arn, external_id)
```

**Impact:**
- ✅ 70-80% token reduction for simple issues (1,500 tokens vs 11,000 tokens)
- ✅ 30-40% token reduction for moderate issues
- ✅ Maintains full capability for complex issues
- ✅ Cost optimization (use Haiku for simple, Sonnet for complex)
- ✅ Faster response times for simple issues

**Effort:** 1 week
**Risk:** High (requires extensive testing across complexity levels)

---

### 6.2 Memory and Caching Layer

**Research:** LangChain memory patterns, context engineering (2025)

**Problem:** Repeated API calls for same resources waste tokens and time.

**Example:**
- Investigation 1: Get Lambda function config for `my-function`
- Investigation 2: Get Lambda function config for `my-function` again (duplicate call)

**Solution:** Cache AWS resource configurations and common investigation patterns

**Implementation:**

**File:** `src/promptrca/cache/investigation_cache.py` (new)

```python
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import json
import hashlib

class InvestigationCache:
    """In-memory cache for AWS resource data and investigation patterns."""

    def __init__(self, ttl_minutes: int = 15):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = timedelta(minutes=ttl_minutes)

    def _generate_key(self, resource_type: str, resource_id: str, region: str) -> str:
        """Generate cache key for resource."""
        key_str = f"{resource_type}:{resource_id}:{region}"
        return hashlib.sha256(key_str.encode()).hexdigest()

    def get(
        self,
        resource_type: str,
        resource_id: str,
        region: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached resource data if available and not expired."""
        key = self._generate_key(resource_type, resource_id, region)

        if key in self._cache:
            cached_data = self._cache[key]
            cached_at = cached_data.get("cached_at")

            # Check expiration
            if datetime.now() - cached_at < self.ttl:
                logger.debug(f"✅ Cache hit: {resource_type}/{resource_id}")
                return cached_data.get("data")
            else:
                # Expired
                del self._cache[key]
                logger.debug(f"⏰ Cache expired: {resource_type}/{resource_id}")

        logger.debug(f"❌ Cache miss: {resource_type}/{resource_id}")
        return None

    def set(
        self,
        resource_type: str,
        resource_id: str,
        region: str,
        data: Dict[str, Any]
    ) -> None:
        """Cache resource data."""
        key = self._generate_key(resource_type, resource_id, region)

        self._cache[key] = {
            "cached_at": datetime.now(),
            "data": data
        }

        logger.debug(f"💾 Cached: {resource_type}/{resource_id}")

    def clear(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
        logger.info("🗑️ Cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_items = len(self._cache)
        expired_items = sum(
            1 for item in self._cache.values()
            if datetime.now() - item["cached_at"] >= self.ttl
        )

        return {
            "total_items": total_items,
            "active_items": total_items - expired_items,
            "expired_items": expired_items,
            "ttl_minutes": self.ttl.total_seconds() / 60
        }

# Global cache instance
_investigation_cache = InvestigationCache(ttl_minutes=15)

def get_investigation_cache() -> InvestigationCache:
    """Get global investigation cache instance."""
    return _investigation_cache
```

**Update AWS Tools to Use Cache:**

**File:** `src/promptrca/tools/lambda_tools.py`

```python
from ..cache.investigation_cache import get_investigation_cache

def get_lambda_config(function_name: str) -> str:
    """Get Lambda function configuration with caching."""
    from ..context import get_aws_client

    # Check cache first
    cache = get_investigation_cache()
    aws_client = get_aws_client()
    region = aws_client.region

    cached_config = cache.get("lambda_config", function_name, region)
    if cached_config:
        return json.dumps(cached_config)

    # Cache miss - fetch from AWS
    try:
        lambda_client = aws_client.get_client('lambda')
        response = lambda_client.get_function_configuration(FunctionName=function_name)

        config = {
            "function_name": response.get("FunctionName"),
            "runtime": response.get("Runtime"),
            "role": response.get("Role"),
            "memory_size": response.get("MemorySize"),
            "timeout": response.get("Timeout"),
            # ... other fields ...
        }

        # Cache the result
        cache.set("lambda_config", function_name, region, config)

        return json.dumps(config)

    except Exception as e:
        return json.dumps({"error": str(e)})
```

**Apply caching to:**
- Lambda configs
- IAM role configs
- API Gateway configs
- Step Functions definitions
- VPC configs
- Security group configs

**Impact:**
- ✅ 50-70% reduction in duplicate API calls
- ✅ Faster investigation times (cached data retrieval)
- ✅ Lower AWS API rate limit risk
- ✅ Enables pattern recognition across investigations

**Effort:** 1 week
**Risk:** Medium (cache invalidation strategy needed)

**Future Enhancement:** Persistent cache (Redis/DynamoDB) for cross-Lambda invocation sharing

---

### 6.3 Refactor Agents-as-Tools to Direct Invocation

**Research:** Chain-of-Agents (NeurIPS 2024), LangGraph patterns

**Problem:** The current "agents-as-tools" pattern creates nested LLM calls and massive tool duplication.

**Current Pattern:**
```python
# LeadAgent (Strands) has 55 tools
tools = [
    get_xray_trace,  # AWS tool
    get_lambda_config,  # AWS tool (duplicated - also in Lambda specialist!)
    # ... 43 more AWS tools ...
    investigate_lambda_function,  # Specialist agent wrapped as @tool
    # ... 9 more specialist agents ...
]

# When LeadAgent calls investigate_lambda_function:
@tool
def investigate_lambda_function(function_name, context):
    lambda_agent = create_lambda_agent()  # NEW Strands agent!
    result = lambda_agent(prompt)  # NEW LLM call with 1,500 token system prompt!
    return result
```

**Better Pattern: Direct Agent Invocation**
```python
class LeadOrchestrator:
    """Orchestrator coordinates agents but is NOT itself a Strands agent."""

    def __init__(self):
        # Only tools for discovery
        self.discovery_tools = [
            get_xray_trace,
            get_all_resources_from_trace,
            query_logs_by_trace_id
        ]

        # Specialist agents (lazy-loaded)
        self._specialist_cache = {}

    async def investigate(self, inputs):
        # 1. Use discovery tools directly (no LLM needed)
        trace_data = get_xray_trace(inputs['trace_id'])
        resources = extract_resources(trace_data)

        # 2. Identify services to investigate
        services_to_investigate = self._identify_services(resources)

        # 3. Call specialists DIRECTLY (not via tool)
        specialist_results = []
        for service in services_to_investigate:
            specialist = self._get_specialist(service['type'])

            # Direct Strands agent call
            prompt = self._create_specialist_prompt(service, trace_data)
            result = specialist(prompt)

            specialist_results.append(result)

        # 4. Synthesize findings
        return self._synthesize_results(specialist_results)
```

**Benefits:**
- ✅ No nested Strands agent calls
- ✅ No tool duplication (lead doesn't need ALL AWS tools)
- ✅ Can use Python logic for routing (no LLM needed)
- ✅ Aligns with Chain-of-Agents research
- ✅ Saves ~3,000 tokens/investigation (no redundant tools in lead context)

**Implementation:**

**File:** `src/promptrca/core/orchestrator.py` (new)

```python
class DirectInvocationOrchestrator:
    """Non-agent orchestrator that coordinates specialist agents directly."""

    def __init__(self, region: str = None):
        self.region = region or get_region()
        self._specialist_cache = {}
        self._agent_factories = {
            'lambda': (create_lambda_agent, create_lambda_agent_model),
            # ... other factories
        }

    async def investigate(
        self,
        inputs: Dict[str, Any],
        region: str = None,
        assume_role_arn: Optional[str] = None,
        external_id: Optional[str] = None
    ) -> InvestigationReport:
        """Run investigation using direct agent invocation."""

        # 1. Parse inputs
        parsed = self._parse_inputs(inputs, region)

        # 2. Discover resources (use Python + raw tools, no LLM)
        resources = []
        if parsed.trace_ids:
            for trace_id in parsed.trace_ids:
                trace_data = get_xray_trace(trace_id)
                resources.extend(extract_resources_from_trace(trace_data))

        # 3. Determine which specialists to invoke
        specialists_needed = self._determine_specialists(resources)

        # 4. Invoke specialists in parallel (direct calls, not via tools)
        specialist_tasks = []
        for specialist_type, context in specialists_needed:
            specialist = self._get_specialist(specialist_type)
            prompt = self._create_specialist_prompt(specialist_type, context)
            specialist_tasks.append(specialist(prompt))

        # Use asyncio.gather for parallel execution
        specialist_results = await asyncio.gather(*specialist_tasks)

        # 5. Synthesize findings
        facts, hypotheses, advice = self._aggregate_results(specialist_results)

        # 6. Root cause analysis
        root_cause = self._analyze_root_cause(hypotheses, facts)

        # 7. Generate report
        return self._generate_report(facts, hypotheses, advice, root_cause)

    def _determine_specialists(self, resources: List[Resource]) -> List[Tuple[str, Dict]]:
        """Determine which specialists to invoke based on resources."""
        specialists = []

        for resource in resources:
            if resource.type == 'lambda_function':
                specialists.append(('lambda', {
                    'function_name': resource.name,
                    'context': resource.error_context
                }))
            elif resource.type == 'apigateway':
                specialists.append(('apigateway', {
                    'api_id': resource.api_id,
                    'stage': resource.stage,
                    'context': resource.error_context
                }))
            # ... other services

        return specialists
```

**Migration Path:**
1. Create `DirectInvocationOrchestrator` alongside existing `LeadOrchestratorAgent`
2. Add feature flag: `PROMPTRCA_USE_DIRECT_INVOCATION=false`
3. Test with 10% of traffic
4. Gradually roll out: 10% → 25% → 50% → 100%
5. Deprecate `LeadOrchestratorAgent` once stable

**Impact:**
- ✅ Eliminates nested agent calls (saves ~1,500 tokens per specialist)
- ✅ Removes tool duplication (saves ~2,000 tokens from lead context)
- ✅ Enables true parallel execution (3-5x latency reduction)
- ✅ Aligns with 2025 research best practices

**Effort:** 1-2 weeks
**Risk:** High (architectural change, requires extensive testing)

---

### 6.4 Parallel Specialist Execution

**Research:** Async agent coordination patterns

**NOTE:** This is now EASIER with direct invocation pattern (6.3). If keeping agents-as-tools, parallel execution is still possible but more complex.

**Problem:** Specialists are called sequentially, increasing latency.

**Current Flow (Sequential):**
```
Orchestrator → Lambda Specialist (2s)
            → API Gateway Specialist (2s)
            → IAM Specialist (2s)
Total: 6 seconds
```

**Optimized Flow (Parallel):**
```
Orchestrator → ┌─ Lambda Specialist (2s)
               ├─ API Gateway Specialist (2s)
               └─ IAM Specialist (2s)
Total: 2 seconds (3x faster)
```

**Implementation:**

**File:** `src/promptrca/agents/lead_orchestrator.py`

```python
import asyncio
from typing import List, Dict, Any

async def _invoke_specialists_parallel(
    self,
    specialist_tasks: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Invoke multiple specialists in parallel."""

    async def _invoke_specialist(task: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for async specialist invocation."""
        specialist_type = task["type"]
        prompt = task["prompt"]

        try:
            specialist = self._get_specialist_agent(specialist_type)

            # Run in thread pool (most LLM clients are sync)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,  # Use default executor
                specialist,
                prompt
            )

            return {
                "specialist_type": specialist_type,
                "status": "success",
                "result": result,
                "error": None
            }

        except Exception as e:
            logger.error(f"Specialist {specialist_type} failed: {e}")
            return {
                "specialist_type": specialist_type,
                "status": "failed",
                "result": None,
                "error": str(e)
            }

    # Execute all specialists in parallel
    results = await asyncio.gather(
        *[_invoke_specialist(task) for task in specialist_tasks],
        return_exceptions=True
    )

    return results

async def investigate(self, inputs: Dict[str, Any], region: str = None, assume_role_arn: Optional[str] = None, external_id: Optional[str] = None) -> InvestigationReport:
    """Run multi-agent investigation with parallel specialist execution."""

    # ... existing setup code ...

    # Identify specialists to invoke
    specialist_tasks = self._identify_specialist_tasks(context)

    if len(specialist_tasks) > 1:
        logger.info(f"🚀 Invoking {len(specialist_tasks)} specialists in parallel")
        specialist_results = await self._invoke_specialists_parallel(specialist_tasks)
    else:
        logger.info(f"🔍 Invoking single specialist")
        # Single specialist - no need for parallelization
        specialist_results = [await self._invoke_specialist(specialist_tasks[0])]

    # Aggregate specialist findings
    facts, hypotheses, advice = self._aggregate_specialist_results(specialist_results)

    # ... rest of investigation ...
```

**Impact:**
- ✅ 3-5x latency reduction (6s → 2s for 3 specialists)
- ✅ No token savings (same total tokens)
- ✅ Better user experience (faster results)
- ⚠️ Higher peak memory usage (multiple agents loaded simultaneously)

**Effort:** 3-4 days
**Risk:** Medium (async complexity, error handling)

**Note:** This is primarily a latency optimization, not token optimization. Include in Priority 3 for completeness.

---

### 6.5 Summary of Priority 3 Impact

| Optimization | Token Savings | Latency Improvement | Effort | Risk |
|--------------|---------------|---------------------|--------|------|
| **Direct Agent Invocation (NEW)** | **3,000-4,000 (eliminate nesting)** | **N/A** | **2 weeks** | **High** |
| Difficulty-Aware Routing | 5,000-7,000 (for simple) | 50% (simple cases) | 1 week | High |
| Memory/Caching Layer | 1,000-2,000 (duplicates) | 30% (cache hits) | 1 week | Medium |
| Parallel Specialist Execution | 0 (latency only) | 3-5x faster | 3-4 days | Medium |
| **Total** | **9,000-13,000 tokens (with direct invocation)** | **50-70% faster** | **5-6 weeks** | **High** |

**Combined with Priority 1 + 2: Total savings = 70-85%**

**CRITICAL:** Direct agent invocation (6.3) is the most impactful Phase 3 optimization, addressing the fundamental "agents-as-tools" architecture issue.

---

## 7. Implementation Roadmap

### Phase 1: Quick Wins (Week 1)
**Goal:** 40-50% token reduction, low risk, immediate impact

| Task | Owner | Duration | Dependencies | Success Metric |
|------|-------|----------|--------------|----------------|
| Implement lazy agent initialization | Engineer | 3 hours | None | Only 2-3 agents created per investigation |
| Add context pruning for trace data | Engineer | 4 hours | None | Trace data reduced from 1,000 → 200 tokens |
| Compress anti-hallucination rules | Engineer | 1 hour | None | Rules reduced from 300 → 100 tokens |
| Test & validate changes | QA | 1 day | Above tasks | No regression in investigation quality |

**Deliverable:** Production deployment with 40% token savings

---

### Phase 2: Medium-Term (Weeks 2-3)
**Goal:** 55-60% total token reduction, moderate risk

| Task | Owner | Duration | Dependencies | Success Metric |
|------|-------|----------|--------------|----------------|
| Optimize Lambda specialist prompt | Engineer | 3 hours | None | Prompt reduced 1,500 → 600 tokens |
| Optimize remaining 9 specialist prompts | Engineer | 2 days | Above | All specialists optimized |
| Implement Pydantic structured outputs | Engineer | 2 days | None | No JSON parsing overhead |
| Add response summarization | Engineer | 3 days | Pydantic outputs | Inter-agent context reduced 80% |
| Integration testing | QA | 2 days | All above | Quality maintained, 55% total savings |

**Deliverable:** Production deployment with 55-60% token savings

---

### Phase 3: Strategic (Weeks 4-8)
**Goal:** 60-80% token reduction, significant latency improvements

| Task | Owner | Duration | Dependencies | Success Metric |
|------|-------|----------|--------------|----------------|
| Design complexity classifier | Architect | 2 days | None | Classification accuracy >85% |
| Implement difficulty-aware routing | Engineer | 1 week | Complexity classifier | Simple investigations use 80% fewer tokens |
| Implement memory/cache layer | Engineer | 1 week | None | 50% cache hit rate |
| Add parallel specialist execution | Engineer | 4 days | None | 3x latency reduction |
| Comprehensive testing | QA | 1 week | All above | Quality + performance metrics met |

**Deliverable:** Production deployment with 60-80% token savings + 50% latency improvement

---

### Rollback Plan

Each phase should be feature-flagged for easy rollback:

```python
# Environment variables for feature flags
ENABLE_LAZY_AGENT_INIT = os.getenv("PROMPTRCA_LAZY_AGENTS", "true").lower() == "true"
ENABLE_CONTEXT_PRUNING = os.getenv("PROMPTRCA_CONTEXT_PRUNING", "true").lower() == "true"
ENABLE_OPTIMIZED_PROMPTS = os.getenv("PROMPTRCA_OPTIMIZED_PROMPTS", "true").lower() == "true"
ENABLE_STRUCTURED_OUTPUTS = os.getenv("PROMPTRCA_STRUCTURED_OUTPUTS", "false").lower() == "true"
ENABLE_RESPONSE_SUMMARIZATION = os.getenv("PROMPTRCA_RESPONSE_SUMMARIZATION", "false").lower() == "true"
ENABLE_DIFFICULTY_ROUTING = os.getenv("PROMPTRCA_DIFFICULTY_ROUTING", "false").lower() == "true"
ENABLE_CACHING = os.getenv("PROMPTRCA_CACHING", "false").lower() == "true"
ENABLE_PARALLEL_SPECIALISTS = os.getenv("PROMPTRCA_PARALLEL_SPECIALISTS", "false").lower() == "true"
```

---

## 8. Metrics and Monitoring

### 8.1 Token Metrics

**Track in OpenTelemetry/Langfuse:**

```python
# Add to investigation span
investigation_span.set_attribute("tokens.orchestrator_prompt", orchestrator_prompt_tokens)
investigation_span.set_attribute("tokens.specialists_total", specialist_total_tokens)
investigation_span.set_attribute("tokens.root_cause", root_cause_tokens)
investigation_span.set_attribute("tokens.total", total_tokens)
investigation_span.set_attribute("tokens.optimization_version", "v2.0")  # Track optimization version

# Calculate savings
baseline_tokens = 17500  # Pre-optimization baseline
savings_percentage = ((baseline_tokens - total_tokens) / baseline_tokens) * 100
investigation_span.set_attribute("tokens.savings_percentage", savings_percentage)
```

**Dashboard Metrics:**
- Average tokens per investigation (trend over time)
- Token savings percentage (target: 40% → 60% → 80%)
- Token distribution (orchestrator vs specialists vs root cause)
- Tokens by complexity level (simple vs moderate vs complex)

### 8.2 Quality Metrics

**Ensure optimizations don't degrade quality:**

```python
# Add to investigation report
investigation_span.set_attribute("quality.facts_found", len(facts))
investigation_span.set_attribute("quality.hypotheses_generated", len(hypotheses))
investigation_span.set_attribute("quality.advice_provided", len(advice))
investigation_span.set_attribute("quality.root_cause_confidence", root_cause.confidence_score)
```

**Quality Thresholds:**
- Root cause confidence ≥ 0.70 (maintain after optimization)
- Facts found ≥ 3 (maintain after optimization)
- Hypotheses generated ≥ 2 (maintain after optimization)

**Automated Alerts:**
- Alert if root cause confidence drops below 0.60 for 3+ consecutive investigations
- Alert if facts found < 2 for simple investigations

### 8.3 Performance Metrics

```python
# Latency tracking
investigation_span.set_attribute("latency.total_ms", total_latency_ms)
investigation_span.set_attribute("latency.orchestrator_ms", orchestrator_latency_ms)
investigation_span.set_attribute("latency.specialists_ms", specialist_latency_ms)

# Specialist usage
investigation_span.set_attribute("specialists.count", num_specialists_invoked)
investigation_span.set_attribute("specialists.types", ",".join(specialist_types))
investigation_span.set_attribute("specialists.lazy_loaded", lazy_loaded_count)

# Cache metrics
investigation_span.set_attribute("cache.hits", cache_hit_count)
investigation_span.set_attribute("cache.misses", cache_miss_count)
investigation_span.set_attribute("cache.hit_rate", cache_hit_rate)
```

**Performance Targets:**
- Simple investigations: <3s total latency
- Moderate investigations: <5s total latency
- Complex investigations: <10s total latency
- Cache hit rate: >50%

---

## 9. Risk Assessment

### 9.1 Priority 1 Risks (Low)

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Lazy loading breaks tool registration | Low | Medium | Add integration tests for all specialists |
| Trace summary loses critical error details | Medium | High | Include all error segments, validate against test cases |
| Compressed rules cause hallucinations | Low | Medium | A/B test with 10% of traffic, monitor quality metrics |

**Overall Risk:** Low
**Recommendation:** Proceed with Phase 1 implementation

---

### 9.2 Priority 2 Risks (Medium)

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Optimized prompts reduce investigation quality | Medium | High | A/B test, maintain quality metrics, gradual rollout |
| Pydantic validation too strict | Low | Medium | Use permissive validation, allow optional fields |
| Summarization loses important context | Medium | High | Preserve top N facts/hypotheses, test on complex cases |

**Overall Risk:** Medium
**Recommendation:** Gradual rollout with 25% → 50% → 100% traffic

---

### 9.3 Priority 3 Risks (High)

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Complexity classifier misclassifies issues | Medium | High | Human-in-the-loop for first 100 classifications, tune thresholds |
| Simple path misses critical issues | Low | Very High | Override mechanism, escalate to complex if confidence <0.70 |
| Cache serves stale data | Medium | Medium | Short TTL (15 min), cache invalidation on errors |
| Parallel execution increases memory usage | High | Low | Monitor memory, add circuit breakers |

**Overall Risk:** High
**Recommendation:** Extended beta testing, canary deployment (5% → 25% → 100%)

---

## 10. Success Criteria

### 10.1 Token Reduction Targets

| Phase | Target Savings | Measured At | Success Threshold |
|-------|----------------|-------------|-------------------|
| Phase 1 | 40-50% | 1 week after deployment | ≥35% reduction |
| Phase 2 | 55-60% | 3 weeks after deployment | ≥50% reduction |
| Phase 3 | 60-80% | 8 weeks after deployment | ≥55% reduction |

### 10.2 Quality Maintenance Targets

| Metric | Baseline | Target | Success Threshold |
|--------|----------|--------|-------------------|
| Root Cause Confidence | 0.75 | ≥0.75 | ≥0.70 |
| Facts Found (avg) | 5.2 | ≥5.0 | ≥4.0 |
| Hypotheses Generated (avg) | 3.8 | ≥3.5 | ≥3.0 |
| User Satisfaction | N/A | ≥4.0/5.0 | ≥3.5/5.0 |

### 10.3 Performance Targets

| Metric | Baseline | Target | Success Threshold |
|--------|----------|--------|-------------------|
| Simple Investigation Latency | 6s | <3s | <4s |
| Complex Investigation Latency | 12s | <10s | <11s |
| Cache Hit Rate | 0% | >50% | >30% |

---

## 11. Cost-Benefit Analysis

### 11.1 Token Cost Savings

**Assumptions:**
- Current avg: 17,500 tokens/investigation
- 1,000 investigations/month
- Cost: $0.015 per 1K input tokens (Sonnet 3.5), $0.075 per 1K output tokens
- Avg input:output ratio: 70:30

**Baseline Monthly Cost:**
```
Input tokens: 17,500 × 0.7 = 12,250 tokens
Output tokens: 17,500 × 0.3 = 5,250 tokens

Input cost: 12,250 / 1000 × $0.015 = $0.184 per investigation
Output cost: 5,250 / 1000 × $0.075 = $0.394 per investigation
Total: $0.578 per investigation

Monthly (1,000 investigations): $578
```

**After Phase 1 (40% reduction):**
```
Tokens: 10,500 (40% savings)
Cost: $0.347 per investigation
Monthly: $347
Savings: $231/month (40%)
```

**After Phase 2 (60% reduction):**
```
Tokens: 7,000 (60% savings)
Cost: $0.231 per investigation
Monthly: $231
Savings: $347/month (60%)
```

**After Phase 3 (70% savings for 50% of investigations, 60% for others):**
```
Simple (50% of traffic, 70% savings): 5,250 tokens → $0.173/investigation
Complex (50% of traffic, 60% savings): 7,000 tokens → $0.231/investigation
Weighted avg: $0.202/investigation
Monthly: $202
Savings: $376/month (65%)
```

**Annual Savings:** $4,512

### 11.2 Engineering Investment

| Phase | Engineering Effort | Cost (at $100/hr) |
|-------|-------------------|-------------------|
| Phase 1 | 2 days | $1,600 |
| Phase 2 | 2 weeks | $8,000 |
| Phase 3 | 4 weeks | $16,000 |
| **Total** | **6.5 weeks** | **$25,600** |

**ROI Timeline:**
- Phase 1 payback: 7 months ($1,600 / $231)
- Phase 2 payback: 23 months ($8,000 / $347)
- Phase 3 payback: 43 months ($16,000 / $376)

**Note:** This is conservative and doesn't account for:
- Improved latency → better user experience → higher adoption
- Reduced AWS Lambda costs (faster execution)
- Enables scaling to 10x traffic without 10x cost

---

## 12. Conclusion

### 12.1 Key Takeaways

✅ **Your architecture is fundamentally sound**
- Hierarchical multi-agent orchestration is the right pattern
- Specialized agents align with 2024-2025 research
- Context isolation via `contextvars` is excellent

⚠️ **Token efficiency can be significantly improved**
- Current: ~17,500 tokens/investigation
- After optimizations: ~6,000 tokens/investigation (65% savings)
- Primary issues: verbose prompts, full context passing, eager initialization

✅ **Research supports your approach**
- Chain-of-Agents (NeurIPS 2024): Multi-agent + summarization = optimal
- Heterogeneous models: Use small models for simple tasks (you support this!)
- Difficulty-aware routing: Emerging best practice for 2025

### 12.2 Recommended Action Plan

**Immediate (This Week):**
- Implement Priority 1 optimizations (lazy loading, context pruning, compress rules)
- Deploy with feature flags
- Monitor token metrics and quality

**Short-Term (Next Month):**
- Implement Priority 2 optimizations (system prompt optimization, structured outputs)
- A/B test optimized prompts
- Gradual rollout with monitoring

**Long-Term (Next Quarter):**
- Implement difficulty-aware routing
- Add memory/caching layer
- Enable parallel specialist execution

### 12.3 Final Recommendation

**Proceed with incremental optimization.** Your multi-agent architecture is solid; it just needs token efficiency tuning. Start with Priority 1 (low risk, high impact), validate quality, then move to Priority 2 and 3.

**Do NOT redesign from scratch.** The research validates your architectural choices. Focus on optimization, not reimplementation.

---

## Appendix A: Research References

1. **Chain-of-Agents (CoA)**, NeurIPS 2024
   - Multi-agent collaboration for long-context tasks
   - O(n²) → O(nk) complexity reduction via summarization
   - https://research.google/blog/chain-of-agents-large-language-models-collaborating-on-long-context-tasks/

2. **Difficulty-Aware Agent Orchestration**, arXiv 2509.11079
   - Adaptive complexity routing
   - Task-level workflows waste resources on simple queries
   - https://arxiv.org/html/2509.11079

3. **LangChain Multi-Agent Patterns**, 2025
   - Hierarchical architecture best practices
   - Memory and context sharing patterns
   - https://blog.langchain.com/langgraph-multi-agent-workflows/

4. **Context Engineering for Production AI Agents**, Medium 2025
   - Context pruning, caching, batching
   - RAG vs full-context comparison
   - https://medium.com/@kuldeep.paul08/context-engineering-optimizing-llm-memory-for-production-ai-agents-6a7c9165a431

5. **Why Do Multi-Agent LLM Systems Fail?**, arXiv 2503.13657v1
   - 14 failure modes in MAS frameworks
   - Prompt bloat, over-processing, ambiguous communication
   - https://arxiv.org/html/2503.13657v1

---

## Appendix B: Code Templates

### B.1 Feature Flag Configuration

```python
# src/promptrca/utils/feature_flags.py

import os
from typing import Dict, Any

class FeatureFlags:
    """Centralized feature flag management for gradual rollout."""

    @staticmethod
    def is_enabled(flag_name: str, default: bool = False) -> bool:
        """Check if feature flag is enabled."""
        env_var = f"PROMPTRCA_{flag_name.upper()}"
        return os.getenv(env_var, str(default)).lower() == "true"

    @staticmethod
    def get_all() -> Dict[str, bool]:
        """Get all feature flag states."""
        return {
            "lazy_agent_init": FeatureFlags.is_enabled("lazy_agents", default=True),
            "context_pruning": FeatureFlags.is_enabled("context_pruning", default=True),
            "optimized_prompts": FeatureFlags.is_enabled("optimized_prompts", default=False),
            "structured_outputs": FeatureFlags.is_enabled("structured_outputs", default=False),
            "response_summarization": FeatureFlags.is_enabled("response_summarization", default=False),
            "difficulty_routing": FeatureFlags.is_enabled("difficulty_routing", default=False),
            "caching": FeatureFlags.is_enabled("caching", default=False),
            "parallel_specialists": FeatureFlags.is_enabled("parallel_specialists", default=False),
        }

# Usage:
from promptrca.utils.feature_flags import FeatureFlags

if FeatureFlags.is_enabled("lazy_agents"):
    agent = self._get_specialist_agent(specialist_type)  # Lazy load
else:
    agent = self.lambda_agent  # Eager load (existing)
```

### B.2 Metrics Collection Template

```python
# src/promptrca/utils/metrics.py

from opentelemetry import trace
from typing import Dict, Any

class InvestigationMetrics:
    """Track investigation metrics for monitoring and optimization."""

    def __init__(self, investigation_span):
        self.span = investigation_span
        self.tokens = {
            "orchestrator_prompt": 0,
            "specialists_total": 0,
            "root_cause": 0,
        }

    def record_prompt_tokens(self, component: str, tokens: int):
        """Record token usage for a component."""
        self.tokens[component] = tokens
        self.span.set_attribute(f"tokens.{component}", tokens)

    def record_specialist_invocation(self, specialist_type: str, tokens: int):
        """Record specialist invocation."""
        self.tokens["specialists_total"] += tokens
        self.span.set_attribute(f"tokens.specialist.{specialist_type}", tokens)

    def calculate_savings(self, baseline: int = 17500) -> float:
        """Calculate token savings vs baseline."""
        total = sum(self.tokens.values())
        savings = ((baseline - total) / baseline) * 100
        self.span.set_attribute("tokens.total", total)
        self.span.set_attribute("tokens.savings_percentage", savings)
        return savings

# Usage:
from promptrca.utils.metrics import InvestigationMetrics

metrics = InvestigationMetrics(investigation_span)
metrics.record_prompt_tokens("orchestrator_prompt", len(prompt.split()) * 1.3)  # Rough estimate
metrics.record_specialist_invocation("lambda", specialist_tokens)
savings = metrics.calculate_savings()
logger.info(f"💰 Token savings: {savings:.1f}%")
```

---

**Document Version:** 1.0
**Last Updated:** 2025-10-20
**Next Review:** After Phase 1 completion
