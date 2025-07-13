"use client";

import { useState, useEffect } from "react";
import { SidebarProvider, SidebarInset } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";
import { agentsApi, sessionsApi } from "@/lib/api";
import { ChatSession, AIAgent } from "@/lib/types";
import { MyRuntimeProvider } from "./MyRuntimeProvider";
import { Thread } from "@/components/assistant-ui/thread";

export const Assistant = () => {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
  const [agents, setAgents] = useState<AIAgent[]>([]);

  useEffect(() => {
    sessionsApi.getSessions().then(setSessions);
    agentsApi.getAgents().then(setAgents);
  }, []);

  // 可选：新建/删除会话后刷新
  const handleSessionCreated = () => {
    sessionsApi.getSessions().then(setSessions);
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
        {currentSession && (
          <MyRuntimeProvider session={currentSession}>
            <Thread />
          </MyRuntimeProvider>
        )}
      </SidebarInset>
    </SidebarProvider>
  );
};

