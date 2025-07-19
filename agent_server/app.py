#!/usr/bin/env python3
"""
ISEK Agent Server
Session management server using ISEK node communication
"""

import logging
from isek.node.etcd_registry import EtcdRegistry
from isek.node.node_v2 import Node
from session_adapter import SessionAdapter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Initialize and start the ISEK agent server"""
    try:
        # Create etcd registry
        etcd_registry = EtcdRegistry(host="47.236.116.81", port=2379)
        
        # Create session adapter
        session_adapter = SessionAdapter()
        
        # Create the server node
        server_node = Node(
            node_id="server_agent", 
            port=8888, 
            adapter=session_adapter,
            registry=etcd_registry
        )
        
        logger.info("Starting ISEK Agent Server...")
        logger.info(f"Node ID: server_agent")
        logger.info(f"Port: 8888")
        logger.info(f"Registry: 47.236.116.81:2379")
        
        # Start the server in the foreground
        server_node.build_server(daemon=False)
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise

if __name__ == '__main__':
    main()