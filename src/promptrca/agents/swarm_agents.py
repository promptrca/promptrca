#!/usr/bin/env python3
"""
Swarm Agents Module for PromptRCA

Provides agent factory functions for the Strands Swarm pattern.
All prompts are now loaded from external .md files for better maintainability.
"""

from typing import List
from strands import Agent

from ..utils.config import (
    create_orchestrator_model,
    create_lambda_agent_model,
    create_apigateway_agent_model,
    create_stepfunctions_agent_model,
    create_iam_agent_model,
    create_s3_agent_model,
    create_sqs_agent_model,
    create_sns_agent_model,
    create_hypothesis_agent_model,
    create_root_cause_agent_model
)
from ..core.swarm_tools import (
    lambda_specialist_tool,
    apigateway_specialist_tool,
    stepfunctions_specialist_tool,
    trace_specialist_tool,
    iam_specialist_tool,
    s3_specialist_tool,
    sqs_specialist_tool,
    sns_specialist_tool
)
from ..utils.prompt_loader import load_prompt


# Agent factory functions following Strands patterns

def create_trace_agent() -> Agent:
    """
    Create trace analysis agent with proper tools and configuration.
    
    This agent serves as the entry point for investigations and coordinates
    the overall investigation flow by analyzing X-Ray traces and handing off
    to appropriate service specialists.
    
    Returns:
        Agent configured for trace analysis with strict handoff rules
    """
    return Agent(
        name="trace_specialist",
        model=create_orchestrator_model(),
        system_prompt=load_prompt("trace_specialist"),
        tools=[trace_specialist_tool]
    )


def create_lambda_agent() -> Agent:
    """
    Create Lambda specialist agent with descriptive name and clear role.
    
    This agent analyzes Lambda function configuration, performance issues,
    and integration problems with other AWS services.
    
    Returns:
        Agent configured for Lambda analysis with proper termination conditions
    """
    return Agent(
        name="lambda_specialist", 
        model=create_lambda_agent_model(),
        system_prompt=load_prompt("lambda_specialist"),
        tools=[lambda_specialist_tool]
    )


def create_apigateway_agent() -> Agent:
    """
    Create API Gateway specialist agent with integration focus.
    
    This agent analyzes API Gateway configuration, stage settings,
    and backend integration issues.
    
    Returns:
        Agent configured for API Gateway analysis with handoff rules
    """
    return Agent(
        name="apigateway_specialist",
        model=create_apigateway_agent_model(),
        system_prompt=load_prompt("apigateway_specialist"),
        tools=[apigateway_specialist_tool]
    )


def create_stepfunctions_agent() -> Agent:
    """
    Create Step Functions specialist agent with execution analysis focus.
    
    This agent analyzes Step Functions state machine executions,
    state transition errors, and service integration issues.
    
    Returns:
        Agent configured for Step Functions analysis with termination rules
    """
    return Agent(
        name="stepfunctions_specialist",
        model=create_stepfunctions_agent_model(),
        system_prompt=load_prompt("stepfunctions_specialist"),
        tools=[stepfunctions_specialist_tool]
    )


def create_iam_agent() -> Agent:
    """
    Create IAM specialist agent with security and permissions focus.
    
    This agent analyzes IAM roles, policies, and permission configurations
    to identify access and security issues.
    
    Returns:
        Agent configured for IAM analysis with proper handoff rules
    """
    return Agent(
        name="iam_specialist",
        model=create_iam_agent_model(),
        system_prompt=load_prompt("iam_specialist"),
        tools=[iam_specialist_tool]
    )


def create_s3_agent() -> Agent:
    """
    Create S3 specialist agent with storage and access focus.
    
    This agent analyzes S3 bucket configuration, policies,
    and access patterns to identify storage issues.
    
    Returns:
        Agent configured for S3 analysis with termination conditions
    """
    return Agent(
        name="s3_specialist",
        model=create_s3_agent_model(),
        system_prompt=load_prompt("s3_specialist"),
        tools=[s3_specialist_tool]
    )


def create_sqs_agent() -> Agent:
    """
    Create SQS specialist agent with message processing focus.
    
    This agent analyzes SQS queue configuration, message processing,
    and integration patterns with other services.
    
    Returns:
        Agent configured for SQS analysis with handoff rules
    """
    return Agent(
        name="sqs_specialist",
        model=create_sqs_agent_model(),
        system_prompt=load_prompt("sqs_specialist"),
        tools=[sqs_specialist_tool]
    )


def create_sns_agent() -> Agent:
    """
    Create SNS specialist agent with notification delivery focus.
    
    This agent analyzes SNS topic configuration, subscriptions,
    and message delivery patterns.
    
    Returns:
        Agent configured for SNS analysis with termination rules
    """
    return Agent(
        name="sns_specialist",
        model=create_sns_agent_model(),
        system_prompt=load_prompt("sns_specialist"),
        tools=[sns_specialist_tool]
    )


def create_hypothesis_agent() -> Agent:
    """
    Create hypothesis generation agent with synthesis focus.
    
    This agent collects findings from all specialist agents and generates
    evidence-based hypotheses about root causes. It has mandatory handoff
    to root cause analysis.
    
    Returns:
        Agent configured for hypothesis generation with mandatory handoff
    """
    return Agent(
        name="hypothesis_generator",
        model=create_hypothesis_agent_model(),
        system_prompt=load_prompt("hypothesis_generator"),
        tools=[]  # No tools needed - receives findings from other agents
    )


def create_root_cause_agent() -> Agent:
    """
    Create root cause analysis agent with terminal configuration.
    
    This agent provides the final root cause analysis and completes
    the investigation. It is configured as a terminal agent with
    no handoffs allowed.
    
    Returns:
        Agent configured for final root cause analysis (terminal)
    """
    return Agent(
        name="root_cause_analyzer", 
        model=create_root_cause_agent_model(),
        system_prompt=load_prompt("root_cause_analyzer"),
        tools=[]  # No tools needed - analyzes hypotheses and provides final results
    )


def create_specialist_swarm_agents() -> List[Agent]:
    """
    Create only the specialist agents for the investigation swarm.
    
    Returns specialist agents that investigate AWS resources:
    - Entry point agent (trace_specialist)
    - Service specialist agents (lambda, apigateway, stepfunctions, iam, s3, sqs, sns)
    
    These agents autonomously investigate and hand off to each other based on findings.
    Analysis agents (hypothesis_generator, root_cause_analyzer) are handled separately
    in the Graph pattern.
    
    Returns:
        List of specialist Agent instances for Swarm orchestration
    """
    return [
        # Entry point agent
        create_trace_agent(),
        
        # Core service specialists
        create_lambda_agent(),
        create_apigateway_agent(),
        create_stepfunctions_agent(),
        
        # Infrastructure specialists
        create_iam_agent(),
        create_s3_agent(),
        create_sqs_agent(),
        create_sns_agent()
    ]


def create_hypothesis_agent_standalone() -> Agent:
    """
    Create the hypothesis generator agent (used outside swarm).
    
    This agent analyzes findings from specialist agents and generates
    structured hypotheses about root causes. Used as a standalone Graph node.
    
    Returns:
        Agent configured for hypothesis generation
    """
    return create_hypothesis_agent()


def create_root_cause_agent_standalone() -> Agent:
    """
    Create the root cause analyzer agent (used outside swarm).
    
    This agent analyzes hypotheses and determines the most likely root cause.
    Used as a standalone Graph node.
    
    Returns:
        Agent configured for root cause analysis
    """
    return create_root_cause_agent()


def create_swarm_agents() -> List[Agent]:
    """
    Create all swarm agents following Strands best practices.
    
    DEPRECATED: Use create_specialist_swarm_agents() instead.
    This function is kept for backward compatibility.
    
    Returns a complete list of agents for the investigation swarm including:
    - Entry point agent (trace_specialist)
    - Service specialist agents (lambda, apigateway, stepfunctions, iam, s3, sqs, sns)
    - Analysis agents (hypothesis_generator, root_cause_analyzer)
    
    Returns:
        List of Agent instances ready for Swarm orchestration
    """
    return [
        # Entry point agent
        create_trace_agent(),
        
        # Core service specialists
        create_lambda_agent(),
        create_apigateway_agent(),
        create_stepfunctions_agent(),
        
        # Infrastructure specialists
        create_iam_agent(),
        create_s3_agent(),
        create_sqs_agent(),
        create_sns_agent(),
        
        # Analysis specialists
        create_hypothesis_agent(),
        create_root_cause_agent()
    ]