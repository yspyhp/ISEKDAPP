import * as React from "react"
import { Sparkles } from "lucide-react"
import Link from "next/link"
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import { SessionList } from "./assistant-ui/session-list"
import { AIAgent, ChatSession } from "@/lib/types"

interface AppSidebarProps extends React.ComponentProps<typeof Sidebar> {
  agents?: AIAgent[];
  sessions?: ChatSession[];
  currentSession?: ChatSession | null;
  onSessionSelect?: (session: ChatSession) => void;
  onSessionCreated?: () => void;
}

export function AppSidebar({ 
  agents = [], 
  sessions = [], 
  currentSession, 
  onSessionSelect, 
  onSessionCreated,
  ...props 
}: AppSidebarProps) {
  return (
    <Sidebar {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
                <Link href="#" onClick={(e) => e.preventDefault()}>
                  <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                    <Sparkles className="size-4" />
                  </div>
                  <div className="flex flex-col gap-0.5 leading-none">
                    <span className="font-semibold">ISEK UI</span>
                    <span className="text-xs">P2P Multi-Agent</span>
                  </div>
                </Link>
              </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <SessionList 
          sessions={sessions}
          currentSession={currentSession}
          onSessionSelect={onSessionSelect}
          onSessionCreated={onSessionCreated}
        />
      </SidebarContent>
    </Sidebar>
  )
}
