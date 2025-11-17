# PromptRCA - One Pager

**AI-Powered Root Cause Analysis for AWS Infrastructure**

---

## What is PromptRCA?

PromptRCA is an intelligent multi-agent system that automatically investigates and diagnoses issues in AWS serverless and cloud infrastructure. Using advanced AI agents powered by Amazon Bedrock, it analyzes AWS resources, traces, logs, and metrics to identify root causes and provide actionable remediation advice.

**License:** GNU Affero General Public License v3.0
**Author:** Christian Gennaro Faraone
**Contact:** info@promptrca.com

---

## Core Functionality

### Multi-Agent Investigation System

PromptRCA employs a **Swarm-based orchestration pattern** (Strands Agents best practices) with specialized AI agents that collaborate to investigate AWS infrastructure issues:

**Lead Orchestrator Agent**
- Coordinates all investigation phases
- Manages agent collaboration and shared context
- Decides investigation flow autonomously

**AWS Service Specialists** (8 specialized agents)
- **Lambda Specialist** - Function errors, timeouts, cold starts
- **API Gateway Specialist** - API errors, throttling, integration issues
- **Step Functions Specialist** - Workflow failures, state machine analysis
- **IAM Specialist** - Permission issues, policy analysis
- **S3 Specialist** - Bucket access, lifecycle, replication issues
- **SQS Specialist** - Queue processing, dead letter queues
- **SNS Specialist** - Topic delivery, subscription issues
- **Trace Specialist** - X-Ray trace analysis, distributed tracing

**Analysis Agents**
- **Hypothesis Agent** - Generates evidence-based hypotheses
- **Root Cause Agent** - Identifies primary root causes and contributing factors
- **Severity Agent** - Assesses impact scope and user impact
- **Advice Agent** - Provides remediation recommendations

### Investigation Workflow

1. **Input Parsing** - Natural language or structured investigation requests
2. **Trace Analysis** - X-Ray trace examination (if trace ID provided)
3. **Service Analysis** - Specialized agents gather facts from AWS services
4. **Hypothesis Generation** - AI analyzes facts to form hypotheses
5. **Root Cause Analysis** - Identifies primary causes with confidence scores
6. **Remediation Advice** - Generates actionable recommendations

### AWS Service Coverage

**Core Services:** Lambda, API Gateway, Step Functions, IAM, X-Ray, CloudWatch
**Additional Services:** DynamoDB, S3, SQS, SNS, EventBridge, VPC/Network
**Total Tools:** 50+ individual AWS investigation tools

---

## Key Features

### Deployment Options

**Docker Compose (Recommended)**
- HTTP Server mode (Starlette-based API)
- Lambda Container mode (AWS Lambda Runtime Interface Emulator)
- Multi-service orchestration

**AWS Lambda Deployment**
- Native AWS Lambda runtime
- API Gateway integration
- EventBridge, SNS, SQS triggers
- Step Functions orchestration

**Standalone HTTP Server**
- Production-ready Starlette server
- Health checks and status endpoints
- Containerized deployment

### Hierarchical Model Configuration

**3-Tier Configuration System:**
1. **Agent-specific** (highest priority) - Override for individual agents
2. **Category-specific** (middle priority) - Configure entire agent categories
3. **Global default** (fallback) - Default for all agents

**Configuration Flexibility:**
- Use cost-optimized models (20B) for specialists
- Use reasoning-optimized models (120B) for analysis
- Fine-tune temperature per agent or category
- Mix-and-match model types for optimal cost/performance

### Cross-Account Access

**Role Assumption Support:**
- Investigate resources in different AWS accounts
- Secure cross-account access with external ID
- Automated credential management
- IAM role-based permissions

### Optional Enhancements

**AWS Knowledge MCP Server Integration**
- Search official AWS documentation
- Get best practices and recommendations
- Check regional service availability
- Enhanced advice with current AWS knowledge
- Reduces hallucinations in recommendations

**Observability & Telemetry**
- OpenTelemetry integration
- Strands Agents telemetry
- Investigation metrics and tracing
- Performance monitoring

---

## Technical Architecture

### Agent Communication Pattern

```
Input → Input Parser Agent → Lead Orchestrator Agent
                                    ↓
                    ┌───────────────┴────────────────┐
                    ↓                                ↓
            Trace Specialist               Service Specialists
                    ↓                                ↓
                    └───────────────┬────────────────┘
                                    ↓
                          Hypothesis Agent
                                    ↓
                          Root Cause Agent
                                    ↓
                       Investigation Report
```

### Data Models

- **Fact** - Observable evidence from AWS services
- **Hypothesis** - Evidence-based theories about issues
- **Advice** - Actionable remediation recommendations
- **InvestigationReport** - Complete analysis with timeline
- **SeverityAssessment** - Impact scoring and resource analysis
- **RootCauseAnalysis** - Primary causes with confidence scores

### Technology Stack

- **AI Framework:** Strands Agents (multi-agent collaboration)
- **LLM Provider:** Amazon Bedrock (Claude, GPT-OSS models)
- **AWS SDK:** boto3 (AWS service integration)
- **Web Framework:** Starlette (HTTP server)
- **Container Runtime:** Docker, AWS Lambda
- **Observability:** OpenTelemetry

---

## Current State (v1.0.0)

### Recently Completed

✅ **Multi-Agent Optimization** - Swarm orchestration with Strands Agents
✅ **Cross-Account Support** - Role assumption with external ID
✅ **Hierarchical Model Configuration** - 3-tier agent configuration system
✅ **Docker Multi-Platform** - Lambda + HTTP server configurations
✅ **OpenTelemetry Integration** - Full observability support
✅ **AWS Knowledge MCP** - Optional documentation enhancement
✅ **8 Specialized Agents** - Comprehensive AWS service coverage
✅ **Production-Ready Deployment** - Docker Compose orchestration

### Stability

- Production-ready for AWS Lambda and serverless investigations
- Robust error handling and timeout management
- Comprehensive test coverage
- Multi-deployment support (Lambda, HTTP, Docker)

---

## Roadmap

### Phase 1: Enhanced AWS Coverage (Q1 2025)

**Additional Service Specialists**
- DynamoDB Specialist (table issues, throttling, GSI problems)
- EventBridge Specialist (rule matching, target failures)
- VPC Specialist (network connectivity, security groups, NACLs)
- CloudFront Specialist (distribution errors, origin issues)
- ECS/Fargate Specialist (container failures, task issues)

**Advanced Analysis**
- Cost impact analysis for incidents
- Performance degradation detection
- Security incident correlation
- Multi-region failure analysis

### Phase 2: Intelligence & Automation (Q2 2025)

**Proactive Monitoring**
- Anomaly detection from CloudWatch metrics
- Predictive failure analysis
- Automatic investigation triggering
- Trend analysis and pattern recognition

**Enhanced Recommendations**
- Infrastructure-as-Code remediation (CDK, Terraform)
- Automated fix implementation (with approval)
- Cost optimization recommendations
- Architecture improvement suggestions

**Knowledge Base**
- Historical incident database
- Pattern matching with past issues
- Organization-specific learning
- Best practices customization

### Phase 3: Enterprise Features (Q3 2025)

**Multi-Cloud Support**
- Azure investigation capabilities
- GCP infrastructure analysis
- Hybrid cloud correlation
- Cross-cloud dependency mapping

**Team Collaboration**
- Investigation sharing and handoff
- Team workspaces and dashboards
- Slack/Teams integration
- JIRA/ServiceNow ticketing integration

**Advanced Security**
- SOC 2 compliance features
- Audit logging and compliance reports
- Role-based access control
- Private model deployment support

### Phase 4: AI Enhancements (Q4 2025)

**Advanced AI Capabilities**
- Custom fine-tuned models for specific workloads
- Reinforcement learning from investigation outcomes
- Natural language query interface
- Voice-activated investigations

**Intelligent Automation**
- Self-healing infrastructure
- Automated runbook execution
- Chaos engineering integration
- Continuous investigation mode

### Future Considerations

**Developer Experience**
- IDE plugins (VSCode, IntelliJ)
- CI/CD pipeline integration
- Local development investigation tools
- GitHub Actions integration

**Ecosystem Integration**
- APM integration (Datadog, New Relic, Dynatrace)
- Incident management (PagerDuty, Opsgenie)
- Observability platforms (Splunk, Sumo Logic)
- Custom webhook support

---

## Getting Started

### Quick Start (Docker Compose)

```bash
# Clone and configure
cp .env.example .env
# Edit .env with your AWS credentials and model preferences

# Start all services
docker-compose up -d

# Test investigation
curl -X POST http://localhost:8080/invocations \
  -H 'Content-Type: application/json' \
  -d '{"investigation": {"input": "My Lambda function is failing with timeout errors"}, "service_config": {}}'
```

### Lambda Deployment

```bash
# Build Lambda image
docker build -f Dockerfile.lambda -t promptrca:latest .

# Push to ECR and deploy via CDK/SAM/Terraform
```

### Configuration

```bash
# Use category-level configuration (simplest)
export PROMPTRCA_SPECIALIST_MODEL_ID=openai.gpt-oss-20b-1:0
export PROMPTRCA_ANALYSIS_MODEL_ID=openai.gpt-oss-120b-1:0
export PROMPTRCA_ORCHESTRATOR_MODEL_ID=openai.gpt-oss-120b-1:0

# Enable AWS Knowledge MCP (optional)
export ENABLE_AWS_KNOWLEDGE_MCP=true
```

---

## Success Metrics

### Investigation Quality
- Root cause identification accuracy
- Remediation advice effectiveness
- False positive rate
- Time to resolution

### Performance
- Average investigation duration
- Cost per investigation
- Agent collaboration efficiency
- API response times

### Coverage
- AWS services supported
- Issue types detected
- Cross-service correlation
- Multi-account investigations

---

## Community & Support

- **Repository:** [GitHub - PromptRCA](https://github.com/yourusername/promptrca)
- **Documentation:** See README.md for detailed setup
- **Issues:** Report bugs and feature requests on GitHub
- **License:** AGPL-3.0 - Free and open source

**Built with ❤️ for the AWS community**
