# PromptRCA Setup Guide for AWS Accounts

This guide explains how to set up PromptRCA to investigate your AWS account. You'll need to create an IAM role that PromptRCA can assume to access your AWS resources.

## 🎯 What PromptRCA Does

PromptRCA is an AI-powered root cause analysis tool that investigates AWS incidents by:
- Analyzing X-Ray traces to understand request flows
- Examining CloudWatch logs for error patterns
- Checking service configurations (Lambda, API Gateway, Step Functions, etc.)
- Identifying the root cause of failures with evidence-based reasoning

## 🔐 Required Setup

### Step 1: Create the PromptRCA Role

1. **Go to IAM Console** → Roles → Create Role
2. **Select "Another AWS account"**
3. **Enter PromptRCA's account ID**: `850826207039`
4. **Check "Require external ID"** and set it to: `9ab0d240-1b35-45b1-b2ae-3efae1a7dd10`
5. **Role name**: `promptrca` (or any name you prefer)

### Step 2: Attach the Investigation Policy

1. **In the role creation wizard**, go to "Attach permissions policies"
2. **Click "Create policy"** and paste the JSON from `promptrca-investigation-policy.json`
3. **Name the policy**: `PromptRCA-Investigation-Policy`
4. **Attach this policy to your role**

### Step 3: Configure Trust Policy (Optional)

If you want to restrict which PromptRCA functions can assume the role, update the trust policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::850826207039:role/promptrca-execution-role"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "9ab0d240-1b35-45b1-b2ae-3efae1a7dd10"
        }
      }
    }
  ]
}
```

## 📋 What Permissions PromptRCA Needs

The policy grants read-only access to investigate:

### Core Services
- **X-Ray**: Trace analysis and service maps
- **CloudWatch Logs**: Error logs and patterns
- **CloudWatch Metrics**: Performance data
- **Lambda**: Function configurations and metrics
- **API Gateway**: API configurations and logs
- **Step Functions**: State machine definitions and execution history

### Additional Services
- **IAM**: Role and policy analysis
- **DynamoDB**: Table configurations
- **S3**: Bucket policies and configurations
- **SQS/SNS**: Queue and topic configurations
- **EventBridge**: Rule definitions
- **VPC/EC2**: Network and instance configurations
- **RDS**: Database configurations
- **SES**: Email service configurations

## 🚀 Using PromptRCA

Once set up, you can invoke PromptRCA with:

```json
{
  "tenant_id": "YOUR_ACCOUNT_ID",
  "xray_trace_id": "1-xxxxxxxxx-xxxxxxxxxxxxxxxxx",
  "assume_role_arn": "arn:aws:iam::YOUR_ACCOUNT_ID:role/promptrca",
  "investigation_id": "unique-investigation-id",
  "external_id": "9ab0d240-1b35-45b1-b2ae-3efae1a7dd10",
  "region": "eu-west-1",
  "client_id": "your-client-id",
  "free_text_input": "Describe the issue you're experiencing"
}
```

## 🔒 Security Considerations

### What PromptRCA Can Do
- ✅ **Read-only access** to AWS resources
- ✅ **Analyze traces and logs** for debugging
- ✅ **Examine configurations** to identify issues
- ✅ **Generate reports** with root cause analysis

### What PromptRCA Cannot Do
- ❌ **Modify any AWS resources**
- ❌ **Delete or create anything**
- ❌ **Access sensitive data** (only metadata and logs)
- ❌ **Make changes** to your infrastructure

### Data Privacy
- PromptRCA only accesses **metadata and logs** needed for investigation
- **No sensitive data** (like S3 object contents) is accessed
- All analysis is performed **in-memory** and not stored
- You can **revoke access** anytime by deleting the role

## 🛠️ Troubleshooting

### Common Issues

1. **"Access Denied" errors**
   - Check that the role ARN is correct
   - Verify the external ID matches exactly
   - Ensure the policy is attached to the role

2. **"Trace not found" errors**
   - Verify the trace ID exists in X-Ray
   - Check that X-Ray is enabled in your region
   - Ensure the trace is within the retention period (30 days)

3. **"Role assumption failed"**
   - Check the trust policy allows PromptRCA's account
   - Verify the external ID is correct
   - Ensure the role exists and is active

### Verification Commands

Test the role assumption:
```bash
aws sts assume-role \
  --role-arn "arn:aws:iam::YOUR_ACCOUNT_ID:role/promptrca" \
  --role-session-name "test-session" \
  --external-id "9ab0d240-1b35-45b1-b2ae-3efae1a7dd10"
```

Check X-Ray traces:
```bash
aws xray get-trace-summaries \
  --start-time 2025-01-01T00:00:00 \
  --end-time 2025-01-02T00:00:00
```

## 📞 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Verify your IAM configuration
3. Contact PromptRCA support with your account ID and error details

## 🔄 Updates

This policy may be updated to support new AWS services or investigation capabilities. Check this guide for the latest version.

---

**Note**: This setup allows PromptRCA to investigate your AWS account for root cause analysis. The tool only performs read operations and does not modify any resources.

