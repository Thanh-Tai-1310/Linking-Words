import asyncio
import websockets
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WordChainServer:
    def __init__(self):
        self.clients = {}  # {websocket: {'username': str, 'score': int}}
        self.player_list = []
        self.used_words = []
        self.current_turn = 0
        self.game_started = False
        self.valid_words = {
            'apple', 'elephant', 'tiger', 'rabbit', 'tree', 'earth', 'house', 'egg',
            'game', 'moon', 'nice', 'easy', 'yellow', 'water', 'rice', 'eat',
            'ant', 'table', 'test', 'sun', 'new', 'wood', 'door', 'red', 'dog',
            'green', 'nine', 'day', 'year', 'run', 'night', 'tea', 'air', 'rat'
        }

    async def register_client(self, websocket):
        client_addr = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"New connection from {client_addr}")
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.process_message(websocket, data)
                except json.JSONDecodeError:
                    await self.send_error(websocket, "Invalid message format")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await self.send_error(websocket, "Server error")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client {client_addr} disconnected")
        except Exception as e:
            logger.error(f"Connection error {client_addr}: {e}")
        finally:
            await self.remove_client(websocket)

    async def process_message(self, websocket, message):
        msg_type = message.get('type')
        
        if msg_type == 'JOIN':
            await self.handle_join(websocket, message)
        elif msg_type == 'WORD':
            await self.handle_word(websocket, message)
        elif msg_type == 'PING':
            await self.send_message(websocket, {'type': 'PONG'})
        else:
            await self.send_error(websocket, f"Unknown message type: {msg_type}")

    async def handle_join(self, websocket, message):
        username = message.get('username', '').strip()

        if not username:
            await self.send_error(websocket, "Username cannot be empty")
            return
        
        if len(username) > 20:
            await self.send_error(websocket, "Username too long (max 20 characters)")
            return
            
        if username in [client['username'] for client in self.clients.values()]:
            await self.send_error(websocket, "Username already exists")
            return
        
        if len(self.clients) >= 5:
            await self.send_error(websocket, "Room is full (max 5 players)")
            return
        self.clients[websocket] = {
            'username': username,
            'score': 0
        }
        self.player_list.append(username)
        logger.info(f"Player {username} joined the game")
        await self.send_message(websocket, {
            'type': 'JOIN_SUCCESS',
            'username': username,
            'players': self.player_list.copy(),
            'used_words': self.used_words.copy(),
            'current_turn': self.current_turn,
            'game_started': self.game_started
        })
        await self.broadcast_game_state()
        if len(self.clients) >= 2 and not self.game_started:
            await self.start_game()

    async def handle_word(self, websocket, message):
        if not self.game_started:
            await self.send_error(websocket, "Game not started yet")
            return
            
        word = message.get('word', '').strip().lower()
        username = self.clients[websocket]['username']
        if self.player_list[self.current_turn] != username:
            await self.send_error(websocket, "Not your turn")
            return
        validation = self.validate_word(word)
        if not validation['valid']:
            await self.send_error(websocket, validation['reason'])
            return
        self.used_words.append({
            'word': word,
            'player': username,
            'timestamp': datetime.now().isoformat()
        })
        self.clients[websocket]['score'] += len(word)
        
        logger.info(f"Player {username} submitted word: {word}")
        self.next_turn()
        await self.send_message(websocket, {
            'type': 'WORD_ACCEPTED',
            'word': word,
            'score': len(word)
        })
        await self.broadcast_game_state()

    def validate_word(self, word):
        if not word:
            return {'valid': False, 'reason': 'Word cannot be empty'}
        
        if len(word) < 2:
            return {'valid': False, 'reason': 'Word must have at least 2 characters'}
            
        if word not in self.valid_words:
            return {'valid': False, 'reason': 'Word not in dictionary'}
        if any(w['word'] == word for w in self.used_words):
            return {'valid': False, 'reason': 'Word already used'}
        if self.used_words:
            last_word = self.used_words[-1]['word']
            last_char = last_word[-1].lower()
            first_char = word[0].lower()
            
            if last_char != first_char:
                return {
                    'valid': False, 
                    'reason': f'Word must start with "{last_char.upper()}"'
                }
        
        return {'valid': True}

    async def start_game(self):
        self.game_started = True
        self.current_turn = 0
        logger.info(f"Game started with {len(self.clients)} players!")
        await self.broadcast_game_state()

    def next_turn(self):
        self.current_turn = (self.current_turn + 1) % len(self.player_list)

    async def broadcast_game_state(self):
        game_state = {
            'type': 'GAME_STATE',
            'players': [
                {
                    'username': username,
                    'score': next((client['score'] for client in self.clients.values() 
                                 if client['username'] == username), 0)
                }
                for username in self.player_list
            ],
            'used_words': self.used_words.copy(),
            'current_turn': self.current_turn,
            'current_player': self.player_list[self.current_turn] if self.player_list else None,
            'game_started': self.game_started,
            'total_words': len(self.used_words)
        }
        
        await self.broadcast(game_state)

    async def broadcast(self, message):
        if not self.clients:
            return
            
        disconnected_clients = []
        
        for websocket in list(self.clients.keys()):
            try:
                await self.send_message(websocket, message)
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.append(websocket)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")
                disconnected_clients.append(websocket)
        for websocket in disconnected_clients:
            await self.remove_client(websocket)

    async def send_message(self, websocket, message):
        try:
            data = json.dumps(message, ensure_ascii=False)
            await websocket.send(data)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise

    async def send_error(self, websocket, error_message):
        await self.send_message(websocket, {
            'type': 'ERROR',
            'message': error_message
        })

    async def remove_client(self, websocket):
        if websocket in self.clients:
            username = self.clients[websocket]['username']
            logger.info(f"Player {username} left the game")
            del self.clients[websocket]
            if username in self.player_list:
                # Adjust current_turn if needed
                removed_index = self.player_list.index(username)
                if removed_index < self.current_turn:
                    self.current_turn -= 1
                elif removed_index == self.current_turn:
                    if self.current_turn >= len(self.player_list) - 1:
                        self.current_turn = 0
                
                self.player_list.remove(username)
            if len(self.clients) < 2:
                self.game_started = False
                self.current_turn = 0
                logger.info("Game paused - not enough players")
            if self.clients:
                await self.broadcast_game_state()

async def main():
    server = WordChainServer()
    host = "localhost"
    port = 8765
    
    logger.info(f"Starting WebSocket server at {host}:{port}")
    
    try:
        async with websockets.serve(server.register_client, host, port):
            logger.info(f"Server running at ws://{host}:{port}")
            logger.info("Waiting for connections...")
            await asyncio.Future()  # Run forever
            
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
