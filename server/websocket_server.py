import asyncio
import websockets
import json
import logging
from datetime import datetime

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WordChainServer:
    def __init__(self):
        self.clients = {}  # {websocket: {'username': str, 'score': int}}
        self.player_list = []  # Ordered list of usernames
        self.used_words = []
        self.current_turn = 0
        self.game_started = False
        
        # Từ điển mẫu
        self.valid_words = {
            'bàn', 'nước', 'cây', 'yêu', 'uống', 'gà', 'ăn', 'ngọt', 'tốt', 'táo',
            'ong', 'gấu', 'ủng', 'ghế', 'ếch', 'chó', 'ót', 'tím', 'mèo', 'ở',
            'apple', 'elephant', 'tiger', 'rabbit', 'tree', 'earth', 'house', 'egg',
            'game', 'moon', 'nice', 'easy', 'yellow', 'water', 'rice', 'eat',
            'ant', 'table', 'test', 'sun', 'new', 'wood', 'door', 'end',
            'red', 'dog', 'green', 'nine', 'day', 'year', 'run', 'night'
        }

    async def register_client(self, websocket, path):
        """Xử lý kết nối WebSocket mới"""
        client_addr = websocket.remote_address
        logger.info(f"📱 Kết nối mới từ {client_addr}")
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.process_message(websocket, data)
                except json.JSONDecodeError:
                    await self.send_error(websocket, "Định dạng tin nhắn không hợp lệ")
                except Exception as e:
                    logger.error(f"Lỗi xử lý tin nhắn: {e}")
                    await self.send_error(websocket, "Lỗi server")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"📱 Client {client_addr} đã ngắt kết nối")
        except Exception as e:
            logger.error(f"❌ Lỗi kết nối {client_addr}: {e}")
        finally:
            await self.remove_client(websocket)

    async def process_message(self, websocket, message):
        """Xử lý tin nhắn từ client"""
        msg_type = message.get('type')
        
        if msg_type == 'JOIN':
            await self.handle_join(websocket, message)
        elif msg_type == 'WORD':
            await self.handle_word(websocket, message)
        elif msg_type == 'PING':
            await self.send_message(websocket, {'type': 'PONG'})
        else:
            await self.send_error(websocket, f"Loại tin nhắn không hợp lệ: {msg_type}")

    async def handle_join(self, websocket, message):
        """Xử lý yêu cầu tham gia game"""
        username = message.get('username', '').strip()
        
        # Validation
        if not username:
            await self.send_error(websocket, "Tên người chơi không được để trống")
            return
        
        if len(username) > 20:
            await self.send_error(websocket, "Tên người chơi quá dài (tối đa 20 ký tự)")
            return
            
        if username in [client['username'] for client in self.clients.values()]:
            await self.send_error(websocket, "Tên người chơi đã tồn tại")
            return
        
        if len(self.clients) >= 5:
            await self.send_error(websocket, "Phòng đã đầy (tối đa 5 người chơi)")
            return

        # Thêm client
        self.clients[websocket] = {
            'username': username,
            'score': 0
        }
        self.player_list.append(username)
        
        logger.info(f"✅ {username} đã tham gia game")
        
        # Gửi thông báo tham gia thành công
        await self.send_message(websocket, {
            'type': 'JOIN_SUCCESS',
            'username': username,
            'players': self.player_list.copy(),
            'used_words': self.used_words.copy(),
            'current_turn': self.current_turn,
            'game_started': self.game_started
        })
        
        # Broadcast cho tất cả client
        await self.broadcast_game_state()
        
        # Bắt đầu game nếu đủ người chơi
        if len(self.clients) >= 2 and not self.game_started:
            await self.start_game()

    async def handle_word(self, websocket, message):
        """Xử lý từ được gửi"""
        if not self.game_started:
            await self.send_error(websocket, "Game chưa bắt đầu")
            return
            
        word = message.get('word', '').strip().lower()
        username = self.clients[websocket]['username']
        
        # Kiểm tra lượt chơi
        if self.player_list[self.current_turn] != username:
            await self.send_error(websocket, "Chưa đến lượt của bạn")
            return
        
        # Validate từ
        validation = self.validate_word(word)
        if not validation['valid']:
            await self.send_error(websocket, validation['reason'])
            return
        
        # Thêm từ vào danh sách
        self.used_words.append({
            'word': word,
            'player': username,
            'timestamp': datetime.now().isoformat()
        })
        
        # Tăng điểm
        self.clients[websocket]['score'] += len(word)
        
        logger.info(f"✅ {username}: {word}")
        
        # Chuyển lượt
        self.next_turn()
        
        # Gửi phản hồi thành công
        await self.send_message(websocket, {
            'type': 'WORD_ACCEPTED',
            'word': word,
            'score': len(word)
        })
        
        # Broadcast trạng thái mới
        await self.broadcast_game_state()

    def validate_word(self, word):
        """Kiểm tra tính hợp lệ của từ"""
        if not word:
            return {'valid': False, 'reason': 'Từ không được để trống'}
        
        if len(word) < 2:
            return {'valid': False, 'reason': 'Từ phải có ít nhất 2 ký tự'}
            
        if word not in self.valid_words:
            return {'valid': False, 'reason': 'Từ không có trong từ điển'}
        
        # Kiểm tra trùng lặp
        if any(w['word'] == word for w in self.used_words):
            return {'valid': False, 'reason': 'Từ đã được sử dụng'}
        
        # Kiểm tra quy tắc nối từ
        if self.used_words:
            last_word = self.used_words[-1]['word']
            last_char = last_word[-1].lower()
            first_char = word[0].lower()
            
            if last_char != first_char:
                return {
                    'valid': False, 
                    'reason': f'Từ phải bắt đầu bằng chữ "{last_char.upper()}"'
                }
        
        return {'valid': True}

    async def start_game(self):
        """Bắt đầu game"""
        self.game_started = True
        self.current_turn = 0
        logger.info(f"🎮 Game bắt đầu với {len(self.clients)} người chơi!")
        await self.broadcast_game_state()

    def next_turn(self):
        """Chuyển sang lượt tiếp theo"""
        self.current_turn = (self.current_turn + 1) % len(self.player_list)

    async def broadcast_game_state(self):
        """Broadcast trạng thái game cho tất cả client"""
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
        """Gửi tin nhắn đến tất cả client"""
        if not self.clients:
            return
            
        disconnected_clients = []
        
        for websocket in list(self.clients.keys()):
            try:
                await self.send_message(websocket, message)
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.append(websocket)
            except Exception as e:
                logger.error(f"Lỗi broadcast đến client: {e}")
                disconnected_clients.append(websocket)
        
        # Xóa client đã ngắt kết nối
        for websocket in disconnected_clients:
            await self.remove_client(websocket)

    async def send_message(self, websocket, message):
        """Gửi tin nhắn đến một client"""
        try:
            data = json.dumps(message, ensure_ascii=False)
            await websocket.send(data)
        except Exception as e:
            logger.error(f"❌ Lỗi gửi tin nhắn: {e}")
            raise

    async def send_error(self, websocket, error_message):
        """Gửi tin nhắn lỗi đến client"""
        await self.send_message(websocket, {
            'type': 'ERROR',
            'message': error_message
        })

    async def remove_client(self, websocket):
        """Xóa client khỏi game"""
        if websocket in self.clients:
            username = self.clients[websocket]['username']
            logger.info(f"👋 {username} đã rời khỏi game")
            
            # Xóa khỏi danh sách
            del self.clients[websocket]
            if username in self.player_list:
                # Điều chỉnh current_turn nếu cần
                removed_index = self.player_list.index(username)
                if removed_index < self.current_turn:
                    self.current_turn -= 1
                elif removed_index == self.current_turn:
                    if self.current_turn >= len(self.player_list) - 1:
                        self.current_turn = 0
                
                self.player_list.remove(username)
            
            # Reset game nếu không đủ người chơi
            if len(self.clients) < 2:
                self.game_started = False
                self.current_turn = 0
                logger.info("⏸️ Game tạm dừng - không đủ người chơi")
            
            # Broadcast trạng thái mới
            if self.clients:
                await self.broadcast_game_state()

async def main():
    # Tạo server instance
    server = WordChainServer()
    
    # Khởi động WebSocket server
    host = "localhost"
    port = 8765
    
    logger.info(f"🚀 Đang khởi động WebSocket server tại {host}:{port}")
    
    try:
        async with websockets.serve(server.register_client, host, port):
            logger.info(f"✅ Server đã khởi động tại ws://{host}:{port}")
            logger.info("Đang chờ người chơi kết nối...")
            
            # Chạy server vĩnh viễn
            await asyncio.Future()  # Run forever
            
    except KeyboardInterrupt:
        logger.info("🔴 Nhận tín hiệu dừng server...")
    except Exception as e:
        logger.error(f"❌ Lỗi server: {e}")

if __name__ == "__main__":
    asyncio.run(main())