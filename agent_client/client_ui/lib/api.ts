import { AIAgent, ChatSession, ChatMessage, CreateSessionRequest, SendMessageRequest, ChatResponse } from './types';

// API base configuration
const API_BASE_URL = process.env.NODE_ENV === 'development' 
  ? '' 
  : '';

// Generic API request function
async function apiRequest<T>(
  endpoint: string, 
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(error.error || `HTTP ${response.status}`);
  }

  return response.json();
}

// Agent API
export const agentsApi = {
  // Get all agents (discovered from ISEK network)
  async getAgents(): Promise<AIAgent[]> {
    return apiRequest<AIAgent[]>('/api/agents');
  },

  // Get specific agent
  async getAgent(id: string): Promise<AIAgent> {
    return apiRequest<AIAgent>(`/api/agents/${id}`);
  },
};

// Network status API
export const networkApi = {
  // Get ISEK network status
  async getNetworkStatus(): Promise<{
    connected: boolean;
    node_url: string;
    discovery_url: string;
    agents_count: number;
    timestamp: string;
  }> {
    return apiRequest('/api/network/status');
  },
};

// Session API
export const sessionsApi = {
  // Get all sessions
  async getSessions(): Promise<ChatSession[]> {
    return apiRequest<ChatSession[]>('/api/sessions');
  },

  // Create new session
  async createSession(request: CreateSessionRequest): Promise<ChatSession> {
    return apiRequest<ChatSession>('/api/sessions', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  // Delete session
  async deleteSession(id: string): Promise<void> {
    return apiRequest<void>(`/api/sessions/${id}`, {
      method: 'DELETE',
    });
  },

  // Sync sessions from agent servers
  async syncSessions(): Promise<{
    message: string;
    count: number;
    sessions: ChatSession[];
  }> {
    return apiRequest('/api/sessions/sync', {
      method: 'POST',
    });
  },
};

// Message API
export const messagesApi = {
  // Get all messages in session
  async getMessages(sessionId: string): Promise<ChatMessage[]> {
    return apiRequest<ChatMessage[]>(`/api/sessions/${sessionId}/messages`);
  },

  // Create new message
  async createMessage(sessionId: string, content: string, role: 'user' | 'assistant' = 'user'): Promise<ChatMessage> {
    return apiRequest<ChatMessage>(`/api/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content, role }),
    });
  },
};

// Chat API - Communicate with agents through ISEK network
export const chatApi = {
  // Send chat message to specific agent
  async sendMessage(request: SendMessageRequest): Promise<ChatResponse> {
    return apiRequest<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  // Simplified send message interface
  async sendMessageSimple(
    message: string, 
    sessionId: string, 
    agentId: string,
    messages: ChatMessage[] = []
  ): Promise<ChatResponse> {
    // Get agent information
    const agent = await agentsApi.getAgent(agentId);
    
    const request: SendMessageRequest = {
      agentId,
      address: agent.node_id,
      sessionId,
      messages,
      system: `${agent.knowledge}\n\nRoutine: ${agent.routine}`,
    };

    return this.sendMessage(request);
  },

  // 流式发送消息，返回异步生成器
  async *sendMessageStream(
    message: string,
    sessionId: string,
    agentId: string,
    messages: ChatMessage[] = [],
    signal?: AbortSignal
  ) {
    const agent = await agentsApi.getAgent(agentId);
    const request: SendMessageRequest = {
      agentId,
      address: agent.node_id,
      sessionId,
      messages,
      system: `${agent.knowledge}\n\nRoutine: ${agent.routine}`,
    };
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify(request),
      signal, // 添加 abort signal 支持
    });
    if (!response.body) throw new Error('No response body for SSE');
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 1);
        if (line.startsWith('0:')) {
          // 文本增量或工具调用
          try {
            const payload = JSON.parse(line.slice(2));
            if (payload.type === 'text') {
              yield { type: 'text', text: payload.text };
            } else if (payload.type === 'tool-call') {
              yield { 
                type: 'tool-call', 
                toolCallId: payload.toolCallId,
                toolName: payload.toolName,
                args: payload.args
              };
            }
          } catch {}
        } else if (line.startsWith('d:')) {
          // 结束信号
          return;
        }
      }
    }
  },
}; 