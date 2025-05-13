#!/usr/bin/env python3
import json
import os
import http.server
import logging
import time
import queue
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('LightRAG-Simple-MCP')

# Queue for SSE events
event_queue = queue.Queue()

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

class SimpleHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # Check Accept header for SSE requests
        accept_header = self.headers.get('Accept', '')
        if 'text/event-stream' in accept_header:
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()
            
            logger.info("Client connected for SSE stream")
            
            # Send initial events
            # 1. Connected event
            self.send_sse_event('connected', {
                "status": "connected", 
                "message": "LightRAG MCP Server Connected"
            })
            
            # 2. Tools definition event
            self.send_sse_event('tools', {
                "type": "tools",
                "tools": TOOLS
            })
            
            # 3. Capabilities event
            self.send_sse_event('capabilities', {
                "status": "ok",
                "message": "Capabilities retrieved",
                "data": {
                    "capabilities": ["query"],
                    "models": {
                        "llm": "llama3:instruct"
                    },
                    "api_version": "1.0",
                    "tools": TOOLS
                }
            })
            
            try:
                # Keep connection open and send events
                while True:
                    # Check for events every second for 30 seconds
                    for _ in range(30):
                        # Check if there's any event in the queue
                        try:
                            event = event_queue.get(block=False)
                            # Send the event
                            self.send_sse_event('message', event)
                        except queue.Empty:
                            # No events, continue
                            pass
                        
                        # Sleep for 1 second
                        time.sleep(1)
                    
                    # Send heartbeat
                    self.send_sse_event('heartbeat', {
                        "type": "heartbeat",
                        "timestamp": time.time()
                    })
            except (ConnectionResetError, BrokenPipeError) as e:
                logger.info(f"Client disconnected from SSE stream: {str(e)}")
                return
        # Health check endpoint
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            health_response = {
                'status': 'ok',
                'message': 'LightRAG Simple MCP Server is healthy'
            }
            self.wfile.write(json.dumps(health_response).encode())
            return
            
        # For capabilities endpoint
        elif self.path == '/capabilities' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            capabilities = {
                'status': 'ok',
                'message': 'Capabilities retrieved',
                'data': {
                    'capabilities': ['query'],
                    'models': {
                        'llm': 'llama3:instruct'
                    },
                    'api_version': '1.0',
                    'tools': TOOLS
                }
            }
            self.wfile.write(json.dumps(capabilities).encode())
            return

        # For tools endpoint
        elif self.path == '/tools':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            tools_response = {
                'status': 'ok',
                'message': 'Tools retrieved',
                'data': {
                    'tools': TOOLS
                }
            }
            self.wfile.write(json.dumps(tools_response).encode())
            return
            
        # Default response
        else:
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'LightRAG Simple MCP Server Running')
    
    def send_sse_event(self, event_type, data):
        """Helper method to send SSE events in the correct format"""
        self.wfile.write(f"event: {event_type}\n".encode())
        self.wfile.write(f"data: {json.dumps(data)}\n\n".encode())
        self.wfile.flush()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            post_data = self.rfile.read(content_length).decode('utf-8')
            try:
                request_data = json.loads(post_data)
                logger.info(f"Received request: {json.dumps(request_data, indent=2)}")
                
                # Process based on action
                if 'action' in request_data:
                    action = request_data.get('action')
                    if action == 'query':
                        response = self.handle_query(request_data)
                    elif action == 'get_tools':
                        response = {
                            'status': 'ok',
                            'message': 'Tools retrieved',
                            'data': {
                                'tools': TOOLS
                            }
                        }
                    else:
                        response = {
                            'status': 'ok',
                            'message': f"Action '{action}' acknowledged",
                            'data': {}
                        }
                else:
                    response = {
                        'status': 'ok',
                        'message': "No action specified",
                        'data': {}
                    }
            except json.JSONDecodeError:
                logger.error(f"Received non-JSON data: {post_data}")
                response = {
                    'status': 'error',
                    'message': 'Invalid JSON data'
                }
        else:
            response = {
                'status': 'ok',
                'message': "Empty request",
                'data': {}
            }
        
        # Send response
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
        
        # Also add to SSE queue for any listening clients
        event_queue.put(response)
    
    def handle_query(self, data):
        query_text = data.get('data', {}).get('query', '')
        if not query_text:
            return {
                'status': 'error',
                'message': 'No query provided',
                'data': None
            }
        
        # For simplicity, we'll just return a hardcoded response about VAEBZ
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
    # Get configuration from environment or use defaults
    host = '0.0.0.0'
    port = 9626
    server_address = (host, port)
    
    httpd = http.server.HTTPServer(server_address, SimpleHTTPRequestHandler)
    logger.info(f'LightRAG Simple MCP Server started on {host}:{port}')
    httpd.serve_forever()

if __name__ == '__main__':
    run_server() 