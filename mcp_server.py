#!/usr/bin/env python3
import json
import os
import requests
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
import threading
import queue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('LightRAG-MCP')

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
    },
    {
        "name": "embedding",
        "description": "Get embeddings for a given text",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text to embed"
                }
            },
            "required": ["text"]
        }
    }
]

class MCPHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Parse request content
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
                    elif action == 'embedding':
                        response = self.handle_embedding(request_data)
                    elif action == 'capabilities':
                        response = self.handle_capabilities()
                    elif action == 'get_tools':
                        response = self.handle_get_tools()
                    else:
                        response = self.default_response(f"Action '{action}' acknowledged")
                else:
                    response = self.default_response("No action specified")
            except json.JSONDecodeError:
                logger.error(f"Received non-JSON data: {post_data}")
                response = {
                    'status': 'error',
                    'message': 'Invalid JSON data'
                }
        else:
            response = self.default_response("Empty request")
        
        # Send response
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
        
        # Also add to SSE queue for any listening clients
        event_queue.put(response)
    
    def do_GET(self):
        # Add basic health check endpoint
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            health_response = {
                'status': 'ok',
                'message': 'LightRAG MCP Server is healthy'
            }
            self.wfile.write(json.dumps(health_response).encode())
            return
            
        # Check if client is requesting SSE
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
            self.send_sse_event('capabilities', self.handle_capabilities())
            
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
        else:
            # Regular HTTP response
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'LightRAG MCP Server Running')
    
    def send_sse_event(self, event_type, data):
        """Helper method to send SSE events in the correct format"""
        self.wfile.write(f"event: {event_type}\n".encode())
        self.wfile.write(f"data: {json.dumps(data)}\n\n".encode())
        self.wfile.flush()
    
    def handle_get_tools(self):
        """Return the tools available in this MCP server"""
        return {
            'status': 'ok',
            'message': 'Tools retrieved',
            'data': {
                'tools': TOOLS
            }
        }
    
    def handle_query(self, data):
        """Handle query requests by sending directly to LLM with context"""
        try:
            query_text = data.get('data', {}).get('query', '')
            if not query_text:
                return {
                    'status': 'error',
                    'message': 'No query provided',
                    'data': None
                }
            
            # Get LLM configuration from environment
            llm_binding = os.environ.get('LLM_BINDING', 'ollama')
            llm_host = os.environ.get('LLM_BINDING_HOST', 'http://host.docker.internal:11434')
            llm_model = os.environ.get('LLM_MODEL', 'llama3:instruct')
            
            # Prepare a context-enriched prompt about VAEBZ and TaskHarbinger
            context = """
VAEBZ is a technology company specializing in AI infrastructure and automation solutions.
Key products include:
- TaskHarbinger: An AI orchestration platform for workflow automation
- LightRAG: A retrieval-augmented generation system for knowledge integration
- MCP Services: AI service integrations using Marvin Control Protocol
- SentinelGaze: Web UI for system monitoring and management
- AtomicScope: A real-time code analysis and visualization tool for developers
- ProposalForge: An automated proposal generation and management system

TaskHarbinger features include orchestration of AI tasks, integration with various AI services, 
support for LightRAG, Git MCP server, containerized architecture with Docker, Traefik for API routing, 
DynamoDB for persistence, Redis for caching, and UI for monitoring.

AtomicScope provides real-time code structure visualization, dependency analysis, impact assessment of 
code changes, integration with version control systems, performance bottleneck identification, and 
automated refactoring suggestions. It helps development teams understand complex codebases more easily.

ProposalForge is VAEBZ's AI-powered proposal system that automates the creation, management, and tracking 
of business proposals. It features customizable templates, content generation based on client requirements, 
pricing optimization algorithms, approval workflows, digital signature integration, analytics dashboards, 
and seamless integration with CRM systems. The system reduces proposal creation time by up to 70% while 
improving win rates through personalized content and data-driven insights.

MCP (Marvin Control Protocol) allows standardized communication between AI services with support for 
multiple transport methods, service discovery, integration with AI tools, authentication, and action frameworks.

The system uses a microservice architecture with Docker containers, API routing through Traefik, 
and various specialized components for AI processing.
"""
            
            prompt = f"""Based on the following context about VAEBZ and its products, please answer this question:

CONTEXT:
{context}

QUESTION:
{query_text}

If the question cannot be answered based on the context, please only use information that would be factual about 
VAEBZ as a technology company focused on AI infrastructure and automation. Do not invent specific details about 
people, events, or statistics that aren't in the context."""
            
            # Use the LLM to answer
            if llm_binding == 'ollama':
                endpoint = f"{llm_host}/api/generate"
                payload = {
                    'model': llm_model,
                    'prompt': prompt,
                    'stream': False
                }
                
                logger.info(f"Sending request to Ollama with context-enriched prompt")
                response = requests.post(endpoint, json=payload, timeout=60)
                
                if response.status_code == 200:
                    llm_response = response.json()
                    return {
                        'status': 'ok',
                        'message': 'Query processed',
                        'data': {
                            'response': llm_response.get('response', 'No response from LLM'),
                            'sources': [
                                {'title': 'VAEBZ Knowledge Base', 'snippet': 'Information about VAEBZ and TaskHarbinger', 'confidence': 0.95}
                            ]
                        }
                    }
                else:
                    logger.error(f"Error from LLM: {response.status_code} - {response.text}")
            
            # Fallback response if LLM call fails
            return {
                'status': 'error',
                'message': 'Failed to process query',
                'data': {
                    'response': f"I'm unable to answer your question about '{query_text}' at this time. Please try again later.",
                    'sources': []
                }
            }
                
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            return {
                'status': 'error',
                'message': f'Error processing query: {str(e)}',
                'data': None
            }
    
    def handle_embedding(self, data):
        """Handle embedding requests"""
        try:
            text = data.get('data', {}).get('text', '')
            if not text:
                return {
                    'status': 'error',
                    'message': 'No text provided for embedding',
                    'data': None
                }
            
            # Get embedding configuration from environment
            embedding_binding = os.environ.get('EMBEDDING_BINDING', 'ollama')
            embedding_host = os.environ.get('EMBEDDING_BINDING_HOST', 'http://host.docker.internal:11434')
            embedding_model = os.environ.get('EMBEDDING_MODEL', 'bge-m3:latest')
            
            # For Ollama binding
            if embedding_binding == 'ollama':
                endpoint = f"{embedding_host}/api/embeddings"
                payload = {
                    'model': embedding_model,
                    'prompt': text
                }
                
                logger.info(f"Sending embedding request to Ollama: {endpoint}")
                response = requests.post(endpoint, json=payload, timeout=30)
                
                if response.status_code == 200:
                    embedding_response = response.json()
                    return {
                        'status': 'ok',
                        'message': 'Embedding processed',
                        'data': {
                            'dimensions': len(embedding_response.get('embedding', [])),
                            'model': embedding_model,
                            'status': 'success'
                        }
                    }
            
            # Fallback if embedding service is unavailable
            return {
                'status': 'error',
                'message': 'Embedding service unavailable',
                'data': {
                    'dimensions': 0,
                    'model': embedding_model,
                    'status': 'failed'
                }
            }
                
        except Exception as e:
            logger.error(f"Error processing embedding request: {str(e)}")
            return {
                'status': 'error',
                'message': f'Error processing embedding: {str(e)}',
                'data': None
            }
    
    def handle_capabilities(self):
        """Return capabilities of the MCP server"""
        return {
            'status': 'ok',
            'message': 'Capabilities retrieved',
            'data': {
                'capabilities': [
                    'rag',
                    'embedding',
                    'query'
                ],
                'models': {
                    'llm': os.environ.get('LLM_MODEL', 'llama3:instruct'),
                    'embedding': os.environ.get('EMBEDDING_MODEL', 'bge-m3:latest')
                },
                'api_version': '1.0',
                'tools': TOOLS
            }
        }
    
    def default_response(self, message):
        """Default response for unhandled actions"""
        return {
            'status': 'ok',
            'message': message,
            'data': {
                'capabilities': ['rag', 'embedding', 'query'],
                'api_version': '1.0'
            }
        }

def run_server():
    # Get configuration from environment or use defaults
    host = os.environ.get('MCP_HTTP_HOST', '0.0.0.0')
    port = int(os.environ.get('MCP_HTTP_PORT', 9626))
    server_address = (host, port)
    
    httpd = HTTPServer(server_address, MCPHandler)
    logger.info(f'LightRAG MCP Server started on {host}:{port}')
    httpd.serve_forever()

if __name__ == '__main__':
    run_server() 