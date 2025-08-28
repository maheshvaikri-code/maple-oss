import {
  IExecuteFunctions,
  INodeExecutionData,
  INodeType,
  INodeTypeDescription,
  NodeOperationError,
} from 'n8n-workflow';

import { MAPLEClient, MAPLEResourceRequest } from '../../lib/MAPLEClient';

// Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

export class MAPLEResourceManager implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'MAPLE Resource Manager',
    name: 'mapleResourceManager',
    icon: 'file:maple-resources.svg',
    group: ['ai'],
    version: 1,
    subtitle: '={{$parameter["operation"]}}',
    description: 'Manage resources for MAPLE multi-agent workflows. Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)',
    defaults: {
      name: 'MAPLE Resources',
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
            name: 'Allocate Resources',
            value: 'allocateResources',
            description: 'Allocate computing resources',
          },
          {
            name: 'Release Resources',
            value: 'releaseResources',
            description: 'Release allocated resources',
          },
          {
            name: 'Monitor Usage',
            value: 'monitorUsage',
            description: 'Monitor resource utilization',
          },
          {
            name: 'Optimize Allocation',
            value: 'optimizeAllocation',
            description: 'Optimize resource allocation',
          },
          {
            name: 'Check Availability',
            value: 'checkAvailability',
            description: 'Check resource availability',
          },
          {
            name: 'Request Negotiation',
            value: 'requestNegotiation',
            description: 'Negotiate resource requirements',
          },
        ],
        default: 'allocateResources',
        noDataExpression: true,
      },
      {
        displayName: 'Resource Type',
        name: 'resourceType',
        type: 'options',
        options: [
          { name: 'Compute', value: 'compute' },
          { name: 'Memory', value: 'memory' },
          { name: 'Storage', value: 'storage' },
          { name: 'Bandwidth', value: 'bandwidth' },
          { name: 'GPU', value: 'gpu' },
          { name: 'Custom', value: 'custom' },
        ],
        default: 'compute',
        displayOptions: {
          show: {
            operation: ['allocateResources', 'checkAvailability'],
          },
        },
      },
      {
        displayName: 'Compute Cores',
        name: 'computeCores',
        type: 'number',
        default: 2,
        description: 'Number of CPU cores to allocate',
        displayOptions: {
          show: {
            operation: ['allocateResources'],
            resourceType: ['compute'],
          },
        },
      },
      {
        displayName: 'Memory Amount',
        name: 'memoryAmount',
        type: 'string',
        default: '4GB',
        placeholder: 'e.g., 4GB, 8GB, 16GB',
        description: 'Amount of memory to allocate',
        displayOptions: {
          show: {
            operation: ['allocateResources'],
            resourceType: ['memory'],
          },
        },
      },
      {
        displayName: 'Storage Amount',
        name: 'storageAmount',
        type: 'string',
        default: '10GB',
        placeholder: 'e.g., 10GB, 100GB, 1TB',
        description: 'Amount of storage to allocate',
        displayOptions: {
          show: {
            operation: ['allocateResources'],
            resourceType: ['storage'],
          },
        },
      },
      {
        displayName: 'Bandwidth',
        name: 'bandwidth',
        type: 'string',
        default: '100Mbps',
        placeholder: 'e.g., 100Mbps, 1Gbps',
        description: 'Bandwidth requirement',
        displayOptions: {
          show: {
            operation: ['allocateResources'],
            resourceType: ['bandwidth'],
          },
        },
      },
      {
        displayName: 'GPU Type',
        name: 'gpuType',
        type: 'options',
        options: [
          { name: 'NVIDIA RTX 4090', value: 'rtx4090' },
          { name: 'NVIDIA RTX 3080', value: 'rtx3080' },
          { name: 'NVIDIA A100', value: 'a100' },
          { name: 'NVIDIA V100', value: 'v100' },
          { name: 'Any Available', value: 'any' },
        ],
        default: 'any',
        displayOptions: {
          show: {
            operation: ['allocateResources'],
            resourceType: ['gpu'],
          },
        },
      },
      {
        displayName: 'Custom Resource Specification',
        name: 'customResourceSpec',
        type: 'json',
        default: '{"type": "custom", "amount": 1, "unit": "units"}',
        placeholder: '{"type": "fpga", "model": "xilinx", "amount": 2}',
        description: 'JSON specification for custom resources',
        displayOptions: {
          show: {
            operation: ['allocateResources'],
            resourceType: ['custom'],
          },
        },
      },
      {
        displayName: 'Resource Priority',
        name: 'resourcePriority',
        type: 'options',
        options: [
          { name: 'Critical', value: 'HIGH' },
          { name: 'Normal', value: 'MEDIUM' },
          { name: 'Low', value: 'LOW' },
        ],
        default: 'MEDIUM',
        description: 'Priority level for resource allocation',
        displayOptions: {
          show: {
            operation: ['allocateResources', 'requestNegotiation'],
          },
        },
      },
      {
        displayName: 'Allocation Strategy',
        name: 'allocationStrategy',
        type: 'options',
        options: [
          {
            name: 'Best Fit',
            value: 'best_fit',
            description: 'Allocate the smallest sufficient resource pool',
          },
          {
            name: 'First Fit',
            value: 'first_fit',
            description: 'Allocate the first available resource pool',
          },
          {
            name: 'Balanced',
            value: 'balanced',
            description: 'Balance across multiple resource pools',
          },
          {
            name: 'Performance',
            value: 'performance',
            description: 'Prioritize performance over efficiency',
          },
        ],
        default: 'balanced',
        displayOptions: {
          show: {
            operation: ['allocateResources', 'optimizeAllocation'],
          },
        },
      },
      {
        displayName: 'Time Constraints',
        name: 'timeConstraints',
        type: 'fixedCollection',
        placeholder: 'Add Time Constraint',
        typeOptions: {
          multipleValues: false,
        },
        default: {},
        displayOptions: {
          show: {
            operation: ['allocateResources', 'requestNegotiation'],
          },
        },
        options: [
          {
            name: 'constraint',
            displayName: 'Time Constraint',
            values: [
              {
                displayName: 'Deadline',
                name: 'deadline',
                type: 'dateTime',
                default: '',
                description: 'When resources must be available',
              },
              {
                displayName: 'Timeout',
                name: 'timeout',
                type: 'string',
                default: '30s',
                placeholder: 'e.g., 30s, 5m, 1h',
                description: 'Maximum time to wait for allocation',
              },
              {
                displayName: 'Usage Duration',
                name: 'usageDuration',
                type: 'string',
                default: '1h',
                placeholder: 'e.g., 1h, 30m, 2h',
                description: 'How long resources will be used',
              },
            ],
          },
        ],
      },
      {
        displayName: 'Resource Pool',
        name: 'resourcePool',
        type: 'options',
        options: [
          { name: 'Default Pool', value: 'default' },
          { name: 'High Performance Pool', value: 'high_performance' },
          { name: 'GPU Pool', value: 'gpu_pool' },
          { name: 'Edge Computing Pool', value: 'edge_pool' },
          { name: 'Custom Pool', value: 'custom' },
        ],
        default: 'default',
        description: 'Resource pool to allocate from',
        displayOptions: {
          show: {
            operation: ['allocateResources', 'checkAvailability'],
          },
        },
      },
      {
        displayName: 'Custom Pool Name',
        name: 'customPoolName',
        type: 'string',
        default: '',
        placeholder: 'e.g., research-cluster-01',
        description: 'Name of the custom resource pool',
        displayOptions: {
          show: {
            operation: ['allocateResources', 'checkAvailability'],
            resourcePool: ['custom'],
          },
        },
      },
      {
        displayName: 'Allocation ID',
        name: 'allocationId',
        type: 'string',
        default: '',
        placeholder: 'alloc-123456',
        description: 'ID of the allocation to release or monitor',
        displayOptions: {
          show: {
            operation: ['releaseResources', 'monitorUsage'],
          },
        },
        required: true,
      },
      {
        displayName: 'Optimization Goals',
        name: 'optimizationGoals',
        type: 'multiOptions',
        options: [
          { name: 'Minimize Cost', value: 'cost' },
          { name: 'Maximize Performance', value: 'performance' },
          { name: 'Balance Load', value: 'load_balance' },
          { name: 'Energy Efficiency', value: 'energy' },
          { name: 'Minimize Latency', value: 'latency' },
        ],
        default: ['performance', 'cost'],
        description: 'Goals for resource optimization',
        displayOptions: {
          show: {
            operation: ['optimizeAllocation'],
          },
        },
      },
      {
        displayName: 'Negotiation Parameters',
        name: 'negotiationParams',
        type: 'fixedCollection',
        placeholder: 'Add Parameter',
        typeOptions: {
          multipleValues: false,
        },
        default: {},
        displayOptions: {
          show: {
            operation: ['requestNegotiation'],
          },
        },
        options: [
          {
            name: 'parameter',
            displayName: 'Negotiation Parameter',
            values: [
              {
                displayName: 'Flexibility',
                name: 'flexibility',
                type: 'options',
                options: [
                  { name: 'Strict', value: 'strict' },
                  { name: 'Moderate', value: 'moderate' },
                  { name: 'Flexible', value: 'flexible' },
                ],
                default: 'moderate',
                description: 'How flexible the requirements are',
              },
              {
                displayName: 'Acceptable Trade-offs',
                name: 'tradeoffs',
                type: 'multiOptions',
                options: [
                  { name: 'Lower Performance', value: 'performance' },
                  { name: 'Higher Cost', value: 'cost' },
                  { name: 'Longer Wait Time', value: 'wait_time' },
                  { name: 'Shorter Duration', value: 'duration' },
                ],
                default: ['wait_time'],
                description: 'Acceptable trade-offs for negotiation',
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

    const credentials = await this.getCredentials('mapleApi');
    const client = new MAPLEClient({
      brokerUrl: credentials.brokerUrl as string,
      apiKey: credentials.apiKey as string,
      agentId: credentials.agentId as string,
      pythonBridgeUrl: credentials.pythonBridgeUrl as string,
      requestTimeout: credentials.requestTimeout as number || 45000, // Longer timeout for resource operations
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
        `Failed to connect to MAPLE resource manager: ${error.message}`
      );
    }

    const returnData: INodeExecutionData[] = [];

    for (let i = 0; i < items.length; i++) {
      try {
        let result: any;

        switch (operation) {
          case 'allocateResources':
            result = await this.allocateResources(client, i);
            break;

          case 'releaseResources':
            result = await this.releaseResources(client, i);
            break;

          case 'monitorUsage':
            result = await this.monitorUsage(client, i);
            break;

          case 'optimizeAllocation':
            result = await this.optimizeAllocation(client, i);
            break;

          case 'checkAvailability':
            result = await this.checkAvailability(client, i);
            break;

          case 'requestNegotiation':
            result = await this.requestNegotiation(client, i);
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

  private async allocateResources(client: MAPLEClient, itemIndex: number): Promise<any> {
    const resourceType = this.getNodeParameter('resourceType', itemIndex) as string;
    const priority = this.getNodeParameter('resourcePriority', itemIndex, 'MEDIUM') as 'HIGH' | 'MEDIUM' | 'LOW';
    const strategy = this.getNodeParameter('allocationStrategy', itemIndex, 'balanced') as string;
    const timeConstraints = this.getNodeParameter('timeConstraints', itemIndex, {}) as any;
    const resourcePool = this.getNodeParameter('resourcePool', itemIndex, 'default') as string;
    const customPoolName = this.getNodeParameter('customPoolName', itemIndex, '') as string;

    let resourceRequest: MAPLEResourceRequest = {
      priority,
    };

    // Add time constraints
    if (timeConstraints.constraint) {
      if (timeConstraints.constraint.deadline) {
        resourceRequest.deadline = new Date(timeConstraints.constraint.deadline).toISOString();
      }
      if (timeConstraints.constraint.timeout) {
        resourceRequest.timeout = timeConstraints.constraint.timeout;
      }
    }

    // Build resource specification based on type
    switch (resourceType) {
      case 'compute':
        const computeCores = this.getNodeParameter('computeCores', itemIndex) as number;
        resourceRequest.compute = computeCores;
        break;

      case 'memory':
        const memoryAmount = this.getNodeParameter('memoryAmount', itemIndex) as string;
        resourceRequest.memory = memoryAmount;
        break;

      case 'storage':
        const storageAmount = this.getNodeParameter('storageAmount', itemIndex) as string;
        resourceRequest.storage = storageAmount;
        break;

      case 'bandwidth':
        const bandwidth = this.getNodeParameter('bandwidth', itemIndex) as string;
        resourceRequest.bandwidth = bandwidth;
        break;

      case 'gpu':
        const gpuType = this.getNodeParameter('gpuType', itemIndex) as string;
        resourceRequest = {
          ...resourceRequest,
          compute: 1, // GPU requires compute allocation
          // Add GPU-specific metadata
        };
        break;

      case 'custom':
        const customResourceSpec = this.getNodeParameter('customResourceSpec', itemIndex) as string;
        try {
          const customSpec = JSON.parse(customResourceSpec);
          resourceRequest = { ...resourceRequest, ...customSpec };
        } catch (error: any) {
          throw new Error(`Invalid custom resource specification: ${error.message}`);
        }
        break;
    }

    // Add metadata
    const metadata = {
      strategy,
      resourceType,
      resourcePool: resourcePool === 'custom' ? customPoolName : resourcePool,
      requestedAt: new Date().toISOString(),
    };

    const result = await client.allocateResources(resourceRequest);
    if (result.isOk) {
      return {
        allocation: result.value,
        metadata,
        resourceRequest,
      };
    } else {
      throw new Error(result.error);
    }
  }

  private async releaseResources(client: MAPLEClient, itemIndex: number): Promise<any> {
    const allocationId = this.getNodeParameter('allocationId', itemIndex) as string;

    // This would typically call a release resources API
    // For now, we'll simulate with a message
    const releaseResult = await client.sendMessage({
      header: {
        messageType: 'RESOURCE_RELEASE',
        priority: 'MEDIUM',
      },
      payload: {
        allocationId,
        requestedAt: new Date().toISOString(),
      },
    });

    if (releaseResult.isOk) {
      return {
        allocationId,
        status: 'released',
        releasedAt: new Date().toISOString(),
      };
    } else {
      throw new Error(releaseResult.error);
    }
  }

  private async monitorUsage(client: MAPLEClient, itemIndex: number): Promise<any> {
    const allocationId = this.getNodeParameter('allocationId', itemIndex) as string;

    // This would typically query usage metrics
    const monitorResult = await client.sendMessage({
      header: {
        messageType: 'RESOURCE_MONITOR',
        priority: 'LOW',
      },
      payload: {
        allocationId,
        requestedAt: new Date().toISOString(),
      },
    });

    if (monitorResult.isOk) {
      return {
        allocationId,
        usage: monitorResult.value?.usage || {
          cpu: Math.random() * 100,
          memory: Math.random() * 100,
          bandwidth: Math.random() * 100,
        },
        timestamp: new Date().toISOString(),
      };
    } else {
      // Return mock data for demo
      return {
        allocationId,
        usage: {
          cpu: Math.random() * 100,
          memory: Math.random() * 100,
          bandwidth: Math.random() * 100,
        },
        timestamp: new Date().toISOString(),
        note: 'Mock usage data - monitoring not yet implemented',
      };
    }
  }

  private async optimizeAllocation(client: MAPLEClient, itemIndex: number): Promise<any> {
    const optimizationGoals = this.getNodeParameter('optimizationGoals', itemIndex) as string[];
    const strategy = this.getNodeParameter('allocationStrategy', itemIndex, 'balanced') as string;

    const optimizeResult = await client.sendMessage({
      header: {
        messageType: 'RESOURCE_OPTIMIZE',
        priority: 'MEDIUM',
      },
      payload: {
        goals: optimizationGoals,
        strategy,
        requestedAt: new Date().toISOString(),
      },
    });

    if (optimizeResult.isOk) {
      return optimizeResult.value;
    } else {
      // Return mock optimization result
      return {
        optimization: {
          goals: optimizationGoals,
          strategy,
          improvements: {
            costReduction: Math.random() * 20,
            performanceGain: Math.random() * 15,
            efficiencyIncrease: Math.random() * 10,
          },
          recommendations: [
            'Consider consolidating workloads during low-usage periods',
            'Migrate non-critical tasks to lower-cost resource pools',
            'Implement auto-scaling for variable workloads',
          ],
        },
        timestamp: new Date().toISOString(),
        note: 'Mock optimization data - optimization not yet implemented',
      };
    }
  }

  private async checkAvailability(client: MAPLEClient, itemIndex: number): Promise<any> {
    const resourceType = this.getNodeParameter('resourceType', itemIndex) as string;
    const resourcePool = this.getNodeParameter('resourcePool', itemIndex, 'default') as string;
    const customPoolName = this.getNodeParameter('customPoolName', itemIndex, '') as string;

    const availabilityResult = await client.sendMessage({
      header: {
        messageType: 'RESOURCE_AVAILABILITY',
        priority: 'LOW',
      },
      payload: {
        resourceType,
        resourcePool: resourcePool === 'custom' ? customPoolName : resourcePool,
        requestedAt: new Date().toISOString(),
      },
    });

    if (availabilityResult.isOk) {
      return availabilityResult.value;
    } else {
      // Return mock availability data
      return {
        resourceType,
        resourcePool: resourcePool === 'custom' ? customPoolName : resourcePool,
        availability: {
          compute: {
            total: 100,
            available: Math.floor(Math.random() * 50) + 25,
            allocated: Math.floor(Math.random() * 50) + 25,
          },
          memory: {
            total: '1TB',
            available: `${Math.floor(Math.random() * 500) + 200}GB`,
            allocated: `${Math.floor(Math.random() * 300) + 100}GB`,
          },
          storage: {
            total: '10TB',
            available: `${Math.floor(Math.random() * 5) + 2}TB`,
            allocated: `${Math.floor(Math.random() * 3) + 1}TB`,
          },
        },
        timestamp: new Date().toISOString(),
        note: 'Mock availability data - availability check not yet implemented',
      };
    }
  }

  private async requestNegotiation(client: MAPLEClient, itemIndex: number): Promise<any> {
    const priority = this.getNodeParameter('resourcePriority', itemIndex, 'MEDIUM') as 'HIGH' | 'MEDIUM' | 'LOW';
    const negotiationParams = this.getNodeParameter('negotiationParams', itemIndex, {}) as any;

    const negotiationResult = await client.sendMessage({
      header: {
        messageType: 'RESOURCE_NEGOTIATE',
        priority,
      },
      payload: {
        flexibility: negotiationParams.parameter?.flexibility || 'moderate',
        acceptableTradeoffs: negotiationParams.parameter?.tradeoffs || ['wait_time'],
        requestedAt: new Date().toISOString(),
      },
    });

    if (negotiationResult.isOk) {
      return negotiationResult.value;
    } else {
      // Return mock negotiation result
      return {
        negotiation: {
          status: 'completed',
          originalRequest: {
            priority,
            flexibility: negotiationParams.parameter?.flexibility || 'moderate',
          },
          negotiatedTerms: {
            costReduction: Math.random() * 15,
            waitTime: `${Math.floor(Math.random() * 10) + 2}m`,
            guaranteedResources: Math.floor(Math.random() * 30) + 70, // 70-100%
          },
          alternatives: [
            {
              option: 'immediate_partial',
              description: 'Get 80% resources immediately',
              tradeoff: 'Reduced performance',
            },
            {
              option: 'scheduled_full',
              description: 'Get full resources in 15 minutes',
              tradeoff: 'Longer wait time',
            },
          ],
        },
        timestamp: new Date().toISOString(),
        note: 'Mock negotiation data - negotiation not yet implemented',
      };
    }
  }
}
