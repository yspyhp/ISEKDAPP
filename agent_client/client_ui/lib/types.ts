// AI Agent type - simplified to match server adapter card
export interface AIAgent {
  name: string;
  node_id: string;
  bio: string;       // from adapter card - displayed as description
  lore: string;      // from adapter card
  knowledge: string; // from adapter card - displayed as capabilities tags
  routine: string;   // from adapter card
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
  address: string; // uses agent.node_id
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