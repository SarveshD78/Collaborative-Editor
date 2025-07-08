#!/usr/bin/env python3
import socket
import threading
import json
import sqlite3
from datetime import datetime
import hashlib
import base64
import struct
import re

class SimpleWebSocketServer:
    def __init__(self):
        self.clients = {}  # {doc_id: {client_id: connection}}
        self.document_users = {}  # {doc_id: {client_id: username}}
        self.client_threads = []
        
    def get_document_content(self, doc_id):
        try:
            conn = sqlite3.connect('db.sqlite3')
            cursor = conn.cursor()
            cursor.execute("SELECT content FROM documents_document WHERE id = ?", (doc_id,))
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else ""
        except Exception as e:
            print(f"❌ Error getting document content: {e}")
            return ""
    
    def update_document_content(self, doc_id, content):
        try:
            conn = sqlite3.connect('db.sqlite3')
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE documents_document SET content = ?, updated_at = ? WHERE id = ?",
                (content, datetime.now(), doc_id)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"❌ Error updating document: {e}")
            return False
    
    def websocket_handshake(self, client_socket, request):
        """Perform WebSocket handshake"""
        try:
            # Extract WebSocket key from request
            key_match = re.search(r'Sec-WebSocket-Key: (.*)', request)
            if not key_match:
                return False
            
            key = key_match.group(1).strip()
            
            # Generate accept key
            magic_string = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
            accept_key = base64.b64encode(
                hashlib.sha1((key + magic_string).encode()).digest()
            ).decode()
            
            # Send handshake response
            response = (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept_key}\r\n"
                "\r\n"
            )
            
            client_socket.send(response.encode())
            return True
        except Exception as e:
            print(f"❌ Handshake error: {e}")
            return False
    
    def decode_websocket_frame(self, data):
        """Decode a WebSocket frame"""
        try:
            if len(data) < 2:
                return None
            
            byte1, byte2 = data[0], data[1]
            fin = byte1 & 0x80
            opcode = byte1 & 0x0f
            masked = byte2 & 0x80
            payload_length = byte2 & 0x7f
            
            # Handle close frame
            if opcode == 0x8:
                return "CLOSE"
            
            # Only handle text frames
            if opcode != 0x1:
                return None
            
            offset = 2
            
            # Extended payload length
            if payload_length == 126:
                if len(data) < offset + 2:
                    return None
                payload_length = struct.unpack(">H", data[offset:offset+2])[0]
                offset += 2
            elif payload_length == 127:
                if len(data) < offset + 8:
                    return None
                payload_length = struct.unpack(">Q", data[offset:offset+8])[0]
                offset += 8
            
            # Masking key
            if masked:
                if len(data) < offset + 4:
                    return None
                mask = data[offset:offset+4]
                offset += 4
            
            # Payload
            if len(data) < offset + payload_length:
                return None
            
            payload = data[offset:offset+payload_length]
            
            # Unmask payload if masked
            if masked:
                payload = bytearray(payload)
                for i in range(len(payload)):
                    payload[i] ^= mask[i % 4]
                payload = bytes(payload)
            
            return payload.decode('utf-8')
        except Exception as e:
            print(f"❌ Frame decode error: {e}")
            return None
    
    def encode_websocket_frame(self, message):
        """Encode a message as a WebSocket frame"""
        try:
            message_bytes = message.encode('utf-8')
            length = len(message_bytes)
            
            # Frame header
            if length < 126:
                frame = bytearray([0x81, length])
            elif length < 65536:
                frame = bytearray([0x81, 126]) + struct.pack(">H", length)
            else:
                frame = bytearray([0x81, 127]) + struct.pack(">Q", length)
            
            # Add payload
            frame.extend(message_bytes)
            return bytes(frame)
        except Exception as e:
            print(f"❌ Frame encode error: {e}")
            return b""
    
    def send_message(self, client_socket, message):
        """Send a JSON message to client"""
        try:
            json_message = json.dumps(message)
            frame = self.encode_websocket_frame(json_message)
            client_socket.send(frame)
            return True
        except Exception as e:
            print(f"❌ Send error: {e}")
            return False
    
    def broadcast_to_document(self, doc_id, message, exclude_client=None):
        """Broadcast message to all clients in a document"""
        if doc_id in self.clients:
            disconnected = []
            for client_id, client_socket in self.clients[doc_id].items():
                if client_id != exclude_client:
                    if not self.send_message(client_socket, message):
                        disconnected.append(client_id)
            
            # Clean up disconnected clients
            for client_id in disconnected:
                self.remove_client(doc_id, client_id)
    
    def add_client(self, doc_id, client_id, client_socket, username):
        """Add a new client to a document"""
        if doc_id not in self.clients:
            self.clients[doc_id] = {}
            self.document_users[doc_id] = {}
        
        self.clients[doc_id][client_id] = client_socket
        self.document_users[doc_id][client_id] = username
        
        print(f"✅ User {username} connected to document {doc_id}")
        
        # Send welcome messages
        self.send_message(client_socket, {
            'type': 'connected',
            'message': f'Connected to document {doc_id}'
        })
        
        # Send online users
        online_users = list(self.document_users[doc_id].values())
        self.send_message(client_socket, {
            'type': 'online_users',
            'users': online_users
        })
        
        # Send document content
        content = self.get_document_content(doc_id)
        self.send_message(client_socket, {
            'type': 'document_content',
            'content': content
        })
        
        # Notify others
        self.broadcast_to_document(doc_id, {
            'type': 'user_joined',
            'username': username
        }, exclude_client=client_id)
    
    def remove_client(self, doc_id, client_id):
        """Remove a client from a document"""
        if doc_id in self.clients and client_id in self.clients[doc_id]:
            username = self.document_users[doc_id].get(client_id, 'Unknown')
            
            try:
                self.clients[doc_id][client_id].close()
            except:
                pass
            
            del self.clients[doc_id][client_id]
            del self.document_users[doc_id][client_id]
            
            print(f"❌ User {username} disconnected from document {doc_id}")
            
            # Notify others
            self.broadcast_to_document(doc_id, {
                'type': 'user_left',
                'username': username
            })
            
            # Clean up empty rooms
            if not self.clients[doc_id]:
                del self.clients[doc_id]
                del self.document_users[doc_id]
    
    def handle_message(self, doc_id, username, client_id, client_socket, message_data):
        """Handle a message from a client"""
        try:
            message = json.loads(message_data)
            message_type = message.get('type')
            
            if message_type == 'document_change':
                content = message.get('content', '')
                print(f"📝 Document {doc_id} updated by {username}: {len(content)} chars")
                
                if self.update_document_content(doc_id, content):
                    self.broadcast_to_document(doc_id, {
                        'type': 'document_update',
                        'content': content,
                        'username': username
                    }, exclude_client=client_id)
                else:
                    self.send_message(client_socket, {
                        'type': 'error',
                        'message': 'Failed to save document'
                    })
        except json.JSONDecodeError:
            self.send_message(client_socket, {
                'type': 'error',
                'message': 'Invalid JSON'
            })
        except Exception as e:
            print(f"❌ Message handling error: {e}")
    
    def handle_client(self, client_socket, address):
        """Handle a new client connection"""
        doc_id = None
        client_id = None
        
        try:
            print(f"🔌 New connection from {address}")
            
            # Read HTTP request
            request = client_socket.recv(4096).decode('utf-8')
            print(f"📡 Request received")
            
            # Extract path
            first_line = request.split('\n')[0]
            path = first_line.split(' ')[1]
            print(f"📍 Path: {path}")
            
            # Parse path: /ws/document/123/username/alice
            parts = path.strip('/').split('/')
            if len(parts) >= 4 and parts[0] == 'ws' and parts[1] == 'document':
                doc_id = int(parts[2])
                username = parts[4] if len(parts) > 4 else 'Anonymous'
                print(f"✅ Parsed: doc_id={doc_id}, username={username}")
            else:
                print(f"❌ Invalid path: {path}")
                client_socket.close()
                return
            
            # Perform WebSocket handshake
            if not self.websocket_handshake(client_socket, request):
                print("❌ Handshake failed")
                client_socket.close()
                return
            
            print(f"✅ Handshake successful for {username}")
            
            # Add client
            client_id = id(client_socket)
            self.add_client(doc_id, client_id, client_socket, username)
            
            # Handle messages
            while True:
                try:
                    data = client_socket.recv(4096)
                    if not data:
                        break
                    
                    message = self.decode_websocket_frame(data)
                    if message == "CLOSE":
                        break
                    elif message:
                        self.handle_message(doc_id, username, client_id, client_socket, message)
                
                except ConnectionResetError:
                    break
                except Exception as e:
                    print(f"❌ Receive error: {e}")
                    break
        
        except Exception as e:
            print(f"❌ Client error: {e}")
        finally:
            if doc_id is not None and client_id is not None:
                self.remove_client(doc_id, client_id)
            try:
                client_socket.close()
            except:
                pass
    
    def start_server(self):
        """Start the WebSocket server"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server_socket.bind(('localhost', 8766))
            server_socket.listen(5)
            
            print("🚀 Pure Python WebSocket server starting on localhost:8766")
            print("✅ Server ready for connections!")
            print("📡 Waiting for clients...")
            
            while True:
                try:
                    client_socket, address = server_socket.accept()
                    # Handle each client in a separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address),
                        daemon=True
                    )
                    client_thread.start()
                    self.client_threads.append(client_thread)
                    
                except Exception as e:
                    print(f"❌ Accept error: {e}")
                    
        except KeyboardInterrupt:
            print("\n🛑 Server stopping...")
        except Exception as e:
            print(f"❌ Server error: {e}")
        finally:
            server_socket.close()
            print("🛑 Server stopped")

if __name__ == "__main__":
    server = SimpleWebSocketServer()
    server.start_server()