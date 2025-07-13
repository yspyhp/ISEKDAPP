"use client";

import { useState, useEffect } from "react";
import { SidebarProvider, SidebarInset } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";
import { agentsApi, sessionsApi } from "@/lib/api";
import { ChatSession, AIAgent } from "@/lib/types";
import { MyRuntimeProvider } from "./MyRuntimeProvider";
import { Thread } from "@/components/assistant-ui/thread";
import { AgentSelector } from "@/components/agent-selector";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

export const Assistant = () => {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
  const [agents, setAgents] = useState<AIAgent[]>([]);
  const [showAgentSelector, setShowAgentSelector] = useState(false);

  useEffect(() => {
    sessionsApi.getSessions().then(setSessions);
    agentsApi.getAgents().then(setAgents);
  }, []);

  // 新建/删除会话后刷新
  const handleSessionCreated = () => {
    sessionsApi.getSessions().then(setSessions);
  };

  // 发送消息后刷新会话列表，保证侧边栏及时更新
  const handleMessageSent = () => {
    sessionsApi.getSessions().then(setSessions);
  };

  // 智能体选择后创建 session
  const handleAgentSelect = async (agent: AIAgent) => {
    try {
      const session = await sessionsApi.createSession({
        agentId: agent.id,
        title: `小队 - ${agent.name}`,
      });
      setShowAgentSelector(false);
      setCurrentSession(session);
      handleSessionCreated();
    } catch (error) {
      // 可加错误提示
    }
  };

  return (
    <SidebarProvider>
      <AppSidebar
        sessions={sessions}
        currentSession={currentSession}
        onSessionSelect={setCurrentSession}
        agents={agents}
        onSessionCreated={handleSessionCreated}
      />
      <SidebarInset>
        {currentSession ? (
          <MyRuntimeProvider session={currentSession} onMessageSent={handleMessageSent}>
            <Thread />
          </MyRuntimeProvider>
        ) : showAgentSelector ? (
          <div className="flex h-full items-center justify-center bg-background">
            <div className="w-full max-w-lg mx-auto">
              <AgentSelector
                onAgentSelect={handleAgentSelect}
                onCancel={() => setShowAgentSelector(false)}
              />
            </div>
          </div>
        ) : (
          <WelcomePage onCreateTeam={() => setShowAgentSelector(true)} />
        )}
      </SidebarInset>
    </SidebarProvider>
  );
};

// 欢迎页组件
const WelcomePage = ({ onCreateTeam }: { onCreateTeam: () => void }) => (
  <div className="flex flex-col items-center justify-center h-full bg-background text-center px-4">
    <div className="flex flex-col items-center gap-4">
      <Sparkles className="w-16 h-16 text-blue-500 mb-2 animate-bounce" />
      <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight mb-2">欢迎来到 ISEK 智能小队</h1>
      <p className="text-lg text-muted-foreground mb-6 max-w-xl">
        组建你的专属智能小队，选择多位智能体协作完成任务。点击下方按钮，立即创建属于你的智能小队！
      </p>
      <Button size="lg" className="px-8 py-3 text-lg font-semibold shadow-md" onClick={onCreateTeam}>
        选择智能体创建小队
      </Button>
    </div>
  </div>
);

