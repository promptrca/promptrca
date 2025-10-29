# Requirements Document

## Introduction

This specification addresses the critical refactoring needed for the PromptRCA swarm orchestrator to eliminate code duplication, remove placeholder implementations, and properly organize the codebase using real AWS API calls through existing tools and specialists.

## Glossary

- **Swarm_Orchestrator**: The main orchestration class that coordinates multiple specialist agents for AWS infrastructure investigation
- **Specialist_Agent**: Individual agents that analyze specific AWS services (Lambda, API Gateway, Step Functions, etc.)
- **Specialist_Tool**: Strands tools that wrap specialist functionality for use by agents
- **AWS_Tool**: Functions that make actual AWS API calls to retrieve service data
- **Placeholder_Implementation**: Non-functional code that returns mock data instead of making real AWS API calls
- **Real_Implementation**: Code that makes actual AWS API calls and returns real data

## Requirements

### Requirement 1

**User Story:** As a developer investigating AWS infrastructure issues, I want the swarm orchestrator to use real AWS API calls instead of placeholder implementations, so that I get accurate diagnostic information.

#### Acceptance Criteria

1. WHEN the swarm orchestrator analyzes AWS services, THE Swarm_Orchestrator SHALL use existing AWS_Tool functions that make real API calls
2. WHEN specialist tools are invoked, THE Specialist_Tool SHALL delegate to existing AWS_Tool functions rather than returning placeholder data
3. WHEN IAM analysis is performed, THE iam_specialist_tool SHALL use real IAM API calls from iam_tools.py
4. WHEN S3 analysis is performed, THE s3_specialist_tool SHALL use real S3 API calls from s3_tools.py
5. WHEN SQS analysis is performed, THE sqs_specialist_tool SHALL use real SQS API calls from sqs_tools.py

### Requirement 2

**User Story:** As a developer maintaining the codebase, I want the swarm orchestrator code to be properly organized into separate files, so that it's maintainable and follows good software engineering practices.

#### Acceptance Criteria

1. WHEN the swarm orchestrator is implemented, THE Swarm_Orchestrator SHALL be split into multiple focused files
2. WHEN specialist agents are defined, THE Specialist_Agent SHALL be implemented in separate agent files under src/promptrca/agents/
3. WHEN specialist tools are defined, THE Specialist_Tool SHALL reuse existing specialist classes from src/promptrca/specialists/
4. WHEN the main orchestrator file is examined, THE swarm_orchestrator.py SHALL contain only orchestration logic and not tool implementations
5. WHEN agent prompts are defined, THE agent prompts SHALL be stored in separate configuration files or constants

### Requirement 3

**User Story:** As a developer working on the system, I want duplicate code to be eliminated, so that there's a single source of truth for each piece of functionality.

#### Acceptance Criteria

1. WHEN duplicate tool implementations are found, THE Swarm_Orchestrator SHALL remove placeholder implementations and use existing real implementations
2. WHEN specialist functionality is needed, THE Specialist_Tool SHALL delegate to existing Specialist classes rather than reimplementing logic
3. WHEN AWS API calls are needed, THE system SHALL use existing AWS_Tool functions from the tools/ directory
4. WHEN the codebase is analyzed, THE system SHALL have no duplicate implementations of the same AWS service functionality
5. WHEN deprecated code is identified, THE system SHALL remove deprecated implementations after migration is complete

### Requirement 4

**User Story:** As a developer debugging AWS issues, I want all specialist tools to make real AWS API calls with proper error handling, so that I can diagnose actual infrastructure problems.

#### Acceptance Criteria

1. WHEN specialist tools encounter AWS API errors, THE Specialist_Tool SHALL return structured error information with AWS error codes
2. WHEN AWS API calls are made, THE AWS_Tool SHALL use the existing AWS client context from the context module
3. WHEN specialist analysis fails, THE Specialist_Tool SHALL provide meaningful error messages that help with debugging
4. WHEN AWS permissions are insufficient, THE system SHALL return clear permission error messages
5. WHEN AWS services are unavailable, THE system SHALL handle service errors gracefully and return diagnostic information

### Requirement 5

**User Story:** As a developer extending the system, I want the specialist architecture to be consistent and extensible, so that new AWS services can be easily added.

#### Acceptance Criteria

1. WHEN new specialist tools are added, THE Specialist_Tool SHALL follow the same pattern as existing tools
2. WHEN specialist tools are implemented, THE Specialist_Tool SHALL use the existing BaseSpecialist interface
3. WHEN AWS tools are created, THE AWS_Tool SHALL follow the existing tool patterns with proper documentation
4. WHEN agent configurations are defined, THE Specialist_Agent SHALL use consistent prompt templates and tool assignments
5. WHEN the system is extended, THE new components SHALL integrate seamlessly with existing swarm orchestration patterns