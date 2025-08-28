import {
  IExecuteFunctions,
  INodeExecutionData,
  INodeType,
  INodeTypeDescription,
  NodeOperationError,
} from 'n8n-workflow';

import { MAPLEClient, MAPLEWorkflow, MAPLEWorkflowStep } from '../../lib/MAPLEClient';

// Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

export class MAPLECoordinator implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'MAPLE Coordinator',
    name: 'mapleCoordinator',
    icon: 'file:maple-coord.svg',
    group: ['ai'],
    version: 1,
    subtitle: '={{$parameter["operation"]}}',
    description: 'Coordinate multiple MAPLE agents in complex workflows. Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)',
    defaults: {
      name: 'MAPLE Coordinator',
    },
    inputs: ['main'],
    outputs: ['main'],
    credentials: [
      {
        name: 'mapleApi',
        required: true,
      },
    ],
    properties: [
      {
        displayName: 'Operation',
        name: 'operation',
        type: 'options',
        options: [
          {
            name: 'Create Workflow',
            value: 'createWorkflow',
            description: 'Create a new multi-agent workflow',
          },
          {
            name: 'Execute Workflow',
            value: 'executeWorkflow',
            description: 'Execute an existing workflow',
          },
          {
            name: 'Orchestrate Agents',
            value: 'orchestrateAgents',
            description: 'Orchestrate multiple agents for a task',
          },
          {
            name: 'Monitor Execution',
            value: 'monitorExecution',
            description: 'Monitor workflow execution status',
          },
          {
            name: 'Sequential Pipeline',
            value: 'sequentialPipeline',
            description: 'Execute agents in sequence',
          },
          {
            name: 'Parallel Processing',
            value: 'parallelProcessing',
            description: 'Execute agents in parallel',
          },
        ],
        default: 'orchestrateAgents',
        noDataExpression: true,
      },
      {
        displayName: 'Workflow Name',
        name: 'workflowName',
        type: 'string',
        default: 'Multi-Agent Workflow',
        placeholder: 'e.g., AI Research Pipeline',
        description: 'Name for the workflow',
        displayOptions: {
          show: {
            operation: ['createWorkflow'],
          },
        },
      },
      {
        displayName: 'Workflow ID',
        name: 'workflowId',
        type: 'string',
        default: '',
        placeholder: 'workflow-123',
        description: 'ID of the workflow to execute',
        displayOptions: {
          show: {
            operation: ['executeWorkflow', 'monitorExecution'],
          },
        },
        required: true,
      },
      {
        displayName: 'Agents',
        name: 'agents',
        type: 'fixedCollection',
        placeholder: 'Add Agent',
        typeOptions: {
          multipleValues: true,
        },
        default: { agent: [] },
        displayOptions: {
          show: {
            operation: ['orchestrateAgents', 'sequentialPipeline', 'parallelProcessing'],
          },
        },
        options: [
          {
            name: 'agent',
            displayName: 'Agent Configuration',
            values: [
              {
                displayName: 'Agent ID',
                name: 'agentId',
                type: 'string',
                default: '',
                placeholder: 'e.g., search-agent-001',
                required: true,
              },
              {
                displayName: 'Task Type',
                name: 'taskType',
                type: 'options',
                options: [
                  { name: 'Search Web', value: 'SEARCH_WEB' },
                  { name: 'Analyze Content', value: 'ANALYZE_CONTENT' },
                  { name: 'Generate Summary', value: 'GENERATE_SUMMARY' },
                  { name: 'Process Data', value: 'PROCESS_DATA' },
                  { name: 'Generate Content', value: 'GENERATE_CONTENT' },
                  { name: 'Custom Task', value: 'CUSTOM' },
                ],
                default: 'SEARCH_WEB',
              },
              {
                displayName: 'Task Parameters',
                name: 'taskParameters',
                type: 'json',
                default: '{}',
                placeholder: '{"query": "AI trends", "sources": 5}',
                description: 'JSON parameters for the task',
              },
              {
                displayName: 'Priority',
                name: 'priority',
                type: 'options',
                options: [
                  { name: 'High', value: 'HIGH' },
                  { name: 'Medium', value: 'MEDIUM' },
                  { name: 'Low', value: 'LOW' },
                ],
                default: 'MEDIUM',
              },
              {
                displayName: 'Timeout',
                name: 'timeout',
                type: 'string',
                default: '30s',
                placeholder: 'e.g., 30s, 5m',
                description: 'Maximum execution time',
              },
            ],
          },
        ],
      },
      {
        displayName: 'Workflow Steps',
        name: 'workflowSteps',
        type: 'fixedCollection',
        placeholder: 'Add Step',
        typeOptions: {
          multipleValues: true,
        },
        default: { step: [] },
        displayOptions: {
          show: {
            operation: ['createWorkflow'],
          },
        },
        options: [
          {
            name: 'step',
            displayName: 'Workflow Step',
            values: [
              {
                displayName: 'Step Name',
                name: 'stepName',
                type: 'string',
                default: '',
                placeholder: 'e.g., Web Search',
                required: true,
              },
              {
                displayName: 'Agent ID',
                name: 'agentId',
                type: 'string',
                default: '',
                placeholder: 'e.g., search-agent-001',
                required: true,
              },
              {
                displayName: 'Operation',
                name: 'operation',
                type: 'string',
                default: 'execute_task',
                placeholder: 'e.g., execute_task, analyze_data',
              },
              {
                displayName: 'Parameters',
                name: 'parameters',
                type: 'json',
                default: '{}',
                placeholder: '{"query": "{{input.query}}"}',
              },
              {
                displayName: 'Dependencies',
                name: 'dependencies',
                type: 'string',
                default: '',
                placeholder: 'step1,step2',
                description: 'Comma-separated list of step IDs this step depends on',
              },
            ],
          },
        ],
      },
      {
        displayName: 'Coordination Strategy',
        name: 'coordinationStrategy',
        type: 'options',
        options: [
          {
            name: 'Sequential',
            value: 'sequential',
            description: 'Execute agents one after another',
          },
          {
            name: 'Parallel',
            value: 'parallel',
            description: 'Execute all agents simultaneously',
          },
          {
            name: 'Pipeline',
            value: 'pipeline',
            description: 'Create a data processing pipeline',
          },
          {
            name: 'Dynamic',
            value: 'dynamic',
            description: 'Dynamically choose based on conditions',
          },
        ],
        default: 'sequential',
        displayOptions: {
          show: {
            operation: ['orchestrateAgents'],
          },
        },
      },
      {
        displayName: 'Error Handling Strategy',
        name: 'errorHandling',
        type: 'options',
        options: [
          {
            name: 'Fail Fast',
            value: 'fail_fast',
            description: 'Stop on first error',
          },
          {
            name: 'Continue on Error',
            value: 'continue',
            description: 'Continue with remaining agents',
          },
          {
            name: 'Retry Failed',
            value: 'retry',
            description: 'Retry failed agents',
          },
          {
            name: 'Fallback',
            value: 'fallback',
            description: 'Use fallback agents on failure',
          },
        ],
        default: 'retry',
      },
      {
        displayName: 'Max Retry Attempts',
        name: 'maxRetries',
        type: 'number',
        default: 3,
        description: 'Maximum retry attempts for failed operations',
        displayOptions: {
          show: {
            errorHandling: ['retry'],
          },
        },
      },
      {
        displayName: 'Resource Requirements',
        name: 'globalResources',
        type: 'fixedCollection',
        placeholder: 'Add Resource',
        typeOptions: {
          multipleValues: false,
        },
        default: {},
        options: [
          {
            name: 'resourceRequirement',
            displayName: 'Global Resource Requirements',
            values: [
              {
                displayName: 'Total Compute',
                name: 'compute',
                type: 'number',
                default: 4,
                description: 'Total CPU cores for the workflow',
              },
              {
                displayName: 'Total Memory',
                name: 'memory',
                type: 'string',
                default: '8GB',
                placeholder: 'e.g., 8GB, 16GB',
              },
              {
                displayName: 'Max Execution Time',
                name: 'timeout',
                type: 'string',
                default: '5m',
                placeholder: 'e.g., 5m, 30s, 1h',
              },
            ],
          },
        ],
      },
    ],
  };

  async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const items = this.getInputData();
    const operation = this.getNodeParameter('operation', 0) as string;
    const errorHandling = this.getNodeParameter('errorHandling', 0, 'retry') as string;
    const maxRetries = this.getNodeParameter('maxRetries', 0, 3) as number;

    const credentials = await this.getCredentials('mapleApi');
    const client = new MAPLEClient({
      brokerUrl: credentials.brokerUrl as string,
      apiKey: credentials.apiKey as string,
      agentId: credentials.agentId as string,
      pythonBridgeUrl: credentials.pythonBridgeUrl as string,
      requestTimeout: credentials.requestTimeout as number || 60000, // Longer timeout for coordination
      reconnect: credentials.enableReconnect as boolean || true,
      maxReconnectAttempts: credentials.maxReconnectAttempts as number || 5,
    });

    try {
      const connectResult = await client.connect();
      if (!connectResult.isOk) {
        throw new NodeOperationError(
          this.getNode(),
          `Failed to connect to MAPLE: ${connectResult.error}`
        );
      }
    } catch (error: any) {
      throw new NodeOperationError(
        this.getNode(),
        `Failed to connect to MAPLE coordinator: ${error.message}`
      );
    }

    const returnData: INodeExecutionData[] = [];

    for (let i = 0; i < items.length; i++) {
      try {
        let result: any;

        switch (operation) {
          case 'createWorkflow':
            result = await this.createWorkflow(client, i);
            break;

          case 'executeWorkflow':
            result = await this.executeWorkflow(client, i);
            break;

          case 'orchestrateAgents':
            result = await this.orchestrateAgents(client, i);
            break;

          case 'sequentialPipeline':
            result = await this.executeSequentialPipeline(client, i);
            break;

          case 'parallelProcessing':
            result = await this.executeParallelProcessing(client, i);
            break;

          case 'monitorExecution':
            result = await this.monitorExecution(client, i);
            break;

          default:
            throw new NodeOperationError(
              this.getNode(),
              `Unknown operation: ${operation}`
            );
        }

        returnData.push({
          json: {
            success: true,
            operation,
            result,
            timestamp: new Date().toISOString(),
            creator: 'Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)',
            ...result,
          },
        });
      } catch (error: any) {
        if (this.continueOnFail()) {
          returnData.push({
            json: {
              success: false,
              operation,
              error: error.message,
              timestamp: new Date().toISOString(),
              creator: 'Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)',
            },
          });
        } else {
          throw new NodeOperationError(this.getNode(), error.message);
        }
      }
    }

    client.disconnect();
    return [returnData];
  }

  private async createWorkflow(client: MAPLEClient, itemIndex: number): Promise<any> {
    const workflowName = this.getNodeParameter('workflowName', itemIndex) as string;
    const workflowSteps = this.getNodeParameter('workflowSteps', itemIndex, { step: [] }) as any;
    const globalResources = this.getNodeParameter('globalResources', itemIndex, {}) as any;

    const steps: MAPLEWorkflowStep[] = workflowSteps.step.map((step: any, index: number) => ({
      stepId: `step_${index + 1}`,
      name: step.stepName,
      agentId: step.agentId,
      operation: step.operation,
      parameters: JSON.parse(step.parameters || '{}'),
      dependencies: step.dependencies ? step.dependencies.split(',').map((s: string) => s.trim()) : [],
    }));

    const workflow: Omit<MAPLEWorkflow, 'workflowId' | 'status'> = {
      name: workflowName,
      description: `Multi-agent workflow created via n8n`,
      agents: [...new Set(steps.map(step => step.agentId))],
      steps,
      resources: globalResources.resourceRequirement || {},
      metadata: {
        createdBy: 'n8n-maple-coordinator',
        creator: 'Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)',
        source: 'n8n',
      },
    };

    const result = await client.createWorkflow(workflow);
    if (result.isOk) {
      return { workflowId: result.value, workflow };
    } else {
      throw new Error(result.error);
    }
  }

  private async executeWorkflow(client: MAPLEClient, itemIndex: number): Promise<any> {
    const workflowId = this.getNodeParameter('workflowId', itemIndex) as string;
    const inputData = this.getInputData()[itemIndex].json;

    const result = await client.executeWorkflow(workflowId, inputData);
    if (result.isOk) {
      return result.value;
    } else {
      throw new Error(result.error);
    }
  }

  private async orchestrateAgents(client: MAPLEClient, itemIndex: number): Promise<any> {
    const agents = this.getNodeParameter('agents', itemIndex, { agent: [] }) as any;
    const coordinationStrategy = this.getNodeParameter('coordinationStrategy', itemIndex) as string;
    const inputData = this.getInputData()[itemIndex].json;

    const agentConfigs = agents.agent.map((agent: any) => ({
      agentId: agent.agentId,
      taskType: agent.taskType,
      taskParameters: JSON.parse(agent.taskParameters || '{}'),
      priority: agent.priority,
      timeout: agent.timeout,
    }));

    switch (coordinationStrategy) {
      case 'sequential':
        return await this.executeSequentialCoordination(client, agentConfigs, inputData);
      case 'parallel':
        return await this.executeParallelCoordination(client, agentConfigs, inputData);
      case 'pipeline':
        return await this.executePipelineCoordination(client, agentConfigs, inputData);
      default:
        throw new Error(`Unknown coordination strategy: ${coordinationStrategy}`);
    }
  }

  private async executeSequentialPipeline(client: MAPLEClient, itemIndex: number): Promise<any> {
    const agents = this.getNodeParameter('agents', itemIndex, { agent: [] }) as any;
    const inputData = this.getInputData()[itemIndex].json;

    let currentData = inputData;
    const results: any[] = [];

    for (const agentConfig of agents.agent) {
      const taskParameters = JSON.parse(agentConfig.taskParameters || '{}');
      const mergedTask = { ...taskParameters, ...currentData };

      const taskResult = await client.executeTask({
        agentId: agentConfig.agentId,
        task: mergedTask,
        priority: agentConfig.priority,
      });

      if (taskResult.isOk) {
        currentData = taskResult.value;
        results.push({
          agentId: agentConfig.agentId,
          result: taskResult.value,
          timestamp: new Date().toISOString(),
        });
      } else {
        throw new Error(`Agent ${agentConfig.agentId} failed: ${taskResult.error}`);
      }
    }

    return { strategy: 'sequential', results, finalResult: currentData };
  }

  private async executeParallelProcessing(client: MAPLEClient, itemIndex: number): Promise<any> {
    const agents = this.getNodeParameter('agents', itemIndex, { agent: [] }) as any;
    const inputData = this.getInputData()[itemIndex].json;

    const taskPromises = agents.agent.map(async (agentConfig: any) => {
      const taskParameters = JSON.parse(agentConfig.taskParameters || '{}');
      const mergedTask = { ...taskParameters, ...inputData };

      const taskResult = await client.executeTask({
        agentId: agentConfig.agentId,
        task: mergedTask,
        priority: agentConfig.priority,
      });

      return {
        agentId: agentConfig.agentId,
        success: taskResult.isOk,
        result: taskResult.isOk ? taskResult.value : null,
        error: taskResult.isOk ? null : taskResult.error,
        timestamp: new Date().toISOString(),
      };
    });

    const results = await Promise.all(taskPromises);
    const successful = results.filter(r => r.success);
    const failed = results.filter(r => !r.success);

    return {
      strategy: 'parallel',
      summary: {
        total: results.length,
        successful: successful.length,
        failed: failed.length,
      },
      results,
      aggregatedResult: successful.map(r => r.result),
    };
  }

  private async executeSequentialCoordination(client: MAPLEClient, agentConfigs: any[], inputData: any): Promise<any> {
    let currentData = inputData;
    const results: any[] = [];

    for (const config of agentConfigs) {
      const mergedTask = { ...config.taskParameters, ...currentData };

      const taskResult = await client.executeTask({
        agentId: config.agentId,
        task: mergedTask,
        priority: config.priority,
      });

      if (taskResult.isOk) {
        currentData = taskResult.value;
        results.push({ agentId: config.agentId, result: taskResult.value });
      } else {
        throw new Error(`Sequential coordination failed at agent ${config.agentId}: ${taskResult.error}`);
      }
    }

    return { strategy: 'sequential', results, finalResult: currentData };
  }

  private async executeParallelCoordination(client: MAPLEClient, agentConfigs: any[], inputData: any): Promise<any> {
    const taskPromises = agentConfigs.map(async (config) => {
      const mergedTask = { ...config.taskParameters, ...inputData };
      const taskResult = await client.executeTask({
        agentId: config.agentId,
        task: mergedTask,
        priority: config.priority,
      });

      return {
        agentId: config.agentId,
        success: taskResult.isOk,
        result: taskResult.isOk ? taskResult.value : null,
        error: taskResult.isOk ? null : taskResult.error,
      };
    });

    const results = await Promise.all(taskPromises);
    return { strategy: 'parallel', results };
  }

  private async executePipelineCoordination(client: MAPLEClient, agentConfigs: any[], inputData: any): Promise<any> {
    // Similar to sequential but with explicit data passing
    return await this.executeSequentialCoordination(client, agentConfigs, inputData);
  }

  private async monitorExecution(client: MAPLEClient, itemIndex: number): Promise<any> {
    const workflowId = this.getNodeParameter('workflowId', itemIndex) as string;
    
    // This would typically query the workflow status
    // For now, return a mock monitoring result
    return {
      workflowId,
      status: 'monitoring',
      message: 'Workflow monitoring not yet implemented',
      timestamp: new Date().toISOString(),
    };
  }
}
