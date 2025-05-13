#!/usr/bin/env python3
from flask import Flask, Response, request, jsonify
import json
import time
import logging
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('LightRAG-Flask-MCP')

app = Flask(__name__)

# Define the tools this MCP server provides
TOOLS = [
    {
        "name": "query",
        "description": "Query VAEBZ product information using natural language",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The query about VAEBZ products or services"
                }
            },
            "required": ["query"]
        }
    }
]

@app.route('/', methods=['GET'])
@app.route('/mcp/lightrag', methods=['GET'])
def sse():
    logger.info(f"Received GET request at path: {request.path}")
    
    # Check if Accept header is for SSE
    accept_header = request.headers.get('Accept', '')
    if 'text/event-stream' in accept_header:
        logger.info("Client requested SSE stream")
        def generate():
            # Send initial events
            yield f"event: connected\ndata: {json.dumps({'status': 'connected', 'message': 'LightRAG MCP Server Connected'})}\n\n"
            
            # Send tools definition
            yield f"event: tools\ndata: {json.dumps({'tools': TOOLS})}\n\n"
            
            # Keep connection open with heartbeats
            while True:
                time.sleep(10)
                yield f"event: heartbeat\ndata: {json.dumps({'type': 'heartbeat', 'timestamp': time.time()})}\n\n"
        
        return Response(generate(), content_type='text/event-stream')
    else:
        # Regular HTTP response for non-SSE requests
        return jsonify({
            'status': 'ok',
            'message': 'LightRAG MCP Server is running',
            'data': {
                'capabilities': ['query'],
                'tools': TOOLS
            }
        })

@app.route('/', methods=['POST'])
@app.route('/mcp/lightrag', methods=['POST'])
def handle_request():
    logger.info(f"Received POST request at path: {request.path}")
    try:
        request_data = request.get_json()
        logger.info(f"Received request: {json.dumps(request_data, indent=2)}")
        
        if 'action' in request_data and request_data['action'] == 'query':
            return handle_query(request_data)
        elif 'action' in request_data and request_data['action'] == 'get_tools':
            return jsonify({
                'status': 'ok',
                'message': 'Tools retrieved',
                'data': {
                    'tools': TOOLS
                }
            })
        else:
            return jsonify({
                'status': 'ok',
                'message': 'Request received',
                'data': {}
            })
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error: {str(e)}',
            'data': {}
        })

def handle_query(data):
    query_text = data.get('data', {}).get('query', '')
    if not query_text:
        return jsonify({
            'status': 'error',
            'message': 'No query provided',
            'data': None
        })
    
    # Hardcoded response about VAEBZ
    if 'vaebz' in query_text.lower():
        response_text = "VAEBZ is a technology company specializing in AI infrastructure and automation solutions. Key products include TaskHarbinger, LightRAG, MCP Services, SentinelGaze, AtomicScope, and ProposalForge."
    else:
        response_text = f"Based on available information, I can tell you that your query '{query_text}' relates to VAEBZ's AI products and services. VAEBZ offers TaskHarbinger for AI orchestration, LightRAG for knowledge integration, and several other AI automation tools."
    
    return jsonify({
        'status': 'ok',
        'message': 'Query processed',
        'data': {
            'response': response_text,
            'sources': [
                {'title': 'VAEBZ Knowledge Base', 'snippet': 'Information about VAEBZ and TaskHarbinger', 'confidence': 0.95}
            ]
        }
    })

# Add health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'ok',
        'message': 'LightRAG MCP Server is healthy'
    })

if __name__ == '__main__':
    port = int(os.environ.get('MCP_HTTP_PORT', 9626))
    host = os.environ.get('MCP_HTTP_HOST', '0.0.0.0')
    logger.info(f'LightRAG Flask MCP Server starting on {host}:{port}')
    app.run(host=host, port=port, threaded=True) 