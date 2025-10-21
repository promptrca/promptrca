# Implementation Plan

- [x] 1. Create swarm tools module with real AWS API implementations
  - Create `src/promptrca/core/swarm_tools.py` with proper Strands tool decorators
  - Implement `lambda_specialist_tool` using existing LambdaSpecialist class and AWS tools
  - Implement `apigateway_specialist_tool` using existing APIGatewaySpecialist class and AWS tools
  - Implement `stepfunctions_specialist_tool` using existing StepFunctionsSpecialist class and AWS tools
  - Implement `trace_specialist_tool` using existing TraceSpecialist class and AWS tools
  - Use `@tool(context=True)` pattern for all tools to access invocation_state
  - Return proper ToolResult dictionaries with status and content structure
  - Handle AWS client context from invocation_state for cross-account access
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 4.1, 4.2, 4.3, 4.4_

- [x] 2. Create missing specialist implementations for additional AWS services
  - Create `src/promptrca/specialists/iam_specialist.py` using existing iam_tools.py functions
  - Create `src/promptrca/specialists/s3_specialist.py` using existing s3_tools.py functions
  - Create `src/promptrca/specialists/sqs_specialist.py` using existing sqs_tools.py functions
  - Create `src/promptrca/specialists/sns_specialist.py` using existing sns_tools.py functions
  - Follow BaseSpecialist interface pattern for consistency
  - Implement real AWS API calls through existing tools
  - _Requirements: 1.1, 3.3, 5.1, 5.2_

- [x] 3. Add missing specialist tools to swarm_tools.py
  - Implement `iam_specialist_tool` using new IAMSpecialist class
  - Implement `s3_specialist_tool` using new S3Specialist class
  - Implement `sqs_specialist_tool` using new SQSSpecialist class
  - Implement `sns_specialist_tool` using new SNSSpecialist class
  - Follow same pattern as other specialist tools with ToolContext access
  - _Requirements: 1.1, 3.3, 4.1, 4.2_

- [x] 4. Create swarm agents module with proper agent configurations
  - Create `src/promptrca/agents/swarm_agents.py` with agent factory functions
  - Define agent prompt templates with clear termination rules to prevent infinite loops
  - Implement `create_trace_agent()` with entry point configuration and strict handoff rules
  - Implement `create_lambda_agent()` with Lambda-specific prompts and termination conditions
  - Implement `create_apigateway_agent()` with API Gateway-specific prompts and handoff rules
  - Implement `create_stepfunctions_agent()` with Step Functions-specific prompts and termination rules
  - Implement `create_hypothesis_agent()` with hypothesis generation prompts and mandatory handoff to root cause
  - Implement `create_root_cause_agent()` with terminal agent configuration (no handoffs allowed)
  - Implement `create_swarm_agents()` function returning list of all agents
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.3, 5.4, 5.5_

- [x] 5. Refactor swarm orchestrator to use new modular components
  - Remove all placeholder tool implementations from `src/promptrca/core/swarm_orchestrator.py`
  - Import tools from `swarm_tools.py` instead of defining them inline
  - Import agent creation functions from `swarm_agents.py`
  - Update `_create_specialist_agents()` to use agent factory functions
  - Update `_create_investigation_swarm()` to use imported agents
  - Ensure AWS client is properly passed through invocation_state for cross-account access
  - Add cost control configuration with appropriate timeouts and handoff limits
  - _Requirements: 2.1, 2.4, 3.1, 3.2, 4.2_

- [x] 6. Implement investigation flow control and cost management
  - Add investigation phase tracking to monitor progress through trace → service → hypothesis → root cause
  - Implement early termination conditions to prevent runaway investigations
  - Add swarm configuration with strict limits: max_handoffs=12, execution_timeout=450.0, node_timeout=60.0
  - Enable repetitive handoff detection to prevent ping-pong behavior between agents
  - Add progress monitoring and cost estimation capabilities
  - _Requirements: Cost control and investigation flow requirements from design_

- [x] 7. Update specialist classes to use existing AWS tools consistently
  - Review `src/promptrca/specialists/lambda_specialist.py` to ensure it uses functions from `lambda_tools.py`
  - Review `src/promptrca/specialists/apigateway_specialist.py` to ensure it uses functions from `apigateway_tools.py`
  - Review `src/promptrca/specialists/stepfunctions_specialist.py` to ensure it uses functions from `stepfunctions_tools.py`
  - Review `src/promptrca/specialists/trace_specialist.py` to ensure it uses functions from `xray_tools.py`
  - Ensure all specialists handle AWS client context properly for cross-account access
  - _Requirements: 3.3, 4.2, 4.4_

- [x] 8. Clean up and remove deprecated code
  - Remove placeholder implementations of `iam_specialist_tool`, `s3_specialist_tool`, `sqs_specialist_tool`, `sns_specialist_tool` from swarm_orchestrator.py
  - Remove duplicate helper functions that are now in swarm_tools.py
  - Remove agent prompt definitions from swarm_orchestrator.py (moved to swarm_agents.py)
  - Clean up imports and remove unused dependencies
  - Verify no duplicate functionality remains between old and new implementations
  - _Requirements: 3.1, 3.2, 3.4, 3.5_

- [x] 9. Add comprehensive error handling and validation
  - Implement structured error responses in all specialist tools using ToolResult format
  - Add AWS client validation before starting investigations
  - Handle cross-account role assumption errors with clear error messages
  - Add input validation for resource_data and investigation_context parameters
  - Implement graceful degradation when some specialists fail
  - _Requirements: 4.1, 4.3, 4.4, 4.5_

- [x] 10. Create integration tests for refactored components
  - Test swarm_tools.py functions with mock AWS clients and real specialist classes
  - Test swarm_agents.py agent creation and configuration
  - Test complete swarm orchestration with refactored components
  - Test cross-account access scenarios with role ARN and external ID
  - Test cost control mechanisms and investigation termination
  - Verify backward compatibility with existing investigation interfaces
  - _Requirements: Testing strategy from design_

- [ ] 11. Performance and cost optimization testing
  - Benchmark investigation execution time before and after refactoring
  - Measure token usage and cost implications of new swarm configuration
  - Test investigation termination under various scenarios
  - Validate that cost control mechanisms prevent runaway investigations
  - Test with various AWS resource configurations and trace scenarios
  - _Requirements: Performance considerations from design_

- [ ] 12. Update documentation and finalize migration
  - Update code comments and docstrings for new modular structure
  - Document investigation flow phases and termination conditions
  - Document cost control mechanisms and configuration options
  - Create migration guide for any breaking changes
  - Update any configuration files or deployment scripts if needed
  - _Requirements: All requirements - final integration and documentation_