# New RCA Tools - Quick Reference

## AWS Health Tools

### check_aws_service_health()
**Purpose**: Check if AWS service has active incidents  
**When to use**: FIRST step in any investigation  
**Example**:
```python
check_aws_service_health('LAMBDA', 'us-east-1')
```

**Service Codes**:
- `LAMBDA` - AWS Lambda
- `APIGATEWAY` - API Gateway
- `DYNAMODB` - DynamoDB
- `STATES` - Step Functions
- `S3` - S3
- `SQS` - SQS
- `SNS` - SNS
- `EVENTS` - EventBridge
- `EC2` - EC2/VPC

---

### get_account_health_events()
**Purpose**: Get all AWS Health events for your account  
**When to use**: When investigating account-wide issues  
**Example**:
```python
get_account_health_events(hours_back=24)
```

---

### check_service_quota_status()
**Purpose**: Check if service quotas are being hit  
**When to use**: When seeing throttling or limit errors  
**Example**:
```python
check_service_quota_status('lambda')
```

---

## CloudTrail Tools

### get_recent_cloudtrail_events()
**Purpose**: Find configuration changes for a resource  
**When to use**: To answer "what changed?"  
**Example**:
```python
get_recent_cloudtrail_events('my-lambda-function', hours_back=24)
```

**Common Event Names**:
- `UpdateFunctionCode` - Lambda code deployment
- `UpdateFunctionConfiguration` - Lambda config change
- `AttachRolePolicy` - IAM policy attached
- `DetachRolePolicy` - IAM policy removed
- `PutFunctionConcurrency` - Lambda concurrency change

---

### find_correlated_changes()
**Purpose**: Find ALL changes around incident time  
**When to use**: To find what changed across multiple services  
**Example**:
```python
find_correlated_changes(
    incident_time="2025-01-20T10:00:00Z",
    window_minutes=30,
    services="lambda,iam,apigateway"
)
```

---

### get_iam_policy_changes()
**Purpose**: Track IAM policy modifications  
**When to use**: When investigating permission errors  
**Example**:
```python
get_iam_policy_changes('my-lambda-execution-role', hours_back=168)
```

---

## Investigation Checklist

### For Any AWS Incident:
1. ✅ Check AWS Service Health
2. ✅ Check CloudTrail for recent changes
3. ✅ Analyze X-Ray traces
4. ✅ Check service-specific logs/metrics
5. ✅ Delegate to specialist agents

### For Permission Errors:
1. ✅ Check AWS Service Health (IAM)
2. ✅ Get IAM policy changes
3. ✅ Check CloudTrail for role modifications
4. ✅ Simulate IAM policy
5. ✅ Check trust relationships

### For Deployment Issues:
1. ✅ Check CloudTrail for recent deployments
2. ✅ Find correlated changes
3. ✅ Check version history
4. ✅ Compare before/after configurations

### For Performance Issues:
1. ✅ Check AWS Service Health
2. ✅ Check service quotas
3. ✅ Check CloudTrail for config changes
4. ✅ Analyze metrics and traces

---

## Common Patterns

### Pattern 1: AWS Service Issue
```python
health = check_aws_service_health('LAMBDA', 'us-east-1')
if health['aws_service_issue_detected']:
    return "AWS service issue - escalate to AWS support"
```

### Pattern 2: Recent Deployment
```python
changes = get_recent_cloudtrail_events('my-function', 24)
if changes['configuration_changes_detected']:
    # Check if deployment happened recently
    for event in changes['events']:
        if 'UpdateFunctionCode' in event['event_name']:
            return "Recent deployment detected - likely cause"
```

### Pattern 3: IAM Policy Change
```python
iam_changes = get_iam_policy_changes('my-role', 168)
if iam_changes['total_policy_changes'] > 0:
    # Check for DetachRolePolicy events
    for change in iam_changes['policy_changes']:
        if 'Detach' in change['event_name']:
            return "IAM policy was removed - permission issue"
```

### Pattern 4: Correlated Changes
```python
correlated = find_correlated_changes(
    incident_time="2025-01-20T10:00:00Z",
    window_minutes=30
)
if correlated['analysis']['high_risk_changes']:
    # Changes within 10min of incident
    return "High-risk changes detected right before incident"
```

---

## Error Handling

### AWS Health API Not Available:
```json
{
  "error": "...",
  "note": "AWS Health API requires Business or Enterprise support plan"
}
```
**Action**: Continue investigation without AWS Health checks

### CloudTrail Not Enabled:
```json
{
  "error": "...",
  "note": "CloudTrail may not be enabled"
}
```
**Action**: Enable CloudTrail for future investigations

### Resource Not Found:
```json
{
  "total_events": 0,
  "configuration_changes_detected": false
}
```
**Action**: Resource name may be incorrect or no changes in time window

---

## Tips

1. **Always check AWS Health first** - saves time if AWS is down
2. **Use 30-minute window** for correlated changes - catches most deployment issues
3. **Check IAM changes for 7 days** - policy changes may have delayed effects
4. **Look for high-risk changes** - changes within 10min of incident are suspicious
5. **Correlate timestamps** - match change times with error start times

---

## IAM Permissions Required

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "health:DescribeEvents",
        "cloudtrail:LookupEvents",
        "servicequotas:GetServiceQuota"
      ],
      "Resource": "*"
    }
  ]
}
```
