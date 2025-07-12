import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function shouldIgnoreError(error: unknown): boolean {
  return error instanceof Error && (error.name === 'AbortError' || error.message.includes('BodyStreamBuffer was aborted'));
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error);
}

// 清理过期的消息缓存
export function cleanupMessageCache(cache: Map<string, { messages: unknown[], timestamp: number }>, maxAge: number = 5 * 60 * 1000) {
  const now = Date.now();
  for (const [key, value] of cache.entries()) {
    if (now - value.timestamp > maxAge) {
      cache.delete(key);
    }
  }
}

// 获取缓存统计信息
export function getCacheStats(cache: Map<string, { messages: unknown[], timestamp: number }>) {
  return {
    size: cache.size,
    entries: Array.from(cache.entries()).map(([id, data]) => ({
      id,
      messageCount: data.messages.length,
      age: Date.now() - data.timestamp
    }))
  };
}
