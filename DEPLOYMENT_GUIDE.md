# DirectInvocationOrchestrator Deployment Guide

**Version:** 1.0
**Date:** 2025-10-20
**Status:** Ready for Canary Deployment

---

## Overview

This guide covers the deployment of the new **DirectInvocationOrchestrator** (code-based orchestration) alongside the existing **LeadOrchestratorAgent** (agents-as-tools pattern).

Both orchestrators run side-by-side with feature-flag-based traffic routing for safe, gradual rollout.

---

## Architecture Comparison

### Old Pattern: Agents-as-Tools
```
LeadAgent (Strands) [55 tools]
  → @tool investigate_lambda_function()
    → LambdaAgent (Strands) [NEW LLM call + 1,500 token prompt]
      → get_lambda_config() [AWS API]

Tokens: ~17,500/investigation
Latency: 10-15s (sequential)
Predictability: 70% (LLM routing)
```

### New Pattern: Direct Invocation
```
DirectOrchestrator (Python)
  → Resource Discovery (Python + tools, no LLM)
  → LambdaAgent (Strands) [Direct call]
    → get_lambda_config() [AWS API]

Tokens: ~5,000-6,000/investigation (70% reduction)
Latency: 3-5s (parallel execution)
Predictability: 99% (deterministic Python)
```

---

## Feature Flags

### Environment Variables

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `PROMPTRCA_USE_DIRECT_ORCHESTRATION` | `true`/`false` | `false` | Enable direct orchestration |
| `PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE` | `0-100` | `100` | Percentage of traffic to route to new orchestrator |
| `PROMPTRCA_FORCE_ORCHESTRATOR` | `direct`/`agent_tools` | (none) | Force specific orchestrator (for testing) |

### Usage Examples

#### 1. Disable (Use Legacy Only)
```bash
# Default - no environment variables needed
# OR explicitly disable
export PROMPTRCA_USE_DIRECT_ORCHESTRATION=false
```

#### 2. Enable for 10% of Traffic (Canary)
```bash
export PROMPTRCA_USE_DIRECT_ORCHESTRATION=true
export PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE=10
```

#### 3. Enable for 50% of Traffic
```bash
export PROMPTRCA_USE_DIRECT_ORCHESTRATION=true
export PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE=50
```

#### 4. Enable for All Traffic
```bash
export PROMPTRCA_USE_DIRECT_ORCHESTRATION=true
export PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE=100
# OR just:
export PROMPTRCA_USE_DIRECT_ORCHESTRATION=true
```

#### 5. Force Direct Orchestration (Testing)
```bash
export PROMPTRCA_FORCE_ORCHESTRATOR=direct
```

#### 6. Force Legacy Orchestration (Testing)
```bash
export PROMPTRCA_FORCE_ORCHESTRATOR=agent_tools
```

---

## Deployment Phases

### Phase 0: Pre-Deployment (Complete ✅)
- [x] Implement DirectInvocationOrchestrator
- [x] Create feature flag system
- [x] Update entry point (PromptRCAInvestigator)
- [x] Add metrics tracking

### Phase 1: Canary Deployment (Week 1)

**Objective:** Validate new orchestrator with 10% of production traffic

**Steps:**
```bash
# 1. Deploy code to production
git pull origin main

# 2. Set environment variables for 10% canary
export PROMPTRCA_USE_DIRECT_ORCHESTRATION=true
export PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE=10

# 3. Restart service
# (specific command depends on your deployment method)

# 4. Monitor metrics for 48-72 hours
```

**Success Criteria:**
- ✅ 0 errors from DirectInvocationOrchestrator
- ✅ Latency reduction: ≥50% (target: 3-5x faster)
- ✅ Token reduction: ≥60% (target: 70%)
- ✅ Root cause confidence: ≥ same as legacy (0.75+)
- ✅ Facts found: ≥ same as legacy (4-6 per investigation)

**Rollback Plan:**
```bash
# If issues detected, immediately revert to 0%
export PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE=0
# OR disable entirely
export PROMPTRCA_USE_DIRECT_ORCHESTRATION=false
```

### Phase 2: Gradual Rollout (Week 2)

**Objective:** Expand to 25% → 50% based on Phase 1 success

**25% Rollout:**
```bash
export PROMPTRCA_USE_DIRECT_ORCHESTRATION=true
export PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE=25
```

Monitor for 48 hours, then:

**50% Rollout:**
```bash
export PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE=50
```

Monitor for 48 hours.

### Phase 3: Full Rollout (Week 3)

**Objective:** Route all traffic to DirectInvocationOrchestrator

```bash
export PROMPTRCA_USE_DIRECT_ORCHESTRATION=true
export PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE=100
```

Monitor for 1 week.

### Phase 4: Cleanup (Week 4+)

After 2 weeks of stable 100% rollout:
- Remove `PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE` (default to 100%)
- Document deprecation of LeadOrchestratorAgent
- Plan removal of legacy code in 3-6 months

---

## Monitoring & Metrics

### Key Metrics to Track

**Performance Metrics:**
```python
# These are automatically logged in the investigation report
{
  "orchestrator_type": "direct_invocation" | "agent_tools",
  "duration_seconds": 3.2,
  "facts": 5,
  "hypotheses": 3,
  "root_cause_confidence": 0.85
}
```

**Dashboard Queries (CloudWatch Logs Insights):**

#### 1. Orchestrator Distribution
```
fields orchestrator_type, @timestamp
| stats count() by orchestrator_type
```

#### 2. Average Duration by Orchestrator
```
fields orchestrator_type, duration_seconds
| stats avg(duration_seconds) by orchestrator_type
```

#### 3. Root Cause Confidence by Orchestrator
```
fields orchestrator_type, root_cause_confidence
| stats avg(root_cause_confidence) by orchestrator_type
```

#### 4. Error Rate by Orchestrator
```
fields orchestrator_type, status
| stats count() by orchestrator_type, status
```

### Expected Metrics

| Metric | Legacy (Agents-as-Tools) | New (Direct Invocation) | Target Improvement |
|--------|-------------------------|------------------------|--------------------|
| Avg Duration | 10-15s | 3-5s | **3-5x faster** |
| Avg Tokens | 17,500 | 5,000-6,000 | **70% reduction** |
| Root Cause Confidence | 0.75 | ≥0.75 | **Maintain or improve** |
| Facts Found | 4-6 | ≥4 | **Maintain or improve** |
| Error Rate | <5% | <5% | **Same or better** |

---

## Testing Locally

### Test Direct Orchestration
```bash
export PROMPTRCA_FORCE_ORCHESTRATOR=direct

python -m promptrca.cli investigate \
  --function-name my-lambda-function \
  --region us-east-1
```

### Test Legacy Orchestration
```bash
export PROMPTRCA_FORCE_ORCHESTRATOR=agent_tools

python -m promptrca.cli investigate \
  --function-name my-lambda-function \
  --region us-east-1
```

### Compare Side-by-Side
```bash
# Run 10 investigations with direct orchestrator
export PROMPTRCA_FORCE_ORCHESTRATOR=direct
for i in {1..10}; do
  python -m promptrca.cli investigate --function-name my-lambda-function | tee direct_$i.json
done

# Run 10 investigations with legacy orchestrator
export PROMPTRCA_FORCE_ORCHESTRATOR=agent_tools
for i in {1..10}; do
  python -m promptrca.cli investigate --function-name my-lambda-function | tee legacy_$i.json
done

# Compare results
python scripts/compare_orchestrators.py direct_*.json legacy_*.json
```

---

## Troubleshooting

### Issue: DirectInvocationOrchestrator not being used

**Check:**
```bash
# Verify environment variables
echo $PROMPTRCA_USE_DIRECT_ORCHESTRATION
echo $PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE

# Check logs for orchestrator selection
grep "Orchestrator Type:" /var/log/promptrca.log
```

**Solution:**
Ensure `PROMPTRCA_USE_DIRECT_ORCHESTRATION=true` is set and service is restarted.

### Issue: High error rate with DirectInvocationOrchestrator

**Check:**
```bash
# Check specialist failures
grep "specialist failed" /var/log/promptrca.log

# Check resource discovery failures
grep "Failed to extract resources" /var/log/promptrca.log
```

**Solution:**
1. Check AWS credentials/permissions
2. Verify specialist agents are properly initialized
3. Review error logs for specific failures
4. If widespread, rollback to legacy: `export PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE=0`

### Issue: Lower root cause confidence than legacy

**Check:**
```bash
# Compare confidence scores
grep "Root Cause Confidence" /var/log/promptrca.log | grep "direct_invocation"
grep "Root Cause Confidence" /var/log/promptrca.log | grep "agent_tools"
```

**Solution:**
1. This might indicate specialists need more context
2. Review specialist prompts in `_create_specialist_prompt()`
3. Consider adding more error context to prompts
4. Compare Facts/Hypotheses counts between orchestrators

---

## Rollback Procedure

### Emergency Rollback (Immediate)

If critical issues are detected:

```bash
# Option 1: Disable direct orchestration entirely
export PROMPTRCA_USE_DIRECT_ORCHESTRATION=false

# Option 2: Set percentage to 0
export PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE=0

# Restart service
systemctl restart promptrca  # or your restart command
```

**Verification:**
```bash
# Check logs - should see "AGENTS-AS-TOOLS ORCHESTRATION"
tail -f /var/log/promptrca.log | grep "Orchestrator Type"
```

### Gradual Rollback

If issues are non-critical but concerning:

```bash
# Reduce from 50% → 25%
export PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE=25

# Monitor for 24 hours

# If still concerning, reduce to 10%
export PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE=10

# If issues persist, disable
export PROMPTRCA_USE_DIRECT_ORCHESTRATION=false
```

---

## Success Criteria

Before proceeding to next phase, verify:

### Phase 1 → Phase 2 (10% → 25%)
- ✅ Zero critical errors from DirectInvocationOrchestrator
- ✅ Latency improvement ≥50%
- ✅ Token reduction ≥60%
- ✅ Root cause confidence maintained (≥0.70)
- ✅ Facts count maintained (≥3 per investigation)

### Phase 2 → Phase 3 (50% → 100%)
- ✅ All Phase 1 criteria maintained
- ✅ No degradation in quality metrics at 50%
- ✅ User feedback positive (if applicable)
- ✅ Cost savings validated (~70% reduction in LLM costs)

### Phase 3 → Phase 4 (100% → Deprecate Legacy)
- ✅ All metrics stable at 100% for 2+ weeks
- ✅ No rollbacks or incidents
- ✅ Team confident in new orchestrator
- ✅ Documentation updated

---

## FAQ

### Q: Can I run both orchestrators for the same investigation?
**A:** No. Feature flags route each investigation to ONE orchestrator. However, you can compare results by running two separate investigations with `PROMPTRCA_FORCE_ORCHESTRATOR`.

### Q: What happens if I change the percentage while the service is running?
**A:** New investigations will use the new percentage. In-flight investigations continue with their selected orchestrator.

### Q: How is the percentage calculated?
**A:** Via consistent hashing on the investigation ID. Same investigation ID → same orchestrator choice (deterministic for debugging).

### Q: Can I A/B test specific customers?
**A:** Yes, use `PROMPTRCA_FORCE_ORCHESTRATOR` in customer-specific environments.

### Q: What if DirectInvocationOrchestrator fails?
**A:** It will return an error report (same as legacy). The investigation won't fail silently.

### Q: How do I know which orchestrator was used for a specific investigation?
**A:** Check the `orchestrator_type` field in the investigation report summary, or check logs for "Orchestrator Type".

---

## Contact

For issues or questions during deployment:
- **Email:** christiangenn99+promptrca@gmail.com
- **Documentation:** See `MIGRATION_TO_CODE_ORCHESTRATION.md` for architecture details

---

## Checklist for Deployment

### Pre-Deployment
- [ ] Code merged to main branch
- [ ] Feature flags tested locally
- [ ] Metrics dashboard created
- [ ] Rollback procedure documented
- [ ] Team notified of deployment

### Phase 1 (10% Canary)
- [ ] Environment variables set (`USE_DIRECT_ORCHESTRATION=true`, `PERCENTAGE=10`)
- [ ] Service restarted
- [ ] Logs monitored for errors
- [ ] Metrics dashboard checked (latency, tokens, confidence)
- [ ] 48-72 hours of monitoring completed
- [ ] Success criteria met

### Phase 2 (25% → 50%)
- [ ] Phase 1 success criteria verified
- [ ] Percentage increased to 25%
- [ ] 48 hours of monitoring at 25%
- [ ] Percentage increased to 50%
- [ ] 48 hours of monitoring at 50%
- [ ] Success criteria met

### Phase 3 (100%)
- [ ] Phase 2 success criteria verified
- [ ] Percentage increased to 100%
- [ ] 1 week of monitoring at 100%
- [ ] All metrics stable
- [ ] No rollbacks or incidents

### Phase 4 (Cleanup)
- [ ] 2 weeks of stable 100% rollout
- [ ] Legacy code marked as deprecated
- [ ] Documentation updated
- [ ] Team trained on new orchestrator
- [ ] Removal of legacy code scheduled (3-6 months)

---

**Last Updated:** 2025-10-20
**Version:** 1.0
**Status:** ✅ Ready for Deployment
