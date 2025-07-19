"use client";

import { AssistantRuntimeProvider, useExternalStoreRuntime, ThreadMessageLike, AppendMessage } from "@assistant-ui/react";
import { ReactNode, useEffect, useState } from "react";
import { chatApi, messagesApi } from "@/lib/api";
import { ChatSession } from "@/lib/types";
import { TeamFormationToolUI } from "@/components/assistant-ui/tool-ui";

// 工具调用更新函数
function updateToolCall(content: any[], newToolCall: any) {
  const existingIndex = content.findIndex(
    item => item.type === 'tool-call' && item.toolCallId === newToolCall.toolCallId
  );
  
  if (existingIndex >= 0) {
    // 更新现有工具调用
    const updatedContent = [...content];
    updatedContent[existingIndex] = newToolCall;
    return updatedContent;
  } else {
    // 添加新工具调用
    return [...content, newToolCall];
  }
}

export function MyRuntimeProvider({
  session,
  children,
  onMessageSent,
}: {
  session: ChatSession;
  children: ReactNode;
  onMessageSent?: () => void;
}) {
  const [messages, setMessages] = useState<ThreadMessageLike[]>([]);
  const [loading, setLoading] = useState(true);

  // 拉取历史消息，适配后端格式
  useEffect(() => {
    if (!session?.id) return;
    setLoading(true);
    messagesApi.getMessages(session.id).then(rawMsgs => {
      setMessages(
        rawMsgs.map(msg => {
          if (msg.role === "assistant") {
            // 直接使用后端返回的 content 分段数组
            let parts: any[] = [];
            const contentAny = msg.content as any;
            
            if (Array.isArray(contentAny)) {
              // 处理content数组中的每个part
              parts = contentAny.map(part => {
                // 确保ui_component类型被正确处理
                if (part.type === "ui_component") {
                  return part; // 保持原样传递
                }
                return part;
              });
            } else if (typeof contentAny === "object" && contentAny !== null) {
              if (typeof contentAny.text === "string") {
                parts.push({ type: "text", text: contentAny.text });
              }
              if (Array.isArray(contentAny.tool_calls)) {
                for (const toolCall of contentAny.tool_calls) {
                  parts.push({ 
                    type: "tool-call", 
                    toolCallId: toolCall.id,
                    toolName: toolCall.function?.name || toolCall.name,
                    args: toolCall.function?.arguments || toolCall.arguments,
                    argsText: typeof (toolCall.function?.arguments || toolCall.arguments) === 'string' 
                      ? (toolCall.function?.arguments || toolCall.arguments)
                      : JSON.stringify(toolCall.function?.arguments || toolCall.arguments, null, 2)
                  });
                }
              }
            } else if (typeof contentAny === "string") {
              parts = [{ type: "text", text: contentAny }];
            }
            // 新增：处理tool字段
            const tool = (msg as any).tool;
            if (tool && typeof tool === "object") {
              // 合并tool的所有数据作为args
              const toolArgs = {
                ...tool.input,
                status: tool.status,
                progress: tool.progress || 0,
                currentStep: tool.currentStep || "",
                members: tool.members || []
              };
              parts.push({
                type: "tool-call",
                toolName: tool.type,
                args: toolArgs,
                argsText: JSON.stringify(toolArgs, null, 2)
              });
            }
            return {
              role: msg.role,
              content: parts,
              id: msg.id,
            };
          } else {
            // user消息保持原样
            return {
              role: msg.role,
              content: [{ type: "text", text: String(msg.content) }],
              id: msg.id,
            };
          }
        })
      );
      setLoading(false);
    });
  }, [session?.id]);

  // 发送新消息，严格按后端要求发送完整历史+新消息
  const onNew = async (message: AppendMessage) => {
    try {
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
        aiMsg = { ...aiMsg, content: [{ type: "text", text: aiText }, ...(Array.isArray(aiMsg.content) ? aiMsg.content.filter(p => p.type !== 'text') : [])] };
        setMessages(msgs => {
          const idx = [...msgs].reverse().findIndex(m => m.role === "assistant" && !m.id);
          if (idx !== -1) {
            const msgsCopy = [...msgs];
            msgsCopy[msgs.length - 1 - idx] = aiMsg;
            return msgsCopy;
          }
          return msgs;
        });
      } else if (chunk.type === "function_call") {
        // 转换function_call为tool-call格式
        const functionCallChunk = chunk as any; // 类型断言以访问属性
        const toolCallPart = {
          type: "tool-call",
          toolCallId: functionCallChunk.id,
          toolName: functionCallChunk.name,
          args: functionCallChunk.arguments,
          argsText: typeof functionCallChunk.arguments === 'string' ? functionCallChunk.arguments : JSON.stringify(functionCallChunk.arguments, null, 2)
        };
        aiMsg = { ...aiMsg, content: [...(Array.isArray(aiMsg.content) ? aiMsg.content : []), toolCallPart] };
        setMessages(msgs => {
          const idx = [...msgs].reverse().findIndex(m => m.role === "assistant" && !m.id);
          if (idx !== -1) {
            const msgsCopy = [...msgs];
            msgsCopy[msgs.length - 1 - idx] = aiMsg;
            return msgsCopy;
          }
          return msgs;
        });
      } else if (chunk.type === "tool-call") {
        // 处理工具调用流式更新
        const toolCallChunk = {
          ...chunk,
          argsText: typeof chunk.args === 'string' ? chunk.args : JSON.stringify(chunk.args, null, 2)
        };
        aiMsg = { ...aiMsg, content: updateToolCall(Array.isArray(aiMsg.content) ? aiMsg.content : [], toolCallChunk) };
        setMessages(msgs => {
          const idx = [...msgs].reverse().findIndex(m => m.role === "assistant" && !m.id);
          if (idx !== -1) {
            const msgsCopy = [...msgs];
            msgsCopy[msgs.length - 1 - idx] = aiMsg;
            return msgsCopy;
          }
          return msgs;
        });
      } else {
        // 遇到未知/不支持的类型，跳过并警告
        console.warn('Unsupported assistant message part type:', chunk.type, chunk);
        continue;
      }
    }
    } catch (error) {
      console.error('发送消息错误:', error);
      // 显示错误消息
      const errorMsg: ThreadMessageLike = { 
        role: "assistant", 
        content: [{ 
          type: "text", 
          text: `发送消息时出现错误: ${error instanceof Error ? error.message : String(error)}` 
        }] 
      };
      setMessages(msgs => [...msgs, errorMsg]);
    } finally {
      // 消息发送后通知父组件刷新 sessions
      if (onMessageSent) onMessageSent();
    }
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
      <TeamFormationToolUI />
      {children}
    </AssistantRuntimeProvider>
  );
} 