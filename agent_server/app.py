#!/usr/bin/env python3
"""
ISEK Agent Server
Session management server using ISEK node communication
"""

import logging
import json
import os
from isek.node.etcd_registry import EtcdRegistry
from isek.node.node_v2 import Node
from session_adapter import SessionAdapter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_config():
    """Load configuration from config.json"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r') as f:
        return json.load(f)

def main():
    """Initialize and start the ISEK agent server"""
    try:
        # Load configuration
        config = load_config()
        
        # Create etcd registry
        etcd_registry = EtcdRegistry(
            host=config["registry"]["host"], 
            port=config["registry"]["port"]
        )
        
        # Create session adapter
        session_adapter = SessionAdapter()
        
        # Create the server node
        server_node = Node(
            node_id=config["node_id"],
            port=config["port"], 
            adapter=session_adapter,
            registry=etcd_registry
        )
        
        logger.info("Starting ISEK Agent Server...")
        logger.info(f"Node ID: {config['node_id']}")
        logger.info(f"Port: {config['port']}")
        logger.info(f"P2P Port: {config['p2p_server_port']}")
        logger.info(f"Registry: {config['registry']['host']}:{config['registry']['port']}")
        
        # Start the server in the foreground
        server_node.build_server(daemon=False)
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise

if __name__ == '__main__':
    main()