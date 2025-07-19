import type { FC } from "react";
import {
  ThreadListItemPrimitive,
  ThreadListPrimitive,
} from "@assistant-ui/react";
import { ArchiveIcon, PlusIcon, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { AgentSelector } from "@/components/agent-selector";
import { AIAgent, ChatSession } from "@/lib/types";
import { sessionsApi } from "@/lib/api";
import { useState, useEffect } from "react";

interface ThreadListProps {
  onSessionCreated?: () => void;
  sessions?: ChatSession[];
  currentSession?: ChatSession | null;
  onSessionSelect?: (session: ChatSession | null) => void;
}

export const ThreadList: FC<ThreadListProps> = ({
  onSessionCreated,
  sessions = [],
  currentSession,
  onSessionSelect,
}) => {
  const [showAgentSelector, setShowAgentSelector] = useState(false);
  const [localSessions, setLocalSessions] = useState<ChatSession[]>(sessions);
  const [deletingSessions, setDeletingSessions] = useState<Set<string>>(new Set());
  
  // 同步外部sessions到本地状态
  useEffect(() => {
    setLocalSessions(sessions);
  }, [sessions]);

  const handleAgentSelect = async (agent: AIAgent) => {
    try {
      const newSession = await sessionsApi.createSession({
        agentId: agent.node_id,
        title: `Chat with ${agent.name}`,
      });
      setShowAgentSelector(false);
      // 立即选中新创建的session
      onSessionSelect?.(newSession);
      onSessionCreated?.();
    } catch (error) {
      console.error('Failed to create session:', error);
    }
  };

  const handleCancelAgentSelect = () => {
    setShowAgentSelector(false);
  };

  const handleSessionSelect = (session: ChatSession) => {
    onSessionSelect?.(session);
  };

  const handleDeleteSession = async (sessionId: string) => {
    // 乐观删除：立即从本地列表中移除
    setLocalSessions(prev => prev.filter(s => s.id !== sessionId));
    setDeletingSessions(prev => new Set(prev).add(sessionId));
    
    // 如果删除的是当前会话，清除选中状态
    if (currentSession && currentSession.id === sessionId && onSessionSelect) {
      onSessionSelect(null);
    }
    
    try {
      await sessionsApi.deleteSession(sessionId);
      // 成功删除后通知父组件刷新
      onSessionCreated?.();
    } catch (error) {
      console.error('Failed to delete session:', error);
      // 删除失败，恢复到列表中
      const deletedSession = sessions.find(s => s.id === sessionId);
      if (deletedSession) {
        setLocalSessions(prev => [...prev, deletedSession].sort((a, b) => 
          new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        ));
      }
      // 尝试刷新列表，可能是缓存问题
      onSessionCreated?.();
    } finally {
      setDeletingSessions(prev => {
        const newSet = new Set(prev);
        newSet.delete(sessionId);
        return newSet;
      });
    }
  };

  if (showAgentSelector) {
    return (
      <AgentSelector
        onAgentSelect={handleAgentSelect}
        onCancel={handleCancelAgentSelect}
      />
    );
  }

  return (
    <div className="flex flex-col items-stretch gap-1.5">
      <ThreadListNew onNewSession={() => setShowAgentSelector(true)} />
      <ThreadListItems
        sessions={localSessions}
        currentSession={currentSession}
        onSessionSelect={handleSessionSelect}
        onDeleteSession={handleDeleteSession}
        deletingSessions={deletingSessions}
      />
    </div>
  );
};

const ThreadListNew: FC<{ onNewSession: () => void }> = ({ onNewSession }) => {
  return (
    <Button
      className="data-[active]:bg-muted hover:bg-muted flex items-center justify-start gap-1 rounded-lg px-2.5 py-2 text-start"
      variant="ghost"
      onClick={onNewSession}
    >
      <PlusIcon />
      <Sparkles className="h-4 w-4" />
      New Chat
    </Button>
  );
};

interface ThreadListItemsProps {
  sessions: ChatSession[];
  currentSession?: ChatSession | null;
  onSessionSelect?: (session: ChatSession) => void;
  onDeleteSession?: (sessionId: string) => void;
}

const ThreadListItems: FC<ThreadListItemsProps> = ({
  sessions,
  currentSession,
  onSessionSelect,
  onDeleteSession,
}) => {
  if (sessions.length === 0) {
    return (
      <div className="px-3 py-4 text-center">
        <Sparkles className="h-8 w-8 text-blue-400 mx-auto mb-2" />
        <p className="text-sm text-gray-500">No conversations yet</p>
        <p className="text-xs text-gray-400 mt-1">Click the button above to start a new chat</p>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {sessions.map((session) => (
        <ThreadListItem
          key={session.id}
          session={session}
          isActive={currentSession?.id === session.id}
          onSelect={() => onSessionSelect?.(session)}
          onDelete={() => onDeleteSession?.(session.id)}
        />
      ))}
    </div>
  );
};

interface ThreadListItemProps {
  session: ChatSession;
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
}

const ThreadListItem: FC<ThreadListItemProps> = ({
  session,
  isActive,
  onSelect,
  onDelete,
}) => {
  return (
    <div
      className={`flex items-center gap-2 rounded-lg transition-all cursor-pointer ${
        isActive ? 'bg-muted' : 'hover:bg-muted'
      }`}
      onClick={onSelect}
    >
      <div className="flex-grow px-3 py-2 text-start min-w-0">
        <div className="flex items-center gap-2">
          <Sparkles className="h-3 w-3 text-blue-500 flex-shrink-0" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium truncate">{session.title}</p>
            <p className="text-xs text-gray-500 truncate">
              {session.agentName} • {session.messageCount} messages
            </p>
          </div>
        </div>
      </div>
      <TooltipIconButton
        className="hover:text-red-500 text-foreground ml-auto mr-3 size-4 p-0"
        variant="ghost"
        tooltip="Delete chat"
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
      >
        <ArchiveIcon />
      </TooltipIconButton>
    </div>
  );
};
