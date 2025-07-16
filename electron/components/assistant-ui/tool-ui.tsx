import { makeAssistantTool, makeAssistantToolUI } from "@assistant-ui/react";
import { useState } from "react";

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
          <div className="text-xs text-blue-600">{member.experience}</div>
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
          <div className="text-xs text-muted-foreground mb-2">
            <strong>经验：</strong>{member.experience}
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
  type: "object",
  properties: {
    task: { type: "string", description: "任务名称" },
    requiredRoles: { type: "array", items: { type: "string" }, description: "需要的角色列表" },
    status: { type: "string", enum: ["starting", "recruiting", "completed"], description: "状态" },
    progress: { type: "number", minimum: 0, maximum: 1, description: "进度" },
    currentStep: { type: "string", description: "当前步骤" },
    members: { 
      type: "array", 
      items: {
        type: "object",
        properties: {
          name: { type: "string" },
          role: { type: "string" },
          skill: { type: "string" },
          experience: { type: "string" },
          avatar: { type: "string" },
          description: { type: "string" }
        }
      },
      description: "团队成员" 
    },
    teamStats: {
      type: "object",
      properties: {
        totalMembers: { type: "number" },
        avgExperience: { type: "string" },
        skills: { type: "array", items: { type: "string" } }
      },
      description: "团队统计"
    }
  }
};

// 创建工具UI
export const TeamFormationToolUI = makeAssistantToolUI({
  toolName: "team-formation",
  render: ({ args, status }) => {
    const { task, progress = 0, currentStep = "", members = [], teamStats } = args || {};
    const toolStatus = args?.status || status?.type || "starting";

    return (
      <div className="w-full max-w-2xl mx-auto my-4 p-4 border rounded-lg bg-muted">
        {/* 标题区域 */}
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xl">🚀</span>
            <h3 className="text-lg font-semibold">{task || "AI项目开发小队"}</h3>
          </div>
          
          {/* 进度条 */}
          <div className="w-full bg-gray-200 rounded-full h-3 dark:bg-gray-700 mb-2">
            <div
              className="bg-gradient-to-r from-blue-500 to-green-500 h-3 rounded-full transition-all duration-500 ease-out"
              style={{ width: `${Math.round(progress * 100)}%` }}
            ></div>
          </div>
          
          <div className="flex justify-between items-center text-sm">
            <span className="text-muted-foreground">{currentStep}</span>
            <span className="font-medium">{Math.round(progress * 100)}%</span>
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
        {members && members.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-md font-medium flex items-center gap-2">
                <span>👥</span>
                小队成员 ({members.length}人)
              </h4>
              {toolStatus === "recruiting" && (
                <div className="text-xs text-muted-foreground">
                  {`${members.length}/4 已招募`}
                </div>
              )}
            </div>
            
            <div className="grid grid-cols-1 gap-2">
              {members.map((member: any, idx: number) => (
                <MemberCard key={idx} member={member} />
              ))}
            </div>
          </div>
        )}

        {/* 小队统计（完成后显示） */}
        {toolStatus === "completed" && teamStats && (
          <div className="mt-4 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
            <div className="text-sm font-medium text-green-800 dark:text-green-200 mb-2">
              ✅ 小队组建成功！
            </div>
            <div className="grid grid-cols-2 gap-4 text-xs text-green-700 dark:text-green-300">
              <div>
                <span className="font-medium">团队规模：</span>
                {teamStats.totalMembers}人
              </div>
              <div>
                <span className="font-medium">平均经验：</span>
                {teamStats.avgExperience}
              </div>
            </div>
            <div className="mt-2 text-xs text-green-700 dark:text-green-300">
              <span className="font-medium">核心技能：</span>
              {teamStats.skills.join("、")}
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