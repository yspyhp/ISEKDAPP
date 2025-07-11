import { FC, useState } from 'react';
import { MessageSquare, Sparkles, ArchiveIcon, PlusIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { TooltipIconButton } from '@/components/assistant-ui/tooltip-icon-button';
import { AgentSelector } from '@/components/agent-selector';
import { AIAgent, ChatSession } from '@/lib/types';
import { sessionsApi } from '@/lib/api';

interface SessionListProps {
  onSessionCreated?: () => void;
  sessions?: ChatSession[];
  currentSession?: ChatSession | null;
  onSessionSelect?: (session: ChatSession | null) => void;
}

export const SessionList: FC<SessionListProps> = ({ 
  onSessionCreated, 
  sessions = [], 
  currentSession,
  onSessionSelect 
}) => {
  const [showAgentSelector, setShowAgentSelector] = useState(false);


  const handleAgentSelect = async (agent: AIAgent) => {
    try {
      await sessionsApi.createSession({
        agentId: agent.id,
        title: `Chat with ${agent.name}`,
      });
      setShowAgentSelector(false);
      onSessionCreated?.();
    } catch (error) {
      console.error('Failed to create session:', error);
      // You can add error notifications here
    }
  };

  const handleCancelAgentSelect = () => {
    setShowAgentSelector(false);
  };

  const handleSessionSelect = (session: ChatSession) => {
    onSessionSelect?.(session);
  };

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await sessionsApi.deleteSession(sessionId);
      onSessionCreated?.(); // Refresh session list
      if (currentSession && currentSession.id === sessionId && onSessionSelect) {
        onSessionSelect(null);
      }
    } catch (error) {
      console.error('Failed to delete session:', error);
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
      <SessionListNew onNewSession={() => setShowAgentSelector(true)} />
      <SessionListItems 
        sessions={sessions}
        currentSession={currentSession}
        onSessionSelect={handleSessionSelect}
        onDeleteSession={handleDeleteSession}
      />
    </div>
  );
};

const SessionListNew: FC<{ onNewSession: () => void }> = ({ onNewSession }) => {
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

interface SessionListItemsProps {
  sessions: ChatSession[];
  currentSession?: ChatSession | null;
  onSessionSelect?: (session: ChatSession) => void;
  onDeleteSession?: (sessionId: string) => void;
}

const SessionListItems: FC<SessionListItemsProps> = ({ 
  sessions, 
  currentSession, 
  onSessionSelect,
  onDeleteSession 
}) => {
  if (sessions.length === 0) {
    return (
      <div className="px-3 py-4 text-center">
        <MessageSquare className="h-8 w-8 text-gray-400 mx-auto mb-2" />
        <p className="text-sm text-gray-500">No conversations yet</p>
        <p className="text-xs text-gray-400 mt-1">Click the button above to start a new chat</p>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {sessions.map((session) => (
        <SessionListItem
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

interface SessionListItemProps {
  session: ChatSession;
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
}

const SessionListItem: FC<SessionListItemProps> = ({ 
  session, 
  isActive, 
  onSelect, 
  onDelete 
}) => {
  return (
    <div 
      className={`flex items-center gap-2 rounded-lg transition-all cursor-pointer ${
        isActive 
          ? 'bg-muted' 
          : 'hover:bg-muted'
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
