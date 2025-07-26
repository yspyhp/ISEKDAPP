"""
P2P Task Management Example
展示如何使用P2P版本的任务管理功能
"""

import asyncio
import json
from typing import Dict, Any

from agent_server.protocol.a2a_protocol import A2AProtocol
from agent_server.adapter.isek_adapter import UnifiedIsekAdapter
from isek.team.isek_team import IsekTeam
from isek.agent.isek_agent import IsekAgent
from isek.utils.log import log


class P2PTaskManagerExample:
    """P2P任务管理示例"""
    
    def __init__(self, node_id: str, port: int, p2p_port: int):
        self.node_id = node_id
        self.port = port
        self.p2p_port = p2p_port
        
        # 创建简单的team用于测试
        self.team = self._create_test_team()
        
        # 创建adapter
        self.adapter = UnifiedIsekAdapter(
            isek_team=self.team,
            enable_streaming=False
        )
        
        # 创建A2A协议
        self.a2a_protocol = A2AProtocol(
            host="localhost",
            port=port,
            p2p=True,
            p2p_server_port=p2p_port,
            adapter=self.adapter
        )
    
    def _create_test_team(self) -> IsekTeam:
        """创建测试用的团队"""
        # 这里使用简单的模拟agent，实际使用时替换为真实的agent
        return IsekTeam(
            name="P2P Test Team",
            description="Team for P2P task management testing",
            members=[]  # 简化示例，不添加实际agent
        )
    
    async def demonstrate_p2p_task_management(self):
        """演示P2P任务管理功能"""
        
        print("🚀 P2P Task Management Demo")
        print("=" * 50)
        
        # 模拟的远程节点信息
        remote_node_id = "remote-agent-node"
        remote_p2p_address = "/ip4/127.0.0.1/tcp/9001/p2p/QmRemoteNodeId"
        
        # 1. 发送P2P消息并获取任务ID
        print("\n1. 发送P2P消息...")
        try:
            response = self.a2a_protocol.send_p2p_message(
                sender_node_id=self.node_id,
                p2p_address=remote_p2p_address,
                message="请帮我分析这个复杂的数据集"
            )
            print(f"   消息发送成功: {response[:100]}...")
            
            # 假设从响应中提取任务ID（实际实现中会从A2A响应解析）
            task_id = "task_123456"
            
        except Exception as e:
            print(f"   消息发送失败: {e}")
            return
        
        # 2. P2P获取任务状态
        print(f"\n2. P2P获取任务状态 (Task ID: {task_id})...")
        task_status = self.a2a_protocol.get_task_p2p(
            sender_node_id=self.node_id,
            p2p_address=remote_p2p_address,
            task_id=task_id
        )
        
        if task_status.get("error"):
            print(f"   获取任务状态失败: {task_status['error']}")
        else:
            print(f"   任务状态: {json.dumps(task_status, indent=2)}")
        
        # 3. P2P获取任务进度
        print(f"\n3. P2P获取任务进度...")
        task_progress = self.a2a_protocol.get_task_progress_p2p(
            sender_node_id=self.node_id,
            p2p_address=remote_p2p_address,
            task_id=task_id
        )
        
        if task_progress:
            print(f"   任务进度: {json.dumps(task_progress, indent=2)}")
        else:
            print("   无法获取任务进度")
        
        # 4. P2P取消任务
        print(f"\n4. P2P取消任务...")
        cancel_result = self.a2a_protocol.cancel_task_p2p(
            sender_node_id=self.node_id,
            p2p_address=remote_p2p_address,
            task_id=task_id
        )
        
        if cancel_result.get("error"):
            print(f"   任务取消失败: {cancel_result['error']}")
        else:
            print(f"   任务取消结果: {json.dumps(cancel_result, indent=2)}")
        
        # 5. 验证任务是否已取消
        print(f"\n5. 验证任务取消状态...")
        final_status = self.a2a_protocol.get_task_p2p(
            sender_node_id=self.node_id,
            p2p_address=remote_p2p_address,
            task_id=task_id
        )
        
        if final_status.get("error"):
            print(f"   获取最终状态失败: {final_status['error']}")
        else:
            print(f"   最终任务状态: {json.dumps(final_status, indent=2)}")
    
    def demonstrate_direct_a2a_task_management(self):
        """演示直接A2A任务管理功能"""
        
        print("\n" + "=" * 50)
        print("🌐 Direct A2A Task Management Demo")
        print("=" * 50)
        
        # 模拟的远程A2A服务器
        remote_address = "http://localhost:8082"
        task_id = "direct_task_789"
        
        # 1. 直接A2A获取任务状态
        print(f"\n1. 直接A2A获取任务状态 (Task ID: {task_id})...")
        task_status = self.a2a_protocol.get_task(
            sender_node_id=self.node_id,
            target_address=remote_address,
            task_id=task_id
        )
        
        if task_status.get("error"):
            print(f"   获取任务状态失败: {task_status['error']}")
        else:
            print(f"   任务状态: {json.dumps(task_status, indent=2)}")
        
        # 2. 直接A2A取消任务
        print(f"\n2. 直接A2A取消任务...")
        cancel_result = self.a2a_protocol.cancel_task(
            sender_node_id=self.node_id,
            target_address=remote_address,
            task_id=task_id
        )
        
        if cancel_result.get("error"):
            print(f"   任务取消失败: {cancel_result['error']}")
        else:
            print(f"   任务取消结果: {json.dumps(cancel_result, indent=2)}")
    
    def compare_p2p_vs_direct(self):
        """比较P2P vs 直接A2A的区别"""
        
        print("\n" + "=" * 50)
        print("📊 P2P vs Direct A2A Comparison")
        print("=" * 50)
        
        comparison = {
            "P2P方式": {
                "优势": [
                    "通过P2P网络发现节点",
                    "支持NAT穿透",
                    "去中心化通信",
                    "更好的网络弹性"
                ],
                "适用场景": [
                    "分布式agent网络",
                    "动态节点发现",
                    "边缘计算环境",
                    "不稳定网络条件"
                ]
            },
            "直接A2A方式": {
                "优势": [
                    "更直接的通信",
                    "更低的延迟",
                    "更简单的调试",
                    "更好的错误处理"
                ],
                "适用场景": [
                    "已知服务器地址",
                    "稳定网络环境",
                    "企业内网部署",
                    "高性能要求"
                ]
            }
        }
        
        for method, details in comparison.items():
            print(f"\n{method}:")
            print(f"  优势: {', '.join(details['优势'])}")
            print(f"  适用场景: {', '.join(details['适用场景'])}")


def main():
    """主函数"""
    
    # 配置
    node_id = "p2p-demo-node"
    port = 8080
    p2p_port = 9000
    
    # 创建示例
    demo = P2PTaskManagerExample(node_id, port, p2p_port)
    
    try:
        # 运行演示
        print("开始P2P任务管理演示...")
        
        # 异步演示
        asyncio.run(demo.demonstrate_p2p_task_management())
        
        # 同步演示
        demo.demonstrate_direct_a2a_task_management()
        
        # 比较分析
        demo.compare_p2p_vs_direct()
        
        print("\n✅ 演示完成!")
        
    except Exception as e:
        log.error(f"演示过程中出错: {e}")
        print(f"❌ 演示失败: {e}")


if __name__ == "__main__":
    main()