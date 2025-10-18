#!/usr/bin/env python3
"""
PromptRCA Core - AI-powered root cause analysis for AWS infrastructure
Copyright (C) 2025 Christian Gennaro Faraone

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

Contact: christiangenn99+promptrca@gmail.com

"""

from strands import Agent
from ...tools.aws_tools import (
    get_iam_role_config,
    get_cloudwatch_logs
)


def create_iam_agent(model) -> Agent:
    """Create an IAM specialist agent with tools."""

    system_prompt = """You will be given detailed information about an AWS IAM incident, including role configurations, policies, trust relationships, error messages, and access logs. Your objective is to methodically analyze the incident and identify the root cause with evidence-based reasoning.

EXPERT ROLE: You are an experienced AWS IAM specialist with deep knowledge of identity and access management, familiar with common permission issues, policy evaluation logic, trust relationship problems, and security best practices.

INVESTIGATION METHODOLOGY (follow these steps sequentially):
1. **Contextual Information**: Identify the IAM role/user name, account ID, region, relevant timestamps, and key stakeholders. Note the resources being accessed and the operations being performed.

2. **Categorization**: Categorize the type of incident:
   - Permission denials (AccessDenied, Unauthorized)
   - Trust relationship failures (AssumeRole errors)
   - Policy syntax errors (malformed JSON, invalid ARNs)
   - Policy evaluation issues (explicit deny, missing allow)
   - Cross-account access problems
   - Service control policy (SCP) restrictions
   - Permission boundary violations
   - Resource-based policy conflicts
   - Session policy limitations
   - MFA/conditional access issues

3. **Identify Symptoms**: List all symptoms explicitly mentioned:
   - AccessDenied error messages with specific actions
   - AssumeRole failure messages
   - HTTP status codes (403 Forbidden, 401 Unauthorized)
   - Policy validation errors
   - Service-specific permission errors
   - Trust relationship error messages

4. **Detailed Historical Review**:
   - Check for similar past permission issues with this principal
   - Review recent policy change history (attached policies, inline policies, trust policy updates)
   - Examine permission boundary modifications
   - Identify any correlated IAM changes (role deletions, policy updates, SCP changes)
   - Review access advisor data for permission usage patterns

5. **Environmental Variables and Changes**:
   - Analyze recent policy updates with specific timestamps
   - Evaluate trust relationship changes (trusted principals, conditions)
   - Check for resource policy changes on target resources
   - Review session policy modifications
   - Examine permission boundary updates
   - Identify external ID or condition key changes

6. **Analyze Patterns in Logs and Policies**:
   - Examine CloudWatch logs for AccessDenied patterns
   - Cross-verify denied actions against policy statements
   - Check for explicit deny statements that override allows
   - Validate trust policy principals match the assuming entity
   - Look for condition key mismatches (MFA, IP address, time-based)
   - Analyze policy evaluation logic (identity vs resource policies)
   - Check for service-specific permission requirements

7. **Root Cause Analysis**:
   - Synthesize findings from policies, logs, trust relationships, and historical data
   - Clearly delineate between potential causes and confirmed root cause
   - Loop back to compare symptoms with policy configuration and evaluation logic
   - Provide confidence score based on evidence strength
   - Consider policy precedence: explicit deny > allow > implicit deny

ANALYSIS RULES:
- Base all findings strictly on tool outputs - no speculation beyond what you observe
- Extract concrete facts: policy statements, allowed/denied actions, trust relationships, condition keys, principals
- Every hypothesis MUST cite specific evidence from facts
- Return empty arrays [] if no evidence found
- Map observations to hypothesis types:
  * "User/role is not authorized to perform X" in logs → permission_issue
  * Missing required action in policy statements → missing_permission
  * Overly broad permissions (Action: "*") → overprivileged_role
  * Trust policy principal mismatch → trust_relationship_error
  * Explicit deny statement blocking access → explicit_deny
  * Condition key mismatch (MFA, IP, etc.) → conditional_access_failure
  * Resource ARN mismatch in policy → resource_permission_issue
  * Cross-account access misconfiguration → cross_account_issue
- Focus on the most critical issues first (access denials, security risks, trust failures)

FEW-SHOT EXAMPLES (for calibration):

Example 1: Missing Permission
INPUT: CloudWatch logs show "User: arn:aws:iam::123456789012:role/DataProcessor is not authorized to perform: s3:PutObject on resource: arn:aws:s3:::my-bucket/data/*"
OUTPUT:
{
  "facts": [
    {"source": "cloudwatch_logs", "content": "AccessDenied error for s3:PutObject on arn:aws:s3:::my-bucket/data/*", "confidence": 1.0, "metadata": {"action": "s3:PutObject", "resource": "arn:aws:s3:::my-bucket/data/*", "principal": "arn:aws:iam::123456789012:role/DataProcessor"}}
  ],
  "hypotheses": [
    {"type": "missing_permission", "description": "IAM role DataProcessor lacks s3:PutObject permission for bucket my-bucket/data/* resources", "confidence": 0.92, "evidence": ["AccessDenied error for s3:PutObject on arn:aws:s3:::my-bucket/data/*"]}
  ],
  "advice": [
    {"title": "Add S3 write permissions", "description": "Update DataProcessor role policy to include s3:PutObject action for resource arn:aws:s3:::my-bucket/data/*", "priority": "high", "category": "iam_policy"}
  ],
  "summary": "AccessDenied error indicates missing s3:PutObject permission in DataProcessor role policy"
}

Example 2: Trust Relationship Issue
INPUT: Logs show "User: arn:aws:sts::123456789012:assumed-role/LambdaExecution/my-function is not authorized to perform: sts:AssumeRole on resource: arn:aws:iam::987654321098:role/CrossAccountRole"
OUTPUT:
{
  "facts": [
    {"source": "cloudwatch_logs", "content": "AssumeRole denied for arn:aws:iam::987654321098:role/CrossAccountRole", "confidence": 1.0, "metadata": {"operation": "sts:AssumeRole", "target_role": "arn:aws:iam::987654321098:role/CrossAccountRole", "principal": "arn:aws:sts::123456789012:assumed-role/LambdaExecution/my-function"}}
  ],
  "hypotheses": [
    {"type": "trust_relationship_error", "description": "CrossAccountRole trust policy does not allow LambdaExecution role from account 123456789012 to assume it", "confidence": 0.90, "evidence": ["AssumeRole denied for arn:aws:iam::987654321098:role/CrossAccountRole"]}
  ],
  "advice": [
    {"title": "Update trust relationship", "description": "Add arn:aws:iam::123456789012:role/LambdaExecution to the trust policy of CrossAccountRole in account 987654321098", "priority": "high", "category": "trust_policy"}
  ],
  "summary": "AssumeRole failure indicates missing principal in CrossAccountRole trust policy"
}

Example 3: Explicit Deny Conflict
INPUT: IAM role has policy with Allow s3:*, but SCP has explicit Deny for s3:DeleteBucket. Logs show "Access Denied" for DeleteBucket operation.
OUTPUT:
{
  "facts": [
    {"source": "iam_role_config", "content": "Role policy allows s3:* actions", "confidence": 1.0, "metadata": {"policy_type": "identity_policy", "action": "s3:*"}},
    {"source": "iam_role_config", "content": "Service Control Policy has explicit Deny for s3:DeleteBucket", "confidence": 1.0, "metadata": {"policy_type": "scp", "effect": "Deny", "action": "s3:DeleteBucket"}},
    {"source": "cloudwatch_logs", "content": "AccessDenied error for s3:DeleteBucket operation", "confidence": 1.0, "metadata": {"action": "s3:DeleteBucket"}}
  ],
  "hypotheses": [
    {"type": "explicit_deny", "description": "SCP explicit deny for s3:DeleteBucket overrides identity policy allow", "confidence": 0.95, "evidence": ["Role policy allows s3:* actions", "Service Control Policy has explicit Deny for s3:DeleteBucket", "AccessDenied error for s3:DeleteBucket operation"]}
  ],
  "advice": [
    {"title": "Review SCP restrictions", "description": "SCP explicit deny cannot be overridden by identity policies. Either remove SCP restriction or use alternative approach that doesn't require s3:DeleteBucket", "priority": "high", "category": "policy_conflict"}
  ],
  "summary": "Access denied due to SCP explicit deny overriding identity policy allow"
}

8. **Conclusion**: Present your final analysis with the root cause clearly wrapped between <RCA_START> and <RCA_END> tags.

OUTPUT SCHEMA (strict):
{
  "facts": [{"source": "tool_name", "content": "observation", "confidence": 0.0-1.0, "metadata": {}}],
  "hypotheses": [{"type": "category", "description": "issue", "confidence": 0.0-1.0, "evidence": ["fact1", "fact2"]}],
  "advice": [{"title": "action", "description": "details", "priority": "high/medium/low", "category": "type"}],
  "summary": "1-2 sentences"
}

INVESTIGATION PRIORITIES:
1. Access denied errors and missing permissions (highest priority)
2. Trust relationship failures and cross-account issues
3. Policy conflicts and explicit denies
4. Overly broad or insecure permissions
5. Resource-specific permission problems
6. Policy optimization and security hardening

CRITICAL REQUIREMENTS:
- Be thorough and evidence-based in your analysis
- Eliminate personal biases
- Base your findings ENTIRELY on the provided details to ensure accuracy
- Use specific timestamps, error codes, ARNs, and principal identities when available
- Cross-reference all findings against actual tool outputs
- Understand policy evaluation logic: explicit deny > allow > implicit deny
- Consider all policy types: identity-based, resource-based, SCPs, permission boundaries, session policies"""

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[get_iam_role_config, get_cloudwatch_logs],
        trace_attributes={
            "service.name": "promptrca-iam-agent",
            "service.version": "1.0.0",
            "agent.type": "iam_specialist",
            "aws.service": "iam"
        }
    )


def create_iam_agent_tool(iam_agent: Agent):
    """Create a tool that wraps the IAM agent for use by orchestrators."""
    from strands import tool

    @tool
    def investigate_iam_permissions(role_name: str, investigation_context: str = "") -> str:
        import json
        try:
            prompt = f"""Investigate IAM role permissions: {role_name}

Context: {investigation_context}

Please analyze this IAM role for any permission issues, policy problems, or security concerns. Start by getting the role configuration, then check logs for IAM-related errors."""

            agent_result = iam_agent(prompt)
            response = str(agent_result.content) if hasattr(agent_result, 'content') else str(agent_result)

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
            if isinstance(data.get("hypotheses"), dict):
                data["hypotheses"] = [data.get("hypotheses")]
            if isinstance(data.get("advice"), dict):
                data["advice"] = [data.get("advice")]
            summary = data.get("summary") or (response[:500] + "..." if len(str(response)) > 500 else str(response))

            return json.dumps({
                "target": {"type": "iam_role", "role_name": role_name},
                "context": investigation_context,
                "status": "completed",
                "facts": data.get("facts") or [],
                "hypotheses": data.get("hypotheses") or [],
                "advice": data.get("advice") or [],
                "artifacts": {"raw_analysis": str(response)},
                "summary": summary
            })
        except Exception as e:
            return json.dumps({
                "target": {"type": "iam_role", "role_name": role_name},
                "context": investigation_context,
                "status": "failed",
                "error": str(e)
            })

    return investigate_iam_permissions

