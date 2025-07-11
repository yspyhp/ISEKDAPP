'use client';

import { useState, useEffect } from 'react';
import { AIAgent } from '@/lib/types';
import { agentsApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { Search, Sparkles, User } from 'lucide-react';

interface AgentSelectorProps {
  onAgentSelect: (agent: AIAgent) => void;
  onCancel: () => void;
}

export function AgentSelector({ onAgentSelect, onCancel }: AgentSelectorProps) {
  const [agents, setAgents] = useState<AIAgent[]>([]);
  const [filteredAgents, setFilteredAgents] = useState<AIAgent[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAgents();
  }, []);

  useEffect(() => {
    if (searchTerm.trim() === '') {
      setFilteredAgents(agents);
    } else {
      const filtered = agents.filter(agent =>
        agent.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        agent.description.toLowerCase().includes(searchTerm.toLowerCase())
      );
      setFilteredAgents(filtered);
    }
  }, [searchTerm, agents]);

  const loadAgents = async () => {
    try {
      setLoading(true);
      setError(null);
      const agentsList = await agentsApi.getAgents();
      setAgents(agentsList);
      setFilteredAgents(agentsList);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load agents');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-4 space-y-4">
        <div className="flex items-center space-x-2">
          <Sparkles className="h-5 w-5 text-blue-500" />
          <h3 className="text-lg font-semibold">选择智能体</h3>
        </div>
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-2 text-sm text-gray-500">加载智能体中...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 space-y-4">
        <div className="flex items-center space-x-2">
          <Sparkles className="h-5 w-5 text-red-500" />
          <h3 className="text-lg font-semibold">选择智能体</h3>
        </div>
        <div className="text-center py-8">
          <p className="text-red-500 mb-4">{error}</p>
          <Button onClick={loadAgents} variant="outline">
            重试
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center space-x-2">
        <Sparkles className="h-5 w-5 text-blue-500" />
        <h3 className="text-lg font-semibold">选择智能体</h3>
      </div>
      
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
        <Input
          placeholder="搜索智能体..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="pl-10"
        />
      </div>

      <Separator />

      <div className="space-y-2 max-h-64 overflow-y-auto">
        {filteredAgents.length === 0 ? (
          <div className="text-center py-8">
            <User className="h-12 w-12 text-gray-300 mx-auto mb-2" />
            <p className="text-gray-500">
              {searchTerm ? '没有找到匹配的智能体' : '没有可用的智能体'}
            </p>
          </div>
        ) : (
          filteredAgents.map((agent) => (
            <div
              key={agent.id}
              className="p-3 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
              onClick={() => onAgentSelect(agent)}
            >
              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0">
                  <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                    <Sparkles className="h-5 w-5 text-blue-600" />
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <h4 className="text-sm font-medium text-gray-900 truncate">
                    {agent.name}
                  </h4>
                  <p className="text-sm text-gray-500 mt-1 line-clamp-2">
                    {agent.description}
                  </p>
                  <p className="text-xs text-gray-400 mt-1 truncate">
                    {agent.address}
                  </p>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      <Separator />

      <div className="flex space-x-2">
        <Button onClick={onCancel} variant="outline" className="flex-1">
          取消
        </Button>
      </div>
    </div>
  );
} 