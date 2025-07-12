"use client";

import { useState, useEffect, useMemo } from "react";
import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { useChatRuntime } from "@assistant-ui/react-ai-sdk";
import { Session } from "@/components/assistant-ui/session";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";
import { Separator } from "@/components/ui/separator";
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import { AIAgent, ChatSession } from "@/lib/types";
import { agentsApi, sessionsApi } from "@/lib/api";
import { Sparkles } from "lucide-react";
import { shouldIgnoreError, getErrorMessage, cleanupMessageCache } from "@/lib/utils";

// 工具函数：归一化消息 content 字段为字符串
function normalizeMessageContent(msg: { content: string | Array<{ text: string }> }) {
  if (Array.isArray(msg.content)) {
    return msg.content.map((c: { text: string }) => c.text).join('');
  }
  return msg.content;
}

// 消息缓存
const messageCache = new Map<string, { messages: unknown[], timestamp: number }>();
const CACHE_DURATION = 5 * 60 * 1000; // 5分钟缓存

// 为特定会话创建 runtime 的组件
const SessionRuntime: React.FC<{ session: ChatSession; onMessageUpdate?: () => void }> = ({ session, onMessageUpdate }) => {
  const [initialMessages, setInitialMessages] = useState<any[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 检查缓存
  const cachedData = useMemo(() => {
    const cached = messageCache.get(session.id);
    console.log('🔧 Cache check for session:', session.id, {
      hasCache: !!cached,
      cacheAge: cached ? Date.now() - cached.timestamp : null,
      cacheValid: cached && Date.now() - cached.timestamp < CACHE_DURATION,
      messageCount: cached?.messages.length || 0
    });
    
    if (cached && Date.now() - cached.timestamp < CACHE_DURATION) {
      console.log('🔧 Using cached messages for session:', session.id);
      return cached.messages;
    }
    console.log('🔧 No valid cache for session:', session.id);
    return null;
  }, [session.id]);

  // 加载会话的初始消息
  useEffect(() => {
    let cancelled = false;
    
    const loadInitialMessages = async () => {
      try {
        // 如果有缓存，直接使用
        if (cachedData) {
          setInitialMessages(cachedData);
          setLoading(false);
          return;
        }

        setLoading(true);
        setError(null);
        
        const response = await fetch(`/api/chat?sessionId=${session.id}`);
        if (!response.ok) {
          setError(`Failed to load messages (${response.status})`);
          setInitialMessages([]);
          return;
        }
        
        const messages = await response.json();
        console.log('🔧 Raw messages from API:', messages);
        
        const normalizedMessages = messages.map((msg: any) => ({
          id: msg.id,
          role: msg.role,
          content: normalizeMessageContent(msg),
          name: msg.role === 'assistant' ? session.agentName : 'User',
          timestamp: msg.timestamp
        }));

        console.log('🔧 Normalized messages:', normalizedMessages);

        if (!cancelled) {
          setInitialMessages(normalizedMessages);
          // 缓存消息
          messageCache.set(session.id, {
            messages: normalizedMessages,
            timestamp: Date.now()
          });
          console.log('🔧 Cached messages for session:', session.id, {
            messageCount: normalizedMessages.length,
            timestamp: Date.now()
          });
        }
      } catch (error) {
        if (!cancelled) {
          setError('Failed to load messages');
          setInitialMessages([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    loadInitialMessages();
    return () => { cancelled = true; };
  }, [session.id, session.agentName, session.updatedAt, cachedData]);

  // 显示加载状态
  if (loading && !cachedData) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-2"></div>
          <p className="text-sm text-gray-500">Loading messages...</p>
        </div>
      </div>
    );
  }

  // 显示错误状态
  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="text-red-500 mb-4">
            <svg className="w-8 h-8 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
            <p className="text-sm">{error}</p>
          </div>
          <button 
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 text-sm"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // 只有在initialMessages准备好时才渲染ChatRuntime组件
  if (!initialMessages) {
    return <div className="text-gray-500">没有找到历史消息</div>;
  }

  // 使用key属性强制重新创建组件，确保runtime在initialMessages准备好时初始化
  return (
    <ChatRuntime 
      key={`${session.id}-${initialMessages.length}`} 
      session={session} 
      initialMessages={initialMessages} 
      onMessageUpdate={onMessageUpdate}
    />
  );
};

// 专门负责渲染runtime的组件，只在initialMessages准备好时才创建
const ChatRuntime: React.FC<{ session: ChatSession; initialMessages: any[]; onMessageUpdate?: () => void }> = ({ 
  session, 
  initialMessages,
  onMessageUpdate
}) => {
  console.log('🔧 ChatRuntime: Creating runtime with messages count:', initialMessages.length);

  const runtime = useChatRuntime({
    api: "/api/chat",
    initialMessages, // 直接传递准备好的消息
    body: {
      sessionId: session.id,
      agentId: session.agentId,
      system: session.agentDescription
    },
    headers: {
      'Accept': 'text/event-stream',
      'Content-Type': 'application/json'
    },
    onFinish: (message) => {
      console.log('✅ Message finished:', message);
      // 更新缓存中的消息
      const cached = messageCache.get(session.id);
      if (cached) {
        cached.messages.push(message);
        cached.timestamp = Date.now();
      }
      // 通知父组件更新会话列表
      onMessageUpdate?.();
    },
    onError: (error) => {
      if (shouldIgnoreError(error)) {
        console.log('🔄 Chat request aborted for session:', session.id);
        return;
      }
      console.error('❌ Chat error:', getErrorMessage(error));
    }
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <Session currentSession={session} />
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

  // 专门用于更新会话列表的函数，更高效
  const updateSessionsList = async () => {
    try {
      const sessionsList = await sessionsApi.getSessions();
      setSessions(sessionsList);
      
      // 更新当前会话的信息
      if (currentSession) {
        const updatedCurrentSession = sessionsList.find(s => s.id === currentSession.id);
        if (updatedCurrentSession) {
          setCurrentSession(updatedCurrentSession);
        }
      }
    } catch (err) {
      console.error('Failed to update sessions list:', err);
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

  // 预加载其他会话的消息（在后台进行）
  useEffect(() => {
    if (sessions.length > 0) {
      sessions.forEach(session => {
        if (session.id !== currentSession?.id && !messageCache.has(session.id)) {
          // 预加载消息到缓存
          fetch(`/api/chat?sessionId=${session.id}`)
            .then(response => response.json())
            .then(messages => {
              const normalizedMessages = messages.map((msg: any) => ({
                id: msg.id,
                role: msg.role,
                content: normalizeMessageContent(msg),
                name: msg.role === 'assistant' ? session.agentName : 'User',
                timestamp: msg.timestamp
              }));
              messageCache.set(session.id, {
                messages: normalizedMessages,
                timestamp: Date.now()
              });
            })
            .catch(() => {
              // 静默失败，不影响用户体验
            });
        }
      });
    }
  }, [sessions, currentSession?.id]);

  // 定期清理过期缓存
  useEffect(() => {
    const cleanupInterval = setInterval(() => {
      cleanupMessageCache(messageCache);
    }, 60000); // 每分钟清理一次

    return () => clearInterval(cleanupInterval);
  }, []);

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
          {/* 主内容区加 padding，避免悬浮按钮遮挡 */}
          <div className="pb-24 pl-6 h-full">
            <SessionRuntime key={currentSession.id} session={currentSession} onMessageUpdate={updateSessionsList} />
          </div>
        </SidebarInset>
      </SidebarProvider>
  );
};

