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
      address: agent.address,
      sessionId,
      messages,
      system: agent.systemPrompt,
    };

    return this.sendMessage(request);
  },
}; 