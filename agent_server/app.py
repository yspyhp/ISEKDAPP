from flask import Flask, request, jsonify
from service.session_service import SessionService
from mapper.models import Session, Message
import json

app = Flask(__name__)
session_service = SessionService()

@app.route('/session/create', methods=['POST'])
def create_session():
    try:
        session = Session.from_dict(json.loads(request.data))
        session = session_service.create_session(session)
        return jsonify(session), 200 if session else 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/session/list', methods=['GET'])
def get_sessions():
    try:
        creator_id = request.args.get('creator_id')
        sessions = session_service.get_user_sessions(creator_id)
        return jsonify(sessions), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/session/delete', methods=['DELETE'])
def delete_session():
    try:
        session_id = request.args.get('session_id')
        creator_id = request.args.get('creator_id')
        success = session_service.delete_session(session_id, creator_id)
        return jsonify({'success': success}), 200 if success else 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/session/get', methods=['GET'])
def get_session_by_id():
    try:
        session_id = request.args.get('session_id')
        creator_id = request.args.get('creator_id')
        session = session_service.get_session_by_id(session_id, creator_id)
        return jsonify(session), 200 if session else 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/message/list', methods=['GET'])
def get_messages():
    try:
        session_id = request.args.get('session_id')
        creator_id = request.args.get('creator_id')
        messages = session_service.get_session_messages(session_id, creator_id)
        return jsonify(messages), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/message/create', methods=['POST'])
def create_message():
    try:
        message = Message.from_dict(json.loads(request.data))
        creator_id = request.args.get('creator_id')
        message = session_service.create_message(message, creator_id)
        return jsonify(message), 200 if message else 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

from isek.node.etcd_registry import EtcdRegistry
from isek.node.node_v2 import Node
from rn_agent import RandomNumberAdapter
if __name__ == '__main__':
    etcd_registry = EtcdRegistry(host="47.236.116.81", port=2379)
    # Create the server node.
    server_node = Node(node_id="Eugen_RN", port=6001, p2p=False, p2p_server_port=6002, adapter=RandomNumberAdapter(),
                       registry=etcd_registry)

    # Start the server in the foreground.
    server_node.build_server(daemon=True)

    app.run(debug=True, port=6000)