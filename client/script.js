class WordChainClient {
    constructor() {
        this.ws = null;
        this.connected = false;
        this.username = '';
        this.gameState = {
            players: [],
            usedWords: [],
            currentTurn: 0,
            currentPlayer: null,
            gameStarted: false,
            totalWords: 0
        };
        
        this.initializeEventListeners();
    }

    initializeEventListeners() {
        document.getElementById('username').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') connectToServer();
        });
        
        document.getElementById('server-host').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') connectToServer();
        });
        
        document.getElementById('server-port').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') connectToServer();
        });

        document.getElementById('word-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.target.disabled) {
                submitWord();
            }
        });
        document.getElementById('word-input').addEventListener('input', (e) => {
            this.validateWordInput(e.target.value);
        });
    }

    connect(host, port, username) {
        try {
            const wsUrl = `ws://${host}:8765`;
            this.ws = new WebSocket(wsUrl);
            
            this.updateConnectionStatus('Đang kết nối...', 'waiting');
            this.addLogEntry(`Đang kết nối đến ${wsUrl}...`, 'info');
            this.ws.onopen = () => {
                this.connected = true;
                this.username = username;
                this.updateConnectionStatus('Đã kết nối', 'connected');
                this.addLogEntry(' Kết nối WebSocket thành công!', 'success');
                this.sendMessage({
                    type: 'JOIN',
                    username: username
                });
                
                this.showGameSection();
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    this.handleMessage(message);
                } catch (error) {
                    console.error('Error parsing message:', error);
                    this.addLogEntry(' Lỗi phân tích tin nhắn từ server', 'error');
                }
            };
            
            this.ws.onclose = (event) => {
                this.connected = false;
                this.updateConnectionStatus('Đã ngắt kết nối', 'disconnected');
                
                if (event.wasClean) {
                    this.addLogEntry(' Đã ngắt kết nối khỏi server', 'system');
                } else {
                    this.addLogEntry(' Mất kết nối đến server', 'error');
                }
                
                this.disableWordInput();
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.addLogEntry(' Lỗi kết nối WebSocket', 'error');
                this.updateConnectionStatus('Lỗi kết nối', 'disconnected');
            };
            
        } catch (error) {
            this.showError('Không thể kết nối đến server: ' + error.message);
            console.error('Connection error:', error);
        }
    }

    handleMessage(message) {
        const type = message.type;
        
        switch (type) {
            case 'JOIN_SUCCESS':
                this.handleJoinSuccess(message);
                break;
                
            case 'GAME_STATE':
                this.handleGameState(message);
                break;
                
            case 'WORD_ACCEPTED':
                this.handleWordAccepted(message);
                break;
                
            case 'ERROR':
                this.handleError(message);
                break;
                
            case 'PONG':
                // Heartbeat response
                break;
                
            default:
                console.log('Unknown message type:', type, message);
        }
    }

    handleJoinSuccess(message) {
        this.addLogEntry(` Đã tham gia game với tên ${message.username}!`, 'success');
        
        // Update initial game state
        this.gameState.players = message.players.map(username => ({
            username: username,
            score: 0
        }));
        this.gameState.usedWords = message.used_words || [];
        this.gameState.currentTurn = message.current_turn || 0;
        this.gameState.gameStarted = message.game_started || false;
        
        this.updateUI();
        
        if (this.gameState.gameStarted) {
            const currentPlayer = this.gameState.players[this.gameState.currentTurn];
            if (currentPlayer && currentPlayer.username === this.username) {
                this.enableWordInput();
                this.addLogEntry(' Đến lượt bạn!', 'info');
            } else {
                this.addLogEntry(' Đang chờ lượt...', 'info');
            }
        } else {
            this.addLogEntry(' Đang chờ game bắt đầu...', 'info');
        }
    }

    handleGameState(message) {
        // Update game state
        this.gameState.players = message.players || [];
        this.gameState.usedWords = message.used_words || [];
        this.gameState.currentTurn = message.current_turn || 0;
        this.gameState.currentPlayer = message.current_player;
        this.gameState.gameStarted = message.game_started || false;
        this.gameState.totalWords = message.total_words || 0;
        
        this.updateUI();
        if (this.gameState.gameStarted) {
            if (this.gameState.currentPlayer === this.username) {
                this.enableWordInput();
                this.addLogEntry(' Đến lượt bạn!', 'info');
            } else {
                this.disableWordInput();
                this.addLogEntry(` Đến lượt ${this.gameState.currentPlayer}...`, 'info');
            }
        }
    }

    handleWordAccepted(message) {
        this.addLogEntry(` Từ "${message.word}" được chấp nhận! (+${message.score} điểm)`, 'success');
        document.getElementById('word-input').value = '';
    }

    handleError(message) {
        this.showError(message.message);
        this.addLogEntry(` ${message.message}`, 'error');
    }

    sendMessage(message) {
        if (!this.connected || !this.ws) {
            this.showError('Chưa kết nối đến server');
            return false;
        }
        
        try {
            this.ws.send(JSON.stringify(message));
            return true;
        } catch (error) {
            console.error('Error sending message:', error);
            this.showError('Lỗi gửi tin nhắn');
            return false;
        }
    }

    submitWord(word) {
        if (!word) {
            word = document.getElementById('word-input').value.trim();
        }
        
        if (!word) {
            this.showError('Vui lòng nhập từ!');
            return;
        }

        if (!this.gameState.gameStarted) {
            this.showError('Game chưa bắt đầu!');
            return;
        }

        if (this.gameState.currentPlayer !== this.username) {
            this.showError('Chưa đến lượt bạn!');
            return;
        }
        const btn = document.getElementById('submit-word-btn');
        const btnText = document.getElementById('btn-text');
        const btnLoading = document.getElementById('btn-loading');
        
        btn.disabled = true;
        btnText.classList.add('hidden');
        btnLoading.classList.remove('hidden');
        this.sendMessage({
            type: 'WORD',
            word: word
        });
        setTimeout(() => {
            btn.disabled = false;
            btnText.classList.remove('hidden');
            btnLoading.classList.add('hidden');
        }, 1000);
    }

    validateWordInput(word) {
        const input = document.getElementById('word-input');
        
        if (!this.gameState.gameStarted || !word) {
            input.style.borderColor = '#ddd';
            input.style.boxShadow = 'none';
            return;
        }
        if (this.gameState.usedWords.length > 0) {
            const lastWord = this.gameState.usedWords[this.gameState.usedWords.length - 1].word;
            const lastChar = lastWord.charAt(lastWord.length - 1).toLowerCase();
            const firstChar = word.charAt(0).toLowerCase();
            
            if (lastChar !== firstChar) {
                input.style.borderColor = '#dc3545';
                input.style.boxShadow = '0 0 0 3px rgba(220, 53, 69, 0.1)';
            } else {
                input.style.borderColor = '#28a745';
                input.style.boxShadow = '0 0 0 3px rgba(40, 167, 69, 0.1)';
            }
        }
        if (this.gameState.usedWords.some(w => w.word.toLowerCase() === word.toLowerCase())) {
            input.style.borderColor = '#ffc107';
            input.style.boxShadow = '0 0 0 3px rgba(255, 193, 7, 0.1)';
        }
    }

    enableWordInput() {
        const input = document.getElementById('word-input');
        const btn = document.getElementById('submit-word-btn');
        const title = document.getElementById('input-title');
        
        input.disabled = false;
        btn.disabled = false;
        title.textContent = ' Lượt của bạn - Nhập từ';
        
        input.focus();
        if (this.gameState.usedWords.length > 0) {
            const lastWord = this.gameState.usedWords[this.gameState.usedWords.length - 1].word;
            const lastChar = lastWord.charAt(lastWord.length - 1).toUpperCase();
            
            document.getElementById('required-char').textContent = lastChar;
            document.getElementById('word-hint').classList.remove('hidden');
        }
    }

    disableWordInput() {
        const input = document.getElementById('word-input');
        const btn = document.getElementById('submit-word-btn');
        const title = document.getElementById('input-title');
        
        input.disabled = true;
        btn.disabled = true;
        input.value = '';
        title.textContent = ' Chờ lượt của bạn';
        
        document.getElementById('word-hint').classList.add('hidden');
        input.style.borderColor = '#ddd';
        input.style.boxShadow = 'none';
    }

    updateUI() {
        this.updatePlayersDisplay();
        this.updateWordChain();
        this.updateGameStats();
    }

    updatePlayersDisplay() {
        const container = document.getElementById('players-container');
        
        if (this.gameState.players.length === 0) {
            container.innerHTML = '<div class="no-players">Chưa có người chơi nào...</div>';
            return;
        }

        container.innerHTML = this.gameState.players.map((player, index) => {
            const isCurrentTurn = index === this.gameState.currentTurn && this.gameState.gameStarted;
            const isMe = player.username === this.username;
            
            let classes = 'player-card';
            if (isCurrentTurn) classes += ' current-turn';
            if (isMe) classes += ' me';

            return `
                <div class="${classes}">
                    <div class="player-name">
                        ${player.username}${isMe ? ' (Bạn)' : ''}
                    </div>
                    <div class="player-score">${player.score} điểm</div>
                    ${isCurrentTurn ? '<div class="turn-indicator">▶</div>' : ''}
                </div>
            `;
        }).join('');
    }

    updateWordChain() {
        const container = document.getElementById('word-chain');
        
        if (this.gameState.usedWords.length === 0) {
            container.innerHTML = '<div class="no-words">Chưa có từ nào...</div>';
            return;
        }

        container.innerHTML = this.gameState.usedWords.map((wordData, index) => `
            <div class="word-item" title="Bởi ${wordData.player}">
                ${wordData.word}
            </div>
        `).join('');
        container.scrollLeft = container.scrollWidth;
    }

    updateGameStats() {
        document.getElementById('total-words').textContent = this.gameState.usedWords.length;
        document.getElementById('total-players').textContent = this.gameState.players.length;
    }

    updateConnectionStatus(message, type) {
        const statusEl = document.getElementById('connection-status');
        statusEl.textContent = message;
        statusEl.className = `status ${type}`;
    }

    showGameSection() {
        document.getElementById('connection-section').classList.add('hidden');
        document.getElementById('game-section').classList.remove('hidden');
    }

    addLogEntry(message, type = 'info') {
        const log = document.getElementById('game-log');
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        
        const timestamp = new Date().toLocaleTimeString();
        entry.textContent = `[${timestamp}] ${message}`;
        
        log.appendChild(entry);
        log.scrollTop = log.scrollHeight;
        while (log.children.length > 100) {
            log.removeChild(log.firstChild);
        }
    }

    showError(message) {
        this.showToast(message, 'error');
    }

    showToast(message, type = 'info') {
        const toast = document.getElementById('toast');
        const messageEl = document.getElementById('toast-message');
        
        messageEl.textContent = message;
        toast.className = `toast ${type}`;
        toast.classList.remove('hidden');
        setTimeout(() => {
            this.hideToast();
        }, 5000);
    }

    hideToast() {
        document.getElementById('toast').classList.add('hidden');
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
        
        this.connected = false;
        document.getElementById('connection-section').classList.remove('hidden');
        document.getElementById('game-section').classList.add('hidden');
        this.gameState = {
            players: [],
            usedWords: [],
            currentTurn: 0,
            currentPlayer: null,
            gameStarted: false,
            totalWords: 0
        };
    }

    clearLog() {
        document.getElementById('game-log').innerHTML = '';
    }
    startHeartbeat() {
        setInterval(() => {
            if (this.connected) {
                this.sendMessage({ type: 'PING' });
            }
        }, 30000);
    }
}
const gameClient = new WordChainClient();
function connectToServer() {
    const host = document.getElementById('server-host').value.trim() || 'localhost';
    const port = parseInt(document.getElementById('server-port').value) || 8765;
    const username = document.getElementById('username').value.trim();
    
    if (!username) {
        gameClient.showError('Vui lòng nhập tên người chơi!');
        return;
    }
    
    if (username.length > 20) {
        gameClient.showError('Tên người chơi quá dài (tối đa 20 ký tự)!');
        return;
    }
    
    gameClient.connect(host, port, username);
}

function submitWord() {
    gameClient.submitWord();
}

function disconnect() {
    gameClient.disconnect();
}

function clearLog() {
    gameClient.clearLog();
}

function hideToast() {
    gameClient.hideToast();
}
document.addEventListener('DOMContentLoaded', () => {
    gameClient.startHeartbeat();
});
