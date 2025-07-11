"use client";

import { useState, useEffect, useMemo } from "react";
import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { useChatRuntime } from "@assistant-ui/react-ai-sdk";
import { Session } from "@/components/assistant-ui/session";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";
import { Separator } from "@/components/ui/separator";
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import { AIAgent, ChatSession, ChatMessage } from "@/lib/types";
import { agentsApi, sessionsApi, messagesApi } from "@/lib/api";
import { Sparkles } from "lucide-react";

// 工具函数：归一化消息 content 字段为字符串
function normalizeMessageContent(msg: { content: string | Array<{ text: string }> }) {
  if (Array.isArray(msg.content)) {
    return msg.content.map((c: { text: string }) => c.text).join('');
  }
  return msg.content;
}

// 包装 body，确保 outgoing messages 的 content 是字符串
function normalizeOutgoingBody(body: { messages?: Array<{ content: string | Array<{ text: string }> }> }) {
  if (Array.isArray(body.messages)) {
    return {
      ...body,
      messages: body.messages.map((msg: { content: string | Array<{ text: string }> }) => ({ ...msg, content: normalizeMessageContent(msg) }))
    };
  }
  return body;
}

// 为特定会话创建 runtime 的组件
const SessionRuntime: React.FC<{ session: ChatSession }> = ({ session }) => {
  const [initialMessages, setInitialMessages] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // 加载会话的初始消息
  useEffect(() => {
    const loadInitialMessages = async () => {
      try {
        console.log('🔄 Loading initial messages for session:', session.id);
        setLoading(true);
        
        const response = await fetch(`/api/chat?sessionId=${session.id}`);
        if (!response.ok) {
          console.error('Failed to load initial messages:', response.status);
          setInitialMessages([]);
          return;
        }
        
        const messages = await response.json();
        console.log('✅ Loaded', messages.length, 'initial messages for session:', session.id);
        
        const normalizedMessages = messages.map((msg: any) => ({
          id: msg.id,
          role: msg.role,
          content: normalizeMessageContent(msg),
          name: msg.role === 'assistant' ? session.agentName : 'User'
        }));
        
        setInitialMessages(normalizedMessages);
      } catch (error) {
        console.error('❌ Failed to load initial messages:', error);
        setInitialMessages([]);
      } finally {
        setLoading(false);
      }
    };

    loadInitialMessages();
  }, [session.id, session.agentName]);

  // 创建 runtime
  const runtime = useChatRuntime({
    api: "/api/chat",
    initialMessages: initialMessages,
    body: {
      sessionId: session.id,
      agentId: session.agentId,
      system: session.agentDescription
    },
    headers: {
      'Accept': 'text/event-stream',
      'Content-Type': 'application/json'
    },
    // 确保消息内容被正确格式化
    onFinish: (message) => {
      console.log('✅ Message finished:', message);
    },
    onError: (error) => {
      console.error('❌ Chat error:', error);
    }
  });

  console.log('🎯 SessionRuntime: Rendering for session:', session.id, session.title, 'with', initialMessages.length, 'messages');
  console.log('🎯 Session agentId:', session.agentId, 'agentName:', session.agentName);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-2"></div>
          <p className="text-sm text-gray-500">Loading messages...</p>
        </div>
      </div>
    );
  }

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <Session key={`${session.id}-${initialMessages.length}`} currentSession={session} />
    </AssistantRuntimeProvider>
  );
};

export const Assistant = () => {
  const [agents, setAgents] = useState<AIAgent[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load agents and sessions
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const [agentsList, sessionsList] = await Promise.all([
        agentsApi.getAgents(),
        sessionsApi.getSessions()
      ]);
      
      setAgents(agentsList);
      setSessions(sessionsList);
      
      // If there are sessions, select the first one as current session
      if (sessionsList.length > 0) {
        setCurrentSession(sessionsList[0]);
      } else {
        setCurrentSession(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleSessionCreated = async () => {
    try {
      const sessionsList = await sessionsApi.getSessions();
      setSessions(sessionsList);
      
      if (sessionsList.length > 0) {
        setCurrentSession(sessionsList[sessionsList.length - 1]);
      }
    } catch (err) {
      console.error('Failed to refresh sessions:', err);
    }
  };

  const handleSessionSelect = (session: ChatSession | null) => {
    console.log('🔄 Assistant: Selecting session:', session?.id, session?.title);
    setCurrentSession(session);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-500">Loading...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <p className="text-red-500 mb-4">{error}</p>
          <button 
            onClick={loadData}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Only render chat interface when there is a current session
  if (!currentSession) {
    return (
      <SidebarProvider>
        <AppSidebar 
          agents={agents}
          sessions={sessions}
          currentSession={currentSession}
          onSessionSelect={handleSessionSelect}
          onSessionCreated={handleSessionCreated}
        />
        <SidebarInset>
          <header className="flex h-16 shrink-0 items-center gap-2 border-b px-4">
            <SidebarTrigger />
            <Separator orientation="vertical" className="mr-2 h-4" />
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem className="hidden md:block">
                  <BreadcrumbLink href="#">
                    <div className="flex items-center gap-2">
                      <Sparkles className="h-4 w-4" />
                      ISEK UI
                    </div>
                  </BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator className="hidden md:block" />
                <BreadcrumbItem>
                  <BreadcrumbPage>
                    Select an agent to start a conversation
                  </BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </header>
          <div className="flex items-center justify-center h-[calc(100vh-4rem)]">
            <div className="text-center">
              <Sparkles className="h-16 w-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-semibold mb-2">Welcome to ISEK UI</h3>
              <p className="text-gray-500 mb-4">Select an agent to start a new conversation</p>
            </div>
          </div>
        </SidebarInset>
      </SidebarProvider>
    );
  }

  return (
      <SidebarProvider>
        <AppSidebar 
          agents={agents}
        sessions={sessions}
        currentSession={currentSession}
        onSessionSelect={handleSessionSelect}
        onSessionCreated={handleSessionCreated}
        />
        <SidebarInset>
          <header className="flex h-16 shrink-0 items-center gap-2 border-b px-4">
            <SidebarTrigger />
            <Separator orientation="vertical" className="mr-2 h-4" />
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem className="hidden md:block">
                  <BreadcrumbLink href="#">
                    <div className="flex items-center gap-2">
                      <Sparkles className="h-4 w-4" />
                      ISEK UI
                    </div>
                  </BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator className="hidden md:block" />
                <BreadcrumbItem>
                  <BreadcrumbPage>
                    <div className="flex items-center gap-2">
                    <span>{currentSession.agentName}</span>
                      <span className="text-gray-400">-</span>
                    <span>{currentSession.title}</span>
                    </div>
                  </BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
          </header>
        <SessionRuntime key={currentSession.id} session={currentSession} />
        </SidebarInset>
      </SidebarProvider>
  );
};
