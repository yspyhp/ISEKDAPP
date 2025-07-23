import { makeAssistantTool, makeAssistantToolUI } from "@assistant-ui/react";
import { useState } from "react";

// 加载动画组件
const LoadingSpinner = () => {
  return (
    <div className="flex items-center gap-3 p-3">
      <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
      <span className="text-sm text-muted-foreground">正在思考...</span>
    </div>
  );
};

// 成员卡片组件
const MemberCard = ({ member }: { member: any }) => {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div
      className="relative"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="flex items-center gap-3 p-3 bg-background rounded-lg border hover:shadow-md transition-all duration-200 cursor-pointer">
        <div className="text-2xl">{member.avatar}</div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium truncate">{member.name}</div>
          <div className="text-xs text-muted-foreground">{member.role}</div>

        </div>
        <div className="w-2 h-2 bg-green-500 rounded-full"></div>
      </div>
      
      {/* Hover详情卡片 */}
      {isHovered && (
        <div className="absolute left-0 top-full mt-2 w-64 p-3 bg-white dark:bg-gray-800 border rounded-lg shadow-lg z-10">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xl">{member.avatar}</span>
            <div>
              <div className="font-medium text-sm">{member.name}</div>
              <div className="text-xs text-muted-foreground">{member.role}</div>
            </div>
          </div>
          <div className="text-xs text-muted-foreground mb-2">
            <strong>技能：</strong>{member.skill}
          </div>

          <div className="text-xs text-muted-foreground">
            {member.description}
          </div>
        </div>
      )}
    </div>
  );
};

// 简化的工具参数定义（不使用zod）
const teamFormationSchema = {
  type: "object" as const,
  properties: {
    task: { type: "string" as const, description: "任务名称" },
    requiredRoles: { type: "array" as const, items: { type: "string" as const }, description: "需要的角色列表" },
    status: { type: "string" as const, enum: ["starting", "recruiting", "completed"], description: "状态" },
    progress: { type: "number" as const, minimum: 0, maximum: 1, description: "进度" },
    currentStep: { type: "string" as const, description: "当前步骤" },
    members: { 
      type: "array" as const, 
      items: {
        type: "object" as const,
        properties: {
          name: { type: "string" as const },
          role: { type: "string" as const },
          skill: { type: "string" as const },

          avatar: { type: "string" as const },
          description: { type: "string" as const }
        }
      },
      description: "团队成员" 
    },
    teamStats: {
      type: "object" as const,
      properties: {
        totalMembers: { type: "number" as const },

        skills: { type: "array" as const, items: { type: "string" as const } }
      },
      description: "团队统计"
    }
  }
};

// 创建加载动画工具UI
export const LoadingSpinnerToolUI = makeAssistantToolUI({
  toolName: "loading-spinner",
  render: () => <LoadingSpinner />
});

// 创建工具UI
export const TeamFormationToolUI = makeAssistantToolUI({
  toolName: "team-formation",
  render: ({ args, status }) => {
    // 确保小队数据完整，修复团队规模显示问题
    const { task, progress = 0, currentStep = "", members = [], teamStats } = args || {};
    const toolStatus = args?.status || status?.type || "starting";
    
    // 确保members是数组且不为空
    const validMembers = Array.isArray(members) ? members : [];
    const memberCount = validMembers.length;
    
    // 调试信息
    console.log('🔍 TeamFormationToolUI Debug:', {
      args,
      members,
      validMembers,
      memberCount,
      teamStats,
      toolStatus
    });
    
    // 确保teamStats包含正确的数据
    const validTeamStats = teamStats || {
      totalMembers: memberCount,
      skills: ['AI图片创作', '数据分析', '智能问答', '流程编排']
    };

    return (
      <div className="w-full max-w-2xl mx-auto my-4 p-4 border rounded-lg bg-muted">
        {/* 标题区域 */}
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xl">🚀</span>
            <h3 className="text-lg font-semibold">{String(task || "AI项目开发小队")}</h3>
          </div>
          
          {/* 进度条 */}
          <div className="w-full bg-gray-200 rounded-full h-3 dark:bg-gray-700 mb-2">
            <div
              className="bg-gradient-to-r from-blue-500 to-green-500 h-3 rounded-full transition-all duration-500 ease-out"
              style={{ width: `${Math.round((progress as number || 0) * 100)}%` }}
            ></div>
          </div>
          
          <div className="flex justify-between items-center text-sm">
            <span className="text-muted-foreground">{String(currentStep || "")}</span>
            <span className="font-medium">{Math.round((progress as number || 0) * 100)}%</span>
          </div>
        </div>

        {/* 状态指示器 */}
        <div className="flex items-center gap-2 mb-4">
          {toolStatus === "recruiting" && (
            <>
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
              <span className="text-sm text-blue-600">正在招募中...</span>
            </>
          )}
          {toolStatus === "completed" && (
            <>
              <div className="w-2 h-2 bg-green-500 rounded-full"></div>
              <span className="text-sm text-green-600">组建完成</span>
            </>
          )}
        </div>

        {/* 小队成员列表 */}
        {validMembers.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-md font-medium flex items-center gap-2">
                <span>👥</span>
                小队成员 ({memberCount}人)
              </h4>
              {toolStatus === "recruiting" && (
                <div className="text-xs text-muted-foreground">
                  {`${memberCount}/4 已招募`}
                </div>
              )}
            </div>
            
            <div className="grid grid-cols-1 gap-2">
              {validMembers.map((member: any, idx: number) => (
                <MemberCard key={idx} member={member} />
              ))}
            </div>
          </div>
        )}

        {/* 小队统计（完成后显示） */}
        {toolStatus === "completed" && validTeamStats && (
          <div className="mt-4 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
            <div className="text-sm font-medium text-green-800 dark:text-green-200 mb-2">
              ✅ 小队组建成功！
            </div>
            <div className="text-xs text-green-700 dark:text-green-300">
              <div className="mb-2">
                <span className="font-medium">团队规模：</span>
                {memberCount}人
              </div>
              {(validTeamStats as any).skills && Array.isArray((validTeamStats as any).skills) && (validTeamStats as any).skills.length > 0 && (
                <div>
                  <span className="font-medium">核心技能：</span>
                  {(validTeamStats as any).skills.join("、")}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    );
  }
});

// 注册工具
export const TeamFormationTool = makeAssistantTool({
  toolName: "team-formation",
  description: "组建AI项目开发小队",
  parameters: teamFormationSchema,
  execute: async (args) => {
    // 这里是前端工具，实际执行由后端streaming提供
    return {
      success: true,
      message: "小队组建完成"
    };
  }
});