#!/usr/bin/env python3
import json
import http.server
import logging
import time
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('LightRAG-SSE-MCP')

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

class SSEHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # Always respond with SSE format for Cursor
        logger.info("Received GET request, sending SSE response")
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        logger.info("SSE connection established")
        
        # Send initial events
        # 1. Connected event
        self.send_sse_event('connected', {
            "status": "connected", 
            "message": "LightRAG MCP Server Connected"
        })
        
        # 2. Tools definition event
        self.send_sse_event('tools', {
            "tools": TOOLS
        })
        
        # Keep the connection open and send heartbeats
        try:
            while True:
                # Send periodic heartbeats
                self.send_sse_event('heartbeat', {
                    "type": "heartbeat",
                    "timestamp": time.time()
                })
                
                # Sleep for a few seconds
                time.sleep(5)
        except (ConnectionResetError, BrokenPipeError) as e:
            logger.info(f"Client disconnected: {str(e)}")
            return
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            post_data = self.rfile.read(content_length).decode('utf-8')
            try:
                request_data = json.loads(post_data)
                logger.info(f"Received request: {json.dumps(request_data, indent=2)}")
                
                # Process query request
                if 'action' in request_data and request_data['action'] == 'query':
                    response = self.handle_query(request_data)
                else:
                    response = {
                        'status': 'ok',
                        'message': 'Request received',
                        'data': {}
                    }
                
                # Send response in SSE format
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
                
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON: {post_data}")
                self.send_error(400, "Invalid JSON data")
        else:
            self.send_error(400, "Empty request")
    
    def send_sse_event(self, event_type, data):
        """Helper method to send SSE events in the correct format"""
        message = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        self.wfile.write(message.encode())
        self.wfile.flush()
        logger.info(f"Sent SSE event: {event_type}")
    
    def handle_query(self, data):
        query_text = data.get('data', {}).get('query', '')
        if not query_text:
            return {
                'status': 'error',
                'message': 'No query provided'
            }
        
        # Hardcoded response about VAEBZ
        if 'vaebz' in query_text.lower():
            response_text = "VAEBZ is a technology company specializing in AI infrastructure and automation solutions. Key products include TaskHarbinger, LightRAG, MCP Services, SentinelGaze, AtomicScope, and ProposalForge."
        else:
            response_text = f"Based on available information, I can tell you that your query '{query_text}' relates to VAEBZ's AI products and services. VAEBZ offers TaskHarbinger for AI orchestration, LightRAG for knowledge integration, and several other AI automation tools."
        
        return {
            'status': 'ok',
            'message': 'Query processed',
            'data': {
                'response': response_text,
                'sources': [
                    {'title': 'VAEBZ Knowledge Base', 'snippet': 'Information about VAEBZ and TaskHarbinger', 'confidence': 0.95}
                ]
            }
        }

def run_server():
    host = '0.0.0.0'
    port = 9626
    server_address = (host, port)
    
    httpd = http.server.HTTPServer(server_address, SSEHandler)
    logger.info(f'LightRAG SSE MCP Server started on {host}:{port}')
    httpd.serve_forever()

if __name__ == '__main__':
    run_server() 