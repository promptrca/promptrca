# Agent Chain Visual Diagram

## Complete Investigation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER INPUT                                   │
│  "My Lambda function is failing with timeout errors"            │
│  OR                                                              │
│  { function_name: "my-func", trace_id: "1-abc-123" }           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  1. INPUT PARSER AGENT                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Responsibility: Parse and structure inputs                │  │
│  │ Input: Raw string or dict                                 │  │
│  │ Output: ParsedInputs                                      │  │
│  │   - primary_targets: [Resource]                           │  │
│  │   - trace_ids: [str]                                      │  │
│  │   - error_messages: [str]                                 │  │
│  │   - business_context: dict                                │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ ParsedInputs
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              2. RESOURCE DISCOVERY (Python Logic)                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Responsibility: Find AWS resources                        │  │
│  │ Input: ParsedInputs                                       │  │
│  │ Process:                                                  │  │
│  │   1. Add explicit targets from ParsedInputs              │  │
│  │   2. Extract resources from X-Ray traces                 │  │
│  │   3. Deduplicate by ARN/name                             │  │
│  │ Output: List[Resource]                                    │  │
│  │   - type: lambda, apigateway, etc.                       │  │
│  │   - name: resource name                                   │  │
│  │   - arn: resource ARN                                     │  │
│  │   - region: AWS region                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ List[Resource]
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│           3. EVIDENCE COLLECTION (Python + AWS Tools)            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Responsibility: Gather facts from AWS                     │  │
│  │ Input: List[Resource] + ParsedInputs                      │  │
│  │ Process:                                                  │  │
│  │   1. Check AWS Service Health (NEW!)                     │  │
│  │   2. Check CloudTrail for changes (NEW!)                 │  │
│  │   3. For each resource:                                   │  │
│  │      - Get configuration                                  │  │
│  │      - Get logs                                           │  │
│  │      - Get metrics                                        │  │
│  │   4. Parallel execution (asyncio.gather)                 │  │
│  │ Output: List[Fact]                                        │  │
│  │   - source: tool name                                     │  │
│  │   - content: observation                                  │  │
│  │   - confidence: 0.0-1.0                                   │  │
│  │   - metadata: additional context                          │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ List[Fact]
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              4. HYPOTHESIS GENERATION AGENT                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Responsibility: Generate potential root causes            │  │
│  │ Input: List[Fact]                                         │  │
│  │ Process:                                                  │  │
│  │   1. AI Analysis (if available):                         │  │
│  │      - Analyze facts for patterns                        │  │
│  │      - Identify error types                              │  │
│  │      - Correlate related facts                           │  │
│  │      - Assign confidence scores                          │  │
│  │   2. Heuristic Fallback:                                 │  │
│  │      - Pattern matching on fact content                  │  │
│  │      - Known error signatures                            │  │
│  │ Output: List[Hypothesis]                                  │  │
│  │   - type: permission_issue, timeout, etc.                │  │
│  │   - description: what might be wrong                     │  │
│  │   - confidence: 0.0-1.0                                   │  │
│  │   - evidence: supporting facts                           │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ List[Hypothesis]
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              5. ROOT CAUSE ANALYSIS AGENT                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Responsibility: Select primary root cause                 │  │
│  │ Input: List[Hypothesis] + List[Fact]                      │  │
│  │ Process:                                                  │  │
│  │   1. AI Classification (if available):                   │  │
│  │      - Analyze causal relationships                      │  │
│  │      - Distinguish symptoms from causes                  │  │
│  │      - Select primary root cause                         │  │
│  │      - Identify contributing factors                     │  │
│  │   2. Heuristic Fallback:                                 │  │
│  │      - Separate root causes from symptoms                │  │
│  │      - Pick highest confidence root cause                │  │
│  │ Output: RootCauseAnalysis                                 │  │
│  │   - primary_root_cause: Hypothesis                       │  │
│  │   - contributing_factors: [Hypothesis]                   │  │
│  │   - confidence_score: 0.0-1.0                            │  │
│  │   - analysis_summary: explanation                        │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ RootCauseAnalysis
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                6. ADVICE GENERATION AGENT                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Responsibility: Generate remediation steps                │  │
│  │ Input: List[Fact] + List[Hypothesis]                      │  │
│  │ Process:                                                  │  │
│  │   - Map hypothesis types to advice templates             │  │
│  │   - Prioritize by hypothesis confidence                  │  │
│  │   - Add context-specific details                         │  │
│  │ Output: List[Advice]                                      │  │
│  │   - title: short description                             │  │
│  │   - description: detailed steps                          │  │
│  │   - priority: high/medium/low                            │  │
│  │   - category: configuration/code/permissions             │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ List[Advice]
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                7. REPORT GENERATION (Python)                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Responsibility: Assemble final report                     │  │
│  │ Input: ALL previous outputs                               │  │
│  │   - facts: List[Fact]                                     │  │
│  │   - hypotheses: List[Hypothesis]                          │  │
│  │   - advice: List[Advice]                                  │  │
│  │   - root_cause: RootCauseAnalysis                         │  │
│  │   - resources: List[Resource]                             │  │
│  │   - timing: start/end times                               │  │
│  │ Output: InvestigationReport                               │  │
│  │   - run_id: unique identifier                             │  │
│  │   - status: completed/failed                              │  │
│  │   - affected_resources: [AffectedResource]               │  │
│  │   - severity_assessment: SeverityAssessment              │  │
│  │   - facts: [Fact]                                         │  │
│  │   - root_cause_analysis: RootCauseAnalysis               │  │
│  │   - hypotheses: [Hypothesis]                              │  │
│  │   - advice: [Advice]                                      │  │
│  │   - timeline: [EventTimeline]                             │  │
│  │   - summary: JSON summary                                 │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ InvestigationReport
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FINAL OUTPUT                                 │
│  {                                                               │
│    "investigation": { "id": "...", "status": "completed" },     │
│    "severity": { "severity": "high", "confidence": 0.85 },      │
│    "root_cause": {                                               │
│      "primary_root_cause": "Permission issue with IAM role",    │
│      "confidence_score": 0.90                                    │
│    },                                                            │
│    "facts": [...],                                               │
│    "hypotheses": [...],                                          │
│    "remediation": [...]                                          │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Summary

```
Raw Input
    ↓ (parse)
ParsedInputs
    ↓ (discover)
List[Resource]
    ↓ (collect evidence)
List[Fact]
    ↓ (generate hypotheses)
List[Hypothesis]
    ↓ (analyze root cause)
RootCauseAnalysis
    ↓ (generate advice)
List[Advice]
    ↓ (assemble report)
InvestigationReport
```

---

## Agent Responsibilities Matrix

| Stage | Agent | Input Type | Output Type | AWS Calls? | AI Used? |
|-------|-------|------------|-------------|------------|----------|
| 1 | InputParser | str/dict | ParsedInputs | ❌ No | ✅ Yes (optional) |
| 2 | ResourceDiscovery | ParsedInputs | List[Resource] | ✅ Yes (X-Ray) | ❌ No |
| 3 | EvidenceCollection | List[Resource] | List[Fact] | ✅ Yes (many) | ❌ No |
| 4 | HypothesisAgent | List[Fact] | List[Hypothesis] | ❌ No | ✅ Yes (fallback: heuristic) |
| 5 | RootCauseAgent | List[Hypothesis] | RootCauseAnalysis | ❌ No | ✅ Yes (fallback: heuristic) |
| 6 | AdviceAgent | List[Hypothesis] | List[Advice] | ❌ No | ❌ No (template-based) |
| 7 | ReportGenerator | All above | InvestigationReport | ❌ No | ❌ No |

---

## Parallel Execution Points

```
Evidence Collection (Stage 3):
┌─────────────────────────────────────┐
│  asyncio.gather() - Parallel        │
│                                     │
│  ┌─────────┐  ┌─────────┐  ┌─────┐│
│  │ Lambda  │  │ API GW  │  │ IAM ││
│  │ Tools   │  │ Tools   │  │Tools││
│  └─────────┘  └─────────┘  └─────┘│
│       │            │           │   │
│       └────────────┴───────────┘   │
│                │                   │
│         Aggregate Facts            │
└─────────────────────────────────────┘
```

---

## Error Handling Flow

```
Each Stage:
┌─────────────────────────────────┐
│  Try:                           │
│    Execute stage logic          │
│  Except:                        │
│    Log error                    │
│    Create fallback output       │
│    Continue to next stage       │
└─────────────────────────────────┘

Example:
  Evidence Collection Fails
         ↓
  Create error Fact
         ↓
  Hypothesis Agent still runs
         ↓
  May generate "insufficient_data" hypothesis
```

---

## Key Design Principles

### 1. Unidirectional Data Flow
```
Stage N → Stage N+1 → Stage N+2
  ✅ Forward only
  ❌ No backtracking
  ❌ No circular dependencies
```

### 2. Single Responsibility
```
Each agent does ONE thing:
  ✅ InputParser: Parse inputs
  ✅ HypothesisAgent: Generate hypotheses
  ❌ HypothesisAgent does NOT collect evidence
  ❌ RootCauseAgent does NOT generate hypotheses
```

### 3. Dependency Inversion
```
Agents depend on interfaces, not implementations:
  ✅ HypothesisAgent receives List[Fact]
  ❌ HypothesisAgent does NOT know about AWS tools
  ✅ RootCauseAgent receives List[Hypothesis]
  ❌ RootCauseAgent does NOT know about HypothesisAgent
```

### 4. Graceful Degradation
```
AI Available:
  Use AI for analysis
     ↓
AI Fails:
  Fall back to heuristics
     ↓
Heuristics Fail:
  Return minimal output with error
```

---

## Comparison: Old vs New

### Old Pattern (Agents-as-Tools)
```
LeadAgent (Strands)
  ↓ (tool call)
investigate_lambda_function() [wrapped as @tool]
  ↓ (creates new agent)
LambdaAgent (Strands)
  ↓ (tool calls)
AWS APIs

Problems:
❌ Nested LLM calls (expensive)
❌ Tool duplication (55 tools in lead)
❌ Non-deterministic routing
```

### New Pattern (Direct Invocation)
```
DirectOrchestrator (Python)
  ↓ (Python logic)
Determine which specialists needed
  ↓ (parallel execution)
[LambdaAgent, APIGWAgent, IAMAgent] (Strands)
  ↓ (tool calls)
AWS APIs

Benefits:
✅ Single-level LLM calls
✅ No tool duplication
✅ Deterministic routing
✅ 3-5x faster (parallel)
```

---

## Performance Characteristics

| Stage | Latency | Tokens | Parallelizable? |
|-------|---------|--------|-----------------|
| Input Parsing | <100ms | 500-1000 | ❌ No |
| Resource Discovery | 200-500ms | 0 (no LLM) | ✅ Yes (multiple traces) |
| Evidence Collection | 1-3s | 0 (no LLM) | ✅ Yes (per resource) |
| Hypothesis Generation | 2-4s | 2000-3000 | ❌ No |
| Root Cause Analysis | 2-3s | 1500-2000 | ❌ No |
| Advice Generation | <100ms | 0 (template) | ❌ No |
| Report Generation | <100ms | 0 (assembly) | ❌ No |
| **Total** | **5-10s** | **4000-6000** | **Partial** |

---

## Success Metrics

### Quality Metrics
- ✅ Root cause confidence ≥ 0.70
- ✅ Facts found ≥ 3
- ✅ Hypotheses generated ≥ 2
- ✅ Evidence per hypothesis ≥ 1

### Performance Metrics
- ✅ Total latency < 15s
- ✅ Token usage < 10,000
- ✅ AWS API calls < 50

### Reliability Metrics
- ✅ Success rate ≥ 95%
- ✅ Graceful degradation on failures
- ✅ No data loss between stages

---

This diagram shows the complete agent chain with proper separation of concerns and correct data flow at each stage.
