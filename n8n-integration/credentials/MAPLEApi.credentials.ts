import {
  IAuthenticateGeneric,
  ICredentialTestRequest,
  ICredentialType,
  INodeProperties,
} from 'n8n-workflow';

// Creator: Mahesh Vaijainthymala Krishnamoorthy (Mahesh Vaikri)

export class MAPLEApi implements ICredentialType {
  name = 'mapleApi';
  displayName = 'MAPLE API';
  documentationUrl = 'https://github.com/mahesh-vaikri/maple-n8n-nodes';
  properties: INodeProperties[] = [
    {
      displayName: 'Connection Type',
      name: 'connectionType',
      type: 'options',
      options: [
        {
          name: 'WebSocket',
          value: 'websocket',
          description: 'Connect via WebSocket to MAPLE broker'
        },
        {
          name: 'Python Bridge',
          value: 'python',
          description: 'Connect via Python MAPLE implementation'
        },
        {
          name: 'Hybrid',
          value: 'hybrid',
          description: 'Use Python bridge with WebSocket fallback'
        }
      ],
      default: 'hybrid',
    },
    {
      displayName: 'Broker URL',
      name: 'brokerUrl',
      type: 'string',
      default: 'ws://localhost:8080/maple',
      placeholder: 'wss://your-maple-broker.com/ws',
      description: 'WebSocket URL of your MAPLE broker',
      displayOptions: {
        show: {
          connectionType: ['websocket', 'hybrid'],
        },
      },
    },
    {
      displayName: 'Python Bridge URL',
      name: 'pythonBridgeUrl',
      type: 'string',
      default: 'http://localhost:8000',
      placeholder: 'http://localhost:8000',
      description: 'HTTP URL of the MAPLE Python bridge server',
      displayOptions: {
        show: {
          connectionType: ['python', 'hybrid'],
        },
      },
    },
    {
      displayName: 'API Key',
      name: 'apiKey',
      type: 'string',
      typeOptions: { password: true },
      default: '',
      placeholder: 'maple_api_key_...',
      description: 'API key for MAPLE broker authentication',
      required: true,
    },
    {
      displayName: 'Agent ID',
      name: 'agentId',
      type: 'string',
      default: 'n8n-workflow-agent',
      placeholder: 'n8n-workflow-agent',
      description: 'Unique identifier for this n8n workflow agent',
      required: true,
    },
    {
      displayName: 'Request Timeout (ms)',
      name: 'requestTimeout',
      type: 'number',
      default: 30000,
      description: 'Timeout for requests in milliseconds',
    },
    {
      displayName: 'Enable Reconnection',
      name: 'enableReconnect',
      type: 'boolean',
      default: true,
      description: 'Whether to automatically reconnect on connection loss',
    },
    {
      displayName: 'Max Reconnect Attempts',
      name: 'maxReconnectAttempts',
      type: 'number',
      default: 5,
      description: 'Maximum number of reconnection attempts',
      displayOptions: {
        show: {
          enableReconnect: [true],
        },
      },
    },
  ];

  authenticate: IAuthenticateGeneric = {
    type: 'generic',
    properties: {
      headers: {
        'Authorization': '=Bearer {{$credentials.apiKey}}',
        'X-MAPLE-Agent-ID': '={{$credentials.agentId}}',
        'X-MAPLE-Client': 'n8n-integration',
      },
    },
  };

  test: ICredentialTestRequest = {
    request: {
      baseURL: '={{$credentials.pythonBridgeUrl || $credentials.brokerUrl.replace("ws://", "http://").replace("wss://", "https://")}}',
      url: '/health',
      method: 'GET',
      headers: {
        'Authorization': '=Bearer {{$credentials.apiKey}}',
      },
    },
    rules: [
      {
        type: 'responseSuccessBody',
        properties: {
          key: 'status',
          value: 'ok',
        },
      },
    ],
  };
}
