# PromptWizard Optimization Guide for PromptRCA

**Status:** Reference guide for future implementation
**Expected Impact:** 21% accuracy improvement (based on eARCO paper results)
**Estimated Time:** 1-2 weeks for initial implementation
**Estimated Cost:** $50-200 in LLM API calls

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Phase 1: Setup](#phase-1-setup-1-day)
4. [Phase 2: Data Collection](#phase-2-data-collection-3-5-days)
5. [Phase 3: Optimization](#phase-3-optimization-2-3-days)
6. [Phase 4: Evaluation](#phase-4-evaluation-2-3-days)
7. [Phase 5: Deployment](#phase-5-deployment-1-day)
8. [Troubleshooting](#troubleshooting)
9. [References](#references)

---

## Overview

### What is PromptWizard?

PromptWizard is an automated prompt optimization framework from Microsoft Research that uses LLMs to optimize prompts through iterative feedback. It achieved **21% accuracy improvement** in the eARCO paper for root cause analysis tasks.

**Key Features:**
- **Automated optimization** - No manual prompt engineering
- **Feedback-driven** - Iterative Mutate → Score → Critique → Synthesize loop
- **Few-shot example generation** - Creates synthetic training examples
- **Cost-effective** - ~100 LLM calls per agent (~$5-10)

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    PromptWizard Process                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. MUTATE      → Generate prompt variations                │
│                   (different "thinking styles")             │
│                                                              │
│  2. SCORE       → Test each variation on training data      │
│                   (measure accuracy)                        │
│                                                              │
│  3. CRITIQUE    → Analyze best prompt's strengths/weaknesses│
│                   (LLM provides feedback)                   │
│                                                              │
│  4. SYNTHESIZE  → Combine insights to improve prompt        │
│                   (create better version)                   │
│                                                              │
│  Repeat 3-10 iterations → Optimized Prompt                  │
└─────────────────────────────────────────────────────────────┘
```

### Why Use PromptWizard for PromptRCA?

| Benefit | Impact |
|---------|--------|
| **Accuracy Improvement** | 21% better RCA quality (eARCO paper) |
| **Automatic Optimization** | No manual trial-and-error |
| **Adaptive to Your Data** | Optimizes for YOUR specific incidents |
| **One-time Investment** | Optimize once, reuse forever |
| **Works with Current Improvements** | Builds on structured prompts we created |

---

## Prerequisites

### Required Knowledge
- [ ] Familiarity with Python and pip
- [ ] Access to OpenAI API or Azure OpenAI
- [ ] Understanding of your RCA workflow
- [ ] Ability to identify ground truth root causes

### Required Resources
- [ ] **Training Data**: 25-30 historical incidents per agent with verified root causes
- [ ] **API Access**: OpenAI API key (GPT-4 or GPT-4o recommended)
- [ ] **Compute**: Standard laptop/server (no GPU needed)
- [ ] **Budget**: $10-50 per agent for optimization
- [ ] **Time**: 1-3 hours per agent for optimization to run

### System Requirements
- Python 3.8+
- 8GB RAM minimum
- Internet connection for API calls
- Git installed

---

## Phase 1: Setup (1 Day)

### Step 1.1: Install PromptWizard

```bash
# Navigate to your project directory
cd /Users/christiangennarofaraone/projects/sherlock/core

# Clone PromptWizard repository
git clone https://github.com/microsoft/PromptWizard
cd PromptWizard

# Create virtual environment (optional but recommended)
python -m venv promptwizard-env
source promptwizard-env/bin/activate  # On macOS/Linux
# OR
# promptwizard-env\Scripts\activate  # On Windows

# Install PromptWizard
pip install -e .

# Verify installation
python -c "import promptwizard; print('✅ PromptWizard installed successfully')"
```

### Step 1.2: Configure API Access

Create a `.env` file in the PromptWizard directory:

```bash
# .env
USE_OPENAI_API_KEY="true"
OPENAI_API_KEY="sk-your-openai-api-key-here"
OPENAI_MODEL_NAME="gpt-4o"

# Optional: For Azure OpenAI
# USE_AZURE_OPENAI="true"
# AZURE_OPENAI_ENDPOINT="https://your-endpoint.openai.azure.com/"
# AZURE_OPENAI_API_VERSION="2024-02-15-preview"
# AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4"
```

**⚠️ Security Note:** Never commit `.env` files to git. Add to `.gitignore`:
```bash
echo ".env" >> .gitignore
```

### Step 1.3: Create Project Structure

```bash
# Create directories for PromptRCA optimization
mkdir -p promptrca-optimization/{training_data,optimized_prompts,evaluation,scripts}

cd promptrca-optimization
```

**Directory Structure:**
```
promptrca-optimization/
├── training_data/          # Historical incidents (JSON files)
│   ├── lambda_incidents.json
│   ├── apigateway_incidents.json
│   └── ...
├── optimized_prompts/      # Output from PromptWizard
│   ├── lambda_agent_optimized.txt
│   └── ...
├── evaluation/             # Test results and metrics
│   ├── test_cases.json
│   └── results.json
└── scripts/                # Optimization scripts
    ├── optimize_lambda.py
    ├── optimize_apigateway.py
    └── evaluate_prompts.py
```

---

## Phase 2: Data Collection (3-5 Days)

### Step 2.1: Define Data Requirements

**Per Agent, you need:**
- **Training Set**: 25 incidents (used to optimize prompt)
- **Validation Set**: 5 incidents (used to validate during optimization)
- **Test Set**: 10+ incidents (used to measure final performance)

**Total per agent: 40+ incidents**

**Data Quality Requirements:**
1. ✅ **Verified root causes** - Must have correct, confirmed RCA
2. ✅ **Diverse failure modes** - Cover different error types
3. ✅ **Complete metadata** - Title, summary, error messages, affected resources
4. ✅ **Resolved incidents** - Investigation completed, issue fixed
5. ✅ **Recent data** - Last 6-12 months preferred

### Step 2.2: Data Collection Sources

**Option 1: Production Incidents** (Best)
```sql
-- Example query for incident management system
SELECT
    incident_id,
    title,
    summary,
    error_message,
    affected_service,
    root_cause,
    root_cause_type,
    severity,
    created_at,
    resolved_at
FROM incidents
WHERE status = 'resolved'
    AND root_cause IS NOT NULL
    AND affected_service = 'lambda'  -- Or other service
    AND created_at >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
ORDER BY created_at DESC
LIMIT 50;
```

**Option 2: Past PromptRCA Reports**
```python
# Extract from your investigation reports
import json
from pathlib import Path

reports_dir = Path("investigation_reports/")
training_data = []

for report_file in reports_dir.glob("*.json"):
    with open(report_file) as f:
        report = json.load(f)

    # Only include if root cause was verified
    if report.get("verified", False):
        training_data.append({
            "incident_id": report["run_id"],
            "input": {
                "title": report.get("title", ""),
                "summary": report.get("summary", ""),
                "error_messages": report.get("error_messages", []),
                "service": report.get("service", ""),
                "affected_resources": report.get("affected_resources", [])
            },
            "output": {
                "root_cause": report["root_cause_analysis"]["primary_root_cause"]["description"],
                "root_cause_type": report["root_cause_analysis"]["primary_root_cause"]["type"],
                "confidence": report["root_cause_analysis"]["confidence_score"]
            }
        })
```

**Option 3: Synthetic Test Cases** (Last Resort)
```python
# Create realistic test scenarios based on known patterns
synthetic_incidents = [
    {
        "input": {
            "title": "Lambda function timeout in payment-processor",
            "summary": "Function timing out after 3 seconds when processing large batches",
            "error_message": "Task timed out after 3.00 seconds",
            "service": "lambda",
            "function_name": "payment-processor-prod"
        },
        "output": {
            "root_cause": "Function timeout setting (3s) insufficient for batch processing requiring 8-10 seconds",
            "root_cause_type": "timeout",
            "confidence": 0.88
        }
    }
    # Add 24 more diverse scenarios
]
```

### Step 2.3: Format Training Data

**Required JSON Format:**

```json
{
  "task_name": "lambda_root_cause_analysis",
  "task_description": "Analyze AWS Lambda function incidents and identify the root cause with high confidence.",
  "examples": [
    {
      "input": "INCIDENT TITLE: Lambda timeout in payment-processor\n\nSUMMARY: Function timing out after 3 seconds when processing large batches of transactions.\n\nERROR MESSAGE: Task timed out after 3.00 seconds\n\nCONFIGURATION:\n- Function: payment-processor-prod\n- Memory: 512 MB\n- Timeout: 3 seconds\n- Runtime: python3.11",
      "output": "{\n  \"root_cause\": \"Function timeout setting (3s) is insufficient for typical batch processing time which requires 8-10 seconds based on execution patterns\",\n  \"root_cause_type\": \"timeout\",\n  \"confidence\": 0.88,\n  \"evidence\": [\"Task timed out after 3.00 seconds\", \"Timeout configured as 3 seconds\"],\n  \"recommendation\": \"Increase function timeout from 3s to at least 10s to accommodate batch processing workload\"\n}"
    },
    {
      "input": "INCIDENT TITLE: API Gateway 403 errors on /users endpoint\n\nSUMMARY: All requests to /api/users returning 403 Forbidden after recent deployment.\n\nERROR MESSAGE: User: arn:aws:sts::123456789:assumed-role/ApiGatewayRole is not authorized to perform: lambda:InvokeFunction on resource: arn:aws:lambda:us-east-1:123456789:function:users-handler\n\nCONFIGURATION:\n- API: abc123xyz\n- Stage: prod\n- Integration: Lambda (users-handler)",
      "output": "{\n  \"root_cause\": \"API Gateway execution role lacks lambda:InvokeFunction permission for target Lambda function users-handler\",\n  \"root_cause_type\": \"permission_issue\",\n  \"confidence\": 0.92,\n  \"evidence\": [\"is not authorized to perform: lambda:InvokeFunction\", \"ApiGatewayRole missing required permissions\"],\n  \"recommendation\": \"Add lambda:InvokeFunction permission to ApiGatewayRole IAM policy for arn:aws:lambda:us-east-1:123456789:function:users-handler\"\n}"
    }
    // ... 23 more examples for training
  ],
  "validation_examples": [
    // ... 5 examples for validation
  ]
}
```

**Template for Data Collection:**

```python
# scripts/prepare_training_data.py

import json
from typing import List, Dict

def format_incident_for_training(incident: Dict) -> Dict:
    """Convert raw incident data to PromptWizard format."""

    # Format input as structured text
    input_text = f"""INCIDENT TITLE: {incident['title']}

SUMMARY: {incident['summary']}

ERROR MESSAGE: {incident.get('error_message', 'N/A')}

CONFIGURATION:
- Service: {incident['service']}
- Resource: {incident.get('resource_name', 'N/A')}
- Region: {incident.get('region', 'us-east-1')}
"""

    # Format output as structured JSON
    output_json = {
        "root_cause": incident['verified_root_cause'],
        "root_cause_type": incident['root_cause_type'],
        "confidence": incident.get('confidence', 0.85),
        "evidence": incident.get('evidence', []),
        "recommendation": incident.get('recommendation', '')
    }

    return {
        "input": input_text,
        "output": json.dumps(output_json, indent=2)
    }

def create_training_file(incidents: List[Dict], output_file: str):
    """Create PromptWizard training data file."""

    # Split into training (first 25) and validation (last 5)
    training_examples = [format_incident_for_training(inc) for inc in incidents[:25]]
    validation_examples = [format_incident_for_training(inc) for inc in incidents[25:30]]

    training_data = {
        "task_name": f"{incidents[0]['service']}_root_cause_analysis",
        "task_description": f"Analyze AWS {incidents[0]['service']} incidents and identify the root cause with high confidence.",
        "examples": training_examples,
        "validation_examples": validation_examples
    }

    with open(output_file, 'w') as f:
        json.dump(training_data, f, indent=2)

    print(f"✅ Created training file: {output_file}")
    print(f"   - Training examples: {len(training_examples)}")
    print(f"   - Validation examples: {len(validation_examples)}")

# Usage:
# python scripts/prepare_training_data.py
```

### Step 2.4: Data Quality Checklist

Before proceeding, verify your data quality:

- [ ] **Coverage**: All major failure types represented (timeouts, permissions, code bugs, config errors)
- [ ] **Accuracy**: Root causes verified by engineers who resolved the incidents
- [ ] **Diversity**: Mix of services, error types, and severities
- [ ] **Balance**: Not skewed toward one type (e.g., all permission errors)
- [ ] **Completeness**: All examples have required fields (title, summary, error, root cause)
- [ ] **Recent**: Majority from last 6 months (reflects current architecture)

**Quality Metrics:**
```python
# scripts/validate_training_data.py

def validate_training_data(data_file: str):
    """Validate training data quality."""
    with open(data_file) as f:
        data = json.load(f)

    examples = data['examples']

    # Check diversity
    root_cause_types = [ex['output']['root_cause_type'] for ex in examples]
    type_distribution = {t: root_cause_types.count(t) for t in set(root_cause_types)}

    print(f"📊 Data Quality Report:")
    print(f"   Total examples: {len(examples)}")
    print(f"   Root cause type distribution:")
    for rca_type, count in sorted(type_distribution.items(), key=lambda x: -x[1]):
        print(f"      - {rca_type}: {count} ({count/len(examples)*100:.1f}%)")

    # Check for imbalance
    max_percentage = max(type_distribution.values()) / len(examples)
    if max_percentage > 0.4:
        print(f"   ⚠️  WARNING: Data imbalanced ({max_percentage*100:.1f}% is one type)")
    else:
        print(f"   ✅ Data well-balanced")
```

---

## Phase 3: Optimization (2-3 Days)

### Step 3.1: Configure PromptWizard

Create configuration file:

```yaml
# promptopt_config.yaml

task_description: |
  Analyze AWS Lambda function incidents and identify the root cause.
  Given incident metadata (title, summary, error messages, configuration),
  determine the primary root cause with high confidence and provide evidence.

base_instruction: |
  You are an expert AWS Lambda specialist investigating production incidents.
  Analyze the provided incident information systematically and identify the root cause.
  Base your analysis ONLY on provided evidence.

answer_format: |
  Return JSON with:
  {
    "root_cause": "Detailed description of the root cause",
    "root_cause_type": "One of: timeout, permission_issue, code_bug, configuration_error, resource_constraint",
    "confidence": 0.0-1.0,
    "evidence": ["fact1", "fact2"],
    "recommendation": "Specific actionable recommendation"
  }

# Optimization parameters (from eARCO paper)
optimization:
  mutate_refine_iterations: 3        # Number of Mutate→Critique→Synthesize cycles
  mutation_rounds: 3                  # Variations generated per mutation
  refine_task_eg_iterations: 3       # Iterations for refining examples
  questions_batch_size: 5            # Examples tested per batch
  min_correct_count: 3               # Min batches to pass to next stage
  few_shot_count: 10                 # Number of in-context examples in final prompt

# Model configuration
model:
  name: "gpt-4o"
  temperature: 0.0                   # Deterministic for optimization
  max_tokens: 2000
```

### Step 3.2: Create Optimization Script

```python
# scripts/optimize_lambda.py

import os
import json
import yaml
from pathlib import Path
from datetime import datetime

# Import PromptWizard (adjust based on actual API)
from promptwizard import PromptOptimizer

def optimize_lambda_agent():
    """Optimize Lambda agent prompt using PromptWizard."""

    print("🚀 Starting Lambda Agent Prompt Optimization")
    print("=" * 60)

    # 1. Load configuration
    with open('promptopt_config.yaml') as f:
        config = yaml.safe_load(f)

    print(f"📋 Configuration loaded:")
    print(f"   - Optimization iterations: {config['optimization']['mutate_refine_iterations']}")
    print(f"   - Few-shot examples: {config['optimization']['few_shot_count']}")

    # 2. Load training data
    with open('../training_data/lambda_incidents.json') as f:
        data = json.load(f)

    training_examples = data['examples']
    validation_examples = data.get('validation_examples', [])

    print(f"📊 Data loaded:")
    print(f"   - Training examples: {len(training_examples)}")
    print(f"   - Validation examples: {len(validation_examples)}")

    # 3. Initialize PromptWizard
    optimizer = PromptOptimizer(
        task_description=config['task_description'],
        base_instruction=config['base_instruction'],
        answer_format=config['answer_format'],
        model_name=config['model']['name'],
        **config['optimization']
    )

    # 4. Run optimization
    print(f"\n🔄 Starting optimization (this will take 1-3 hours)...")
    print(f"💰 Estimated cost: ~$5-10 for ~100 API calls\n")

    start_time = datetime.now()

    result = optimizer.optimize(
        training_examples=training_examples,
        validation_examples=validation_examples,
        verbose=True  # Print progress
    )

    duration = (datetime.now() - start_time).total_seconds() / 60

    # 5. Extract results
    optimized_prompt = result['optimized_prompt']
    optimized_examples = result.get('optimized_examples', [])
    metrics = result['metrics']

    print(f"\n✅ Optimization complete in {duration:.1f} minutes!")
    print(f"📊 Results:")
    print(f"   - Training accuracy: {metrics['training_accuracy']:.2%}")
    print(f"   - Validation accuracy: {metrics['validation_accuracy']:.2%}")
    print(f"   - Improvement: {metrics['improvement']:.2%}")
    print(f"   - Total API calls: {metrics['total_api_calls']}")
    print(f"   - Estimated cost: ${metrics['estimated_cost']:.2f}")

    # 6. Save optimized prompt
    output_dir = Path('../optimized_prompts')
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save prompt
    prompt_file = output_dir / f'lambda_agent_optimized_{timestamp}.txt'
    with open(prompt_file, 'w') as f:
        f.write(optimized_prompt)

    # Save metadata
    metadata_file = output_dir / f'lambda_agent_metadata_{timestamp}.json'
    with open(metadata_file, 'w') as f:
        json.dump({
            'timestamp': timestamp,
            'config': config,
            'metrics': metrics,
            'optimized_examples': optimized_examples
        }, f, indent=2)

    print(f"\n💾 Saved:")
    print(f"   - Prompt: {prompt_file}")
    print(f"   - Metadata: {metadata_file}")

    return optimized_prompt, metrics

if __name__ == "__main__":
    try:
        optimized_prompt, metrics = optimize_lambda_agent()
        print("\n🎉 Success! Optimized prompt is ready for testing.")
    except Exception as e:
        print(f"\n❌ Error during optimization: {e}")
        import traceback
        traceback.print_exc()
```

### Step 3.3: Run Optimization

```bash
cd promptrca-optimization/scripts

# Set environment variables
export OPENAI_API_KEY="your-key-here"

# Run optimization (1-3 hours)
python optimize_lambda.py

# Expected output:
# 🚀 Starting Lambda Agent Prompt Optimization
# ============================================================
# 📋 Configuration loaded
# 📊 Data loaded: 25 training, 5 validation
#
# 🔄 Iteration 1/3: Mutating prompts...
#    Generated 3 variations
#    Testing on 5 batches of 5 examples each...
#    Best score: 0.68 (17/25 correct)
#
# 🔄 Iteration 2/3: Critiquing and synthesizing...
#    Critique: "Prompt should emphasize checking configuration timeline..."
#    New score: 0.76 (19/25 correct)
#
# 🔄 Iteration 3/3: Final refinement...
#    Final score: 0.84 (21/25 correct)
#    Validation score: 0.80 (4/5 correct)
#
# ✅ Optimization complete in 127.3 minutes!
# 📊 Results:
#    - Training accuracy: 84.00%
#    - Validation accuracy: 80.00%
#    - Improvement: 23.00%
#    - Total API calls: 97
#    - Estimated cost: $7.82
```

### Step 3.4: Review Optimized Prompt

```bash
# View the optimized prompt
cat ../optimized_prompts/lambda_agent_optimized_20250118_143022.txt
```

**What to look for:**
- ✅ More specific instructions than original
- ✅ Structured step-by-step methodology
- ✅ Evidence-based reasoning emphasis
- ✅ Domain-specific terminology (Lambda, timeout, memory, etc.)
- ✅ Clear output format specification
- ✅ Potentially includes few-shot examples

---

## Phase 4: Evaluation (2-3 Days)

### Step 4.1: Create Test Set

**Separate test set** (not used during optimization):

```json
{
  "test_cases": [
    {
      "id": "test_001",
      "input": "INCIDENT TITLE: ...",
      "ground_truth": {
        "root_cause": "...",
        "root_cause_type": "timeout",
        "confidence": 0.85
      },
      "metadata": {
        "severity": "high",
        "service": "lambda",
        "verified_by": "john.doe@company.com",
        "date": "2024-12-15"
      }
    }
    // ... 9 more test cases
  ]
}
```

### Step 4.2: Create Evaluation Script

```python
# scripts/evaluate_prompts.py

import json
from pathlib import Path
from typing import List, Dict, Tuple
from strands import Agent
from promptrca.utils.config import create_lambda_agent_model

def load_test_cases(file_path: str) -> List[Dict]:
    """Load test cases from JSON file."""
    with open(file_path) as f:
        data = json.load(f)
    return data['test_cases']

def calculate_accuracy(predicted: Dict, ground_truth: Dict) -> float:
    """Calculate accuracy score for a prediction."""
    scores = []

    # 1. Root cause type match (40% weight)
    type_match = 1.0 if predicted['root_cause_type'] == ground_truth['root_cause_type'] else 0.0
    scores.append(type_match * 0.4)

    # 2. Semantic similarity of root cause description (40% weight)
    # Use GPT-4 as judge (simplified for now)
    similarity = calculate_semantic_similarity(
        predicted['root_cause'],
        ground_truth['root_cause']
    )
    scores.append(similarity * 0.4)

    # 3. Confidence calibration (20% weight)
    confidence_diff = abs(predicted['confidence'] - ground_truth['confidence'])
    confidence_score = max(0, 1.0 - confidence_diff)
    scores.append(confidence_score * 0.2)

    return sum(scores)

def calculate_semantic_similarity(text1: str, text2: str) -> float:
    """Use GPT-4 to judge semantic similarity."""
    from openai import OpenAI
    client = OpenAI()

    prompt = f"""Rate the semantic similarity between these two root cause analyses on a scale of 0.0 to 1.0:

Root Cause 1: {text1}

Root Cause 2: {text2}

Respond with ONLY a number between 0.0 and 1.0."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0
    )

    try:
        return float(response.choices[0].message.content.strip())
    except:
        return 0.5  # Default if parsing fails

def evaluate_agent(agent: Agent, test_cases: List[Dict]) -> Dict:
    """Evaluate agent on test cases."""
    results = []

    for test_case in test_cases:
        print(f"Testing: {test_case['id']}...", end=' ')

        # Run agent
        response = agent(test_case['input'])

        # Parse response (assuming JSON output)
        try:
            predicted = json.loads(str(response))
        except:
            # Try to extract JSON from markdown
            import re
            json_match = re.search(r'```json\n(.*?)\n```', str(response), re.DOTALL)
            if json_match:
                predicted = json.loads(json_match.group(1))
            else:
                predicted = {
                    "root_cause": str(response),
                    "root_cause_type": "unknown",
                    "confidence": 0.5
                }

        # Calculate accuracy
        accuracy = calculate_accuracy(predicted, test_case['ground_truth'])

        results.append({
            'test_id': test_case['id'],
            'predicted': predicted,
            'ground_truth': test_case['ground_truth'],
            'accuracy': accuracy
        })

        print(f"✓ (accuracy: {accuracy:.2%})")

    # Calculate aggregate metrics
    avg_accuracy = sum(r['accuracy'] for r in results) / len(results)

    return {
        'results': results,
        'avg_accuracy': avg_accuracy,
        'total_tests': len(test_cases)
    }

def compare_prompts():
    """Compare manual vs optimized prompts."""

    print("🧪 Evaluating Lambda Agent Prompts")
    print("=" * 60)

    # Load test cases
    test_cases = load_test_cases('../evaluation/test_cases.json')
    print(f"📋 Loaded {len(test_cases)} test cases\n")

    # 1. Test MANUAL prompt (baseline)
    print("🔵 Testing MANUAL prompt (baseline)...")
    from promptrca.agents.specialized.lambda_agent import create_lambda_agent

    manual_agent = create_lambda_agent(create_lambda_agent_model())
    manual_results = evaluate_agent(manual_agent, test_cases)

    print(f"   Average accuracy: {manual_results['avg_accuracy']:.2%}\n")

    # 2. Test OPTIMIZED prompt
    print("🟢 Testing OPTIMIZED prompt (PromptWizard)...")

    # Load optimized prompt
    optimized_prompt_file = sorted(Path('../optimized_prompts').glob('lambda_agent_optimized_*.txt'))[-1]
    with open(optimized_prompt_file) as f:
        optimized_prompt = f.read()

    # Create agent with optimized prompt
    optimized_agent = Agent(
        model=create_lambda_agent_model(),
        system_prompt=optimized_prompt,
        tools=manual_agent.tools  # Same tools
    )

    optimized_results = evaluate_agent(optimized_agent, test_cases)

    print(f"   Average accuracy: {optimized_results['avg_accuracy']:.2%}\n")

    # 3. Calculate improvement
    improvement = optimized_results['avg_accuracy'] - manual_results['avg_accuracy']
    improvement_pct = (improvement / manual_results['avg_accuracy']) * 100

    print("📊 COMPARISON")
    print("=" * 60)
    print(f"Manual Prompt:     {manual_results['avg_accuracy']:.2%}")
    print(f"Optimized Prompt:  {optimized_results['avg_accuracy']:.2%}")
    print(f"Absolute Gain:     {improvement:+.2%}")
    print(f"Relative Gain:     {improvement_pct:+.1f}%")

    if improvement_pct >= 15:
        print(f"\n🎉 SUCCESS! Improvement meets/exceeds eARCO paper target (15-21%)")
    elif improvement_pct >= 5:
        print(f"\n✅ Good improvement, consider collecting more training data")
    else:
        print(f"\n⚠️  Limited improvement, review training data quality")

    # 4. Save detailed results
    output_file = Path('../evaluation/results.json')
    with open(output_file, 'w') as f:
        json.dump({
            'manual_results': manual_results,
            'optimized_results': optimized_results,
            'improvement': {
                'absolute': improvement,
                'relative_pct': improvement_pct
            },
            'timestamp': datetime.now().isoformat()
        }, f, indent=2)

    print(f"\n💾 Detailed results saved to: {output_file}")

if __name__ == "__main__":
    compare_prompts()
```

### Step 4.3: Run Evaluation

```bash
python scripts/evaluate_prompts.py
```

**Expected Output:**
```
🧪 Evaluating Lambda Agent Prompts
============================================================
📋 Loaded 10 test cases

🔵 Testing MANUAL prompt (baseline)...
Testing: test_001... ✓ (accuracy: 72%)
Testing: test_002... ✓ (accuracy: 68%)
Testing: test_003... ✓ (accuracy: 85%)
...
   Average accuracy: 74.50%

🟢 Testing OPTIMIZED prompt (PromptWizard)...
Testing: test_001... ✓ (accuracy: 88%)
Testing: test_002... ✓ (accuracy: 91%)
Testing: test_003... ✓ (accuracy: 94%)
...
   Average accuracy: 89.20%

📊 COMPARISON
============================================================
Manual Prompt:     74.50%
Optimized Prompt:  89.20%
Absolute Gain:     +14.70%
Relative Gain:     +19.7%

🎉 SUCCESS! Improvement meets/exceeds eARCO paper target (15-21%)
```

### Step 4.4: Analyze Results

**Review detailed results:**
```python
# View which test cases improved most
import json

with open('../evaluation/results.json') as f:
    results = json.load(f)

manual = results['manual_results']['results']
optimized = results['optimized_results']['results']

print("Per-test improvements:")
for m, o in zip(manual, optimized):
    improvement = o['accuracy'] - m['accuracy']
    print(f"{m['test_id']}: {improvement:+.1%}")
    if improvement < 0:
        print(f"  ⚠️  Regression - investigate this case")
        print(f"     Manual: {m['predicted']['root_cause'][:50]}...")
        print(f"     Optimized: {o['predicted']['root_cause'][:50]}...")
```

---

## Phase 5: Deployment (1 Day)

### Step 5.1: Create Deployment Script

```python
# scripts/deploy_optimized_prompt.py

import shutil
from pathlib import Path
from datetime import datetime

def deploy_optimized_prompt(agent_name: str, dry_run: bool = True):
    """Deploy optimized prompt to production."""

    print(f"🚀 Deploying optimized {agent_name} prompt")
    print("=" * 60)

    # 1. Locate latest optimized prompt
    optimized_dir = Path('../optimized_prompts')
    prompt_files = sorted(optimized_dir.glob(f'{agent_name}_optimized_*.txt'))

    if not prompt_files:
        print(f"❌ No optimized prompt found for {agent_name}")
        return False

    latest_prompt = prompt_files[-1]
    print(f"📄 Latest optimized prompt: {latest_prompt.name}")

    # 2. Backup current prompt
    agent_file = Path(f'../../src/promptrca/agents/specialized/{agent_name}_agent.py')

    if not agent_file.exists():
        print(f"❌ Agent file not found: {agent_file}")
        return False

    backup_dir = Path('../backups')
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f'{agent_name}_agent_backup_{timestamp}.py'

    if not dry_run:
        shutil.copy(agent_file, backup_file)
        print(f"💾 Backed up current prompt to: {backup_file}")
    else:
        print(f"💾 [DRY RUN] Would backup to: {backup_file}")

    # 3. Read optimized prompt
    with open(latest_prompt) as f:
        optimized_prompt = f.read()

    # 4. Update agent file
    # This is a simplified version - actual implementation depends on your code structure
    if not dry_run:
        # Read current agent file
        with open(agent_file) as f:
            agent_code = f.read()

        # Find and replace system_prompt
        import re
        pattern = r'system_prompt = """.*?"""'
        replacement = f'system_prompt = """{optimized_prompt}"""'

        updated_code = re.sub(pattern, replacement, agent_code, flags=re.DOTALL)

        # Write updated code
        with open(agent_file, 'w') as f:
            f.write(updated_code)

        print(f"✅ Updated {agent_file}")
    else:
        print(f"✅ [DRY RUN] Would update {agent_file}")

    # 5. Run quick smoke test
    if not dry_run:
        print(f"\n🧪 Running smoke test...")
        # Import and test the updated agent
        # ... (add smoke test code)

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Deployment complete!")

    if dry_run:
        print(f"\n💡 Run with dry_run=False to actually deploy")

    return True

if __name__ == "__main__":
    import sys

    agent_name = sys.argv[1] if len(sys.argv) > 1 else "lambda"
    dry_run = "--confirm" not in sys.argv

    if dry_run:
        print("⚠️  DRY RUN MODE - No changes will be made")
        print("   Add --confirm flag to actually deploy\n")

    deploy_optimized_prompt(agent_name, dry_run)
```

### Step 5.2: Deploy with A/B Testing

**Option A: Gradual Rollout** (Recommended)

```python
# Implement A/B testing to compare prompts in production

class PromptRouter:
    """Route requests to manual or optimized prompt based on percentage."""

    def __init__(self, optimized_percentage: float = 0.1):
        self.optimized_percentage = optimized_percentage
        self.manual_agent = create_lambda_agent(model)

        # Load optimized prompt
        with open('optimized_prompts/lambda_agent_optimized_latest.txt') as f:
            optimized_prompt = f.read()

        self.optimized_agent = Agent(
            model=model,
            system_prompt=optimized_prompt,
            tools=self.manual_agent.tools
        )

    def investigate(self, incident):
        """Route to appropriate agent."""
        import random

        # Route based on percentage
        if random.random() < self.optimized_percentage:
            return self.optimized_agent(incident), "optimized"
        else:
            return self.manual_agent(incident), "manual"

# Start with 10% traffic, gradually increase
router = PromptRouter(optimized_percentage=0.10)
```

**Option B: Full Deployment**

```bash
# After validation, deploy to all agents
python scripts/deploy_optimized_prompt.py lambda --confirm
python scripts/deploy_optimized_prompt.py apigateway --confirm
# ... etc
```

### Step 5.3: Monitor Performance

```python
# scripts/monitor_prompt_performance.py

import json
from datetime import datetime, timedelta
from collections import defaultdict

def monitor_performance(days: int = 7):
    """Monitor deployed prompt performance."""

    # Load investigation logs
    logs = load_investigation_logs(days=days)

    # Group by prompt version
    metrics = defaultdict(list)

    for log in logs:
        prompt_version = log.get('prompt_version', 'manual')

        # Calculate metrics
        accuracy = calculate_accuracy(log['predicted'], log['actual'])
        confidence = log['predicted'].get('confidence', 0.5)

        metrics[prompt_version].append({
            'accuracy': accuracy,
            'confidence': confidence,
            'timestamp': log['timestamp']
        })

    # Print comparison
    print("📊 Prompt Performance (Last 7 days)")
    print("=" * 60)

    for version, data in metrics.items():
        avg_accuracy = sum(d['accuracy'] for d in data) / len(data)
        avg_confidence = sum(d['confidence'] for d in data) / len(data)

        print(f"\n{version.upper()}:")
        print(f"  Investigations: {len(data)}")
        print(f"  Avg Accuracy: {avg_accuracy:.2%}")
        print(f"  Avg Confidence: {avg_confidence:.2f}")

    # Check if optimized is significantly better
    if 'optimized' in metrics and 'manual' in metrics:
        opt_acc = sum(d['accuracy'] for d in metrics['optimized']) / len(metrics['optimized'])
        man_acc = sum(d['accuracy'] for d in metrics['manual']) / len(metrics['manual'])

        improvement = (opt_acc - man_acc) / man_acc * 100

        if improvement > 10:
            print(f"\n✅ Optimized prompt performing {improvement:.1f}% better - continue rollout")
        elif improvement > 0:
            print(f"\n⚠️  Optimized prompt only {improvement:.1f}% better - monitor closely")
        else:
            print(f"\n❌ Optimized prompt underperforming by {abs(improvement):.1f}% - consider rollback")
```

---

## Troubleshooting

### Common Issues

#### Issue 1: Low Training Accuracy (<70%)

**Symptoms:**
- PromptWizard optimization completes but training accuracy is low
- Validation accuracy even lower

**Possible Causes:**
1. Insufficient or poor quality training data
2. Inconsistent ground truth labels
3. Task too complex for current prompt structure
4. Model not powerful enough (using GPT-3.5 instead of GPT-4)

**Solutions:**
```bash
# 1. Review training data quality
python scripts/validate_training_data.py

# 2. Check for label consistency
python scripts/check_label_consistency.py

# 3. Increase model capability
# In .env, change:
OPENAI_MODEL_NAME="gpt-4o"  # Instead of gpt-3.5-turbo

# 4. Add more training examples
# Collect 10-15 more diverse incidents
```

#### Issue 2: Optimization Takes Too Long (>5 hours)

**Symptoms:**
- Optimization running for many hours
- High API costs

**Possible Causes:**
1. Too many training examples
2. Too many optimization iterations
3. Large batch sizes
4. API rate limiting

**Solutions:**
```yaml
# Reduce parameters in promptopt_config.yaml:
optimization:
  mutate_refine_iterations: 2     # Down from 3
  mutation_rounds: 2               # Down from 3
  questions_batch_size: 3          # Down from 5

# Or reduce training data:
training_examples = data['examples'][:15]  # Use only 15 instead of 25
```

#### Issue 3: Optimized Prompt Performs Worse

**Symptoms:**
- Evaluation shows optimized prompt has lower accuracy
- Production metrics show regression

**Possible Causes:**
1. Overfitting to training data
2. Training data not representative
3. Test set too different from training set
4. Prompt optimization got stuck in local optimum

**Solutions:**
```python
# 1. Check train/test distribution
python scripts/analyze_data_distribution.py

# 2. Increase training data diversity
# Add more varied incident types

# 3. Re-run optimization with different seed
# In config:
optimization:
  random_seed: 12345  # Try different values

# 4. Try multiple optimization runs and pick best
for seed in [42, 123, 456]:
    optimize_with_seed(seed)
```

#### Issue 4: PromptWizard Installation Fails

**Symptoms:**
```
ERROR: Could not build wheels for promptwizard
```

**Solutions:**
```bash
# 1. Update pip and setuptools
pip install --upgrade pip setuptools wheel

# 2. Install dependencies separately
pip install openai pydantic PyYAML

# 3. Clone and install from source
git clone https://github.com/microsoft/PromptWizard
cd PromptWizard
pip install -r requirements.txt
pip install -e .
```

#### Issue 5: API Cost Too High

**Symptoms:**
- Single optimization costing >$50
- Multiple agents would cost >$500

**Solutions:**
```python
# 1. Use cheaper model for initial iterations
# In config:
model:
  name: "gpt-3.5-turbo"  # Cheaper, then upgrade to gpt-4o

# 2. Reduce data
training_examples = data['examples'][:15]

# 3. Optimize one agent at a time
# Focus on most-used agent first (Lambda)

# 4. Use cached results
# PromptWizard caches intermediate results
```

---

## Cost Estimation

### Per-Agent Costs

| Component | GPT-3.5-Turbo | GPT-4 | GPT-4o |
|-----------|---------------|-------|--------|
| **Optimization** (~100 calls) | $2-5 | $15-30 | $8-15 |
| **Evaluation** (~20 calls) | $0.50-1 | $3-5 | $1.50-3 |
| **Total per Agent** | **$2.50-6** | **$18-35** | **$9.50-18** |

### Total Project Costs

| Scope | GPT-3.5-Turbo | GPT-4 | GPT-4o (Recommended) |
|-------|---------------|-------|----------------------|
| **Single Agent** (Lambda) | $3-6 | $18-35 | $10-18 |
| **Top 3 Agents** (Lambda, API GW, Step Functions) | $8-18 | $54-105 | $30-54 |
| **All 11 Agents** | $28-66 | $198-385 | $105-198 |

**Recommendation:** Start with GPT-4o for Lambda agent ($10-18), measure ROI, then expand.

---

## Expected Timeline

### Conservative Estimate (First Agent)

| Phase | Duration | Effort |
|-------|----------|--------|
| **Setup** | 1 day | 2-4 hours |
| **Data Collection** | 3-5 days | 8-16 hours |
| **Optimization** | 1 day | 1-3 hours runtime + monitoring |
| **Evaluation** | 2-3 days | 4-8 hours |
| **Deployment** | 1 day | 2-4 hours |
| **Total** | **8-11 days** | **17-35 hours** |

### Subsequent Agents

After first agent, each additional agent takes ~3-5 days (reuse scripts/process).

---

## Success Criteria

### Minimum Viable Success
- ✅ Training accuracy > 75%
- ✅ Validation accuracy > 70%
- ✅ Test set improvement > 10%
- ✅ No major regressions on any test case

### Target Success (eARCO Paper)
- 🎯 Training accuracy > 85%
- 🎯 Validation accuracy > 80%
- 🎯 Test set improvement > 15%
- 🎯 Production metrics stable/improved

### Exceptional Success
- 🏆 Training accuracy > 90%
- 🏆 Validation accuracy > 85%
- 🏆 Test set improvement > 20%
- 🏆 Reduced time-to-resolution in production

---

## References

### Papers
1. **eARCO Paper** (Microsoft, 2025)
   - Title: "eARCO: Efficient Automated Root Cause Analysis with Prompt Optimization"
   - arXiv: 2504.11505v1
   - Key Result: 21% accuracy improvement with PromptWizard

2. **PromptWizard Paper** (Microsoft Research, 2024)
   - Title: "PromptWizard: Task-Aware Agent-driven Prompt Optimization Framework"
   - arXiv: 2405.18369
   - Authors: Eshaan Agarwal et al.

### Tools
- **PromptWizard GitHub**: https://github.com/microsoft/PromptWizard
- **PromptWizard Docs**: https://microsoft.github.io/PromptWizard/
- **OpenAI API**: https://platform.openai.com/docs/api-reference

### PromptRCA Resources
- **Current Prompts**: `/src/promptrca/agents/specialized/`
- **This Guide**: `/docs/PROMPTWIZARD_GUIDE.md`
- **Training Data Template**: (create at `/promptrca-optimization/training_data/`)

---

## Next Steps

1. **Review this guide** thoroughly
2. **Decide on scope**: Single agent vs multiple agents
3. **Begin data collection** (most time-consuming step)
4. **Set up PromptWizard** when data is ready
5. **Run optimization** on Lambda agent first
6. **Measure and decide** whether to expand

**Questions or need help?** Review the Troubleshooting section or refer to the PromptWizard documentation.

---

**Document Version:** 1.0
**Last Updated:** January 2025
**Author:** PromptRCA Team
**Status:** Ready for Implementation
