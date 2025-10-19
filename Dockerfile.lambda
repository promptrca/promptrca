# Use AWS Lambda Python 3.13 base image
FROM public.ecr.aws/lambda/python:3.13

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Copy requirements and install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/promptrca/ ${LAMBDA_TASK_ROOT}/promptrca/

# Set the Lambda handler
CMD ["promptrca.lambda_handler.lambda_handler"]

# Add metadata labels
LABEL maintainer="PromptRCA Team"
LABEL version="1.0.0"
LABEL description="AI Root-Cause Investigator for AWS Serverless"

# Note: This Lambda function requires AWS credentials to be configured
# via environment variables or IAM roles when deployed to AWS Lambda.
# 
# Required AWS permissions:
# - lambda:GetFunction, lambda:ListFunctions, lambda:GetFunctionConfiguration
# - apigateway:GET, apigateway:POST
# - states:DescribeStateMachine, states:ListExecutions
# - iam:GetRole, iam:GetRolePolicy, iam:ListAttachedRolePolicies
# - xray:GetTraceSummaries, xray:BatchGetTraces
# - logs:DescribeLogGroups, logs:DescribeLogStreams, logs:GetLogEvents
# - cloudwatch:GetMetricStatistics, cloudwatch:ListMetrics
# - dynamodb:DescribeTable, dynamodb:ListTables
# - s3:GetBucketLocation, s3:GetBucketVersioning, s3:ListBucket
# - sqs:GetQueueAttributes, sqs:ListQueues
# - sns:GetTopicAttributes, sns:ListTopics
# - events:ListRules, events:ListTargetsByRule
# - ec2:DescribeVpcs, ec2:DescribeSubnets, ec2:DescribeSecurityGroups
