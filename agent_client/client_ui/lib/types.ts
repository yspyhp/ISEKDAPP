// AI Agent type
export interface AIAgent {
  id: string;
  name: string;
  description: string;
  systemPrompt: string;
  model: string;
  address: string;
  isek_id: string;
  capabilities: string[];
  status: 'online' | 'offline';
  network: string;
}

// Chat session type
export interface ChatSession {
  id: string;
  title: string;
  agentId: string;
  agentName: string;
  agentDescription: string;
  agentAddress: string;
  createdAt: string;
  updatedAt: string;
  messageCount?: number;
}

// Chat message type
export interface ChatMessage {
  id: string;
  sessionId: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: string;
}

// Create session request
export interface CreateSessionRequest {
  agentId: string;
  title?: string;
}

// Send message request
export interface SendMessageRequest {
  agentId: string;
  address: string;
  sessionId: string;
  messages: ChatMessage[];
  system?: string;
}

// Chat response
export interface ChatResponse {
  userMessage: ChatMessage;
  aiMessage: ChatMessage;
  agent: AIAgent;
}

// Network status
export interface NetworkStatus {
  connected: boolean;
  node_url: string;
  discovery_url: string;
  agents_count: number;
  timestamp: string;
} 