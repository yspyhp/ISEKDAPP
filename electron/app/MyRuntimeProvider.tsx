"use client";

import { AssistantRuntimeProvider, useExternalStoreRuntime, ThreadMessageLike, AppendMessage } from "@assistant-ui/react";
import { ReactNode, useEffect, useState } from "react";
import { chatApi, messagesApi } from "@/lib/api";
import { ChatSession } from "@/lib/types";

export function MyRuntimeProvider({
  session,
  children,
}: {
  session: ChatSession;
  children: ReactNode;
}) {
  const [messages, setMessages] = useState<ThreadMessageLike[]>([]);
  const [loading, setLoading] = useState(true);

  // 拉取历史消息，适配后端格式
  useEffect(() => {
    if (!session?.id) return;
    setLoading(true);
    messagesApi.getMessages(session.id).then(rawMsgs => {
      setMessages(
        rawMsgs.map(msg => ({
          role: msg.role,
          content: [{ type: "text", text: String(msg.content) }],
          id: msg.id,
        }))
      );
      setLoading(false);
    });
  }, [session?.id]);

  // 发送新消息，严格按后端要求发送完整历史+新消息
  const onNew = async (message: AppendMessage) => {
    const userText = message.content[0]?.type === "text" ? message.content[0].text : "";
    // 构造历史消息，确保 content 为字符串
    const history = messages.map(m => ({
      role: m.role,
      content: (m.content && m.content[0] && typeof m.content[0] === "object" && "text" in m.content[0]) ? m.content[0].text : "",
    }));
    const newUserMsg = { role: "user", content: userText };
    const allMessages = [...history, newUserMsg] as any; // 断言为 any 以兼容 ChatMessage[]

    // 本地展示用户消息
    setMessages(msgs => [...msgs, { role: "user", content: [{ type: "text", text: userText }] }]);

    // 流式展示 AI 回复
    let aiText = "";
    let aiMsg: ThreadMessageLike = { role: "assistant", content: [] };
    setMessages(msgs => [...msgs, aiMsg]);
    for await (const chunk of chatApi.sendMessageStream(
      userText,
      session.id,
      session.agentId,
      allMessages // 发送完整历史+新消息
    )) {
      if (chunk.type === "text") {
        aiText += chunk.text;
        aiMsg = { ...aiMsg, content: [{ type: "text", text: aiText }] };
        setMessages(msgs => {
          const idx = [...msgs].reverse().findIndex(m => m.role === "assistant" && !m.id);
          if (idx !== -1) {
            const realIdx = msgs.length - 1 - idx;
            const newMsgs = [...msgs];
            newMsgs[realIdx] = aiMsg;
            return newMsgs;
          }
          return msgs;
        });
      }
    }
    // 不需要本地保存，后端已自动处理
  };

  const runtime = useExternalStoreRuntime<ThreadMessageLike>({
    messages,
    setMessages,
    onNew,
    convertMessage: (msg: any) => msg,
  });

  if (loading) {
    return <div className="flex items-center justify-center h-full">Loading...</div>;
  }

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  );
} 