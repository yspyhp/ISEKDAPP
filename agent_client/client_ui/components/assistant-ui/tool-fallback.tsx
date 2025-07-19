import { ToolCallContentPartComponent } from "@assistant-ui/react";
import { CheckIcon, ChevronDownIcon, ChevronUpIcon } from "lucide-react";
import { useState } from "react";
import { Button } from "../ui/button";

export const ToolFallback: ToolCallContentPartComponent = ({
  toolName,
  argsText,
  result,
  status,
  ...props
}) => {
  const [isCollapsed, setIsCollapsed] = useState(true);
  
  
  return (
    <div className="mb-4 flex w-full flex-col gap-3 rounded-lg border py-3 bg-muted">
      <div className="flex items-center gap-2 px-4">
        <CheckIcon className="size-4 text-green-600" />
        <p className="">
          工具调用: <b>{toolName}</b>
        </p>
        {status && (
          <span className={`text-xs px-2 py-1 rounded ${
            status.type === 'running' ? 'bg-blue-100 text-blue-800' :
            status.type === 'complete' ? 'bg-green-100 text-green-800' :
            'bg-gray-100 text-gray-800'
          }`}>
            {status.type === 'running' ? '执行中' : 
             status.type === 'complete' ? '已完成' : 
             status.type}
          </span>
        )}
        <div className="flex-grow" />
        <Button 
          onClick={() => setIsCollapsed(!isCollapsed)}
          variant="ghost"
          size="sm"
        >
          {isCollapsed ? <ChevronDownIcon className="size-4" /> : <ChevronUpIcon className="size-4" />}
        </Button>
      </div>
      {!isCollapsed && (
        <div className="flex flex-col gap-2 border-t pt-2">
          <div className="px-4">
            <p className="text-sm font-medium mb-1">参数:</p>
            <pre className="text-xs bg-gray-100 p-2 rounded whitespace-pre-wrap">{argsText}</pre>
          </div>
          {result !== undefined && (
            <div className="border-t border-dashed px-4 pt-2">
              <p className="text-sm font-medium mb-1">结果:</p>
              <pre className="text-xs bg-gray-100 p-2 rounded whitespace-pre-wrap">
                {typeof result === "string"
                  ? result
                  : JSON.stringify(result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
