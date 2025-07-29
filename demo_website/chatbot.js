/**
 * E-Care Chatbot Integration
 * Complete integration with the E-Care chatbot API
 */

class EChatbot {
    constructor() {
        this.baseURL = 'http://localhost:8000';  // Your FastAPI backend
        this.token = null;
        this.sessionId = this.generateSessionId();
        this.isTyping = false;
        this.messageQueue = [];
        
        console.log('🤖 E-Care Chatbot initialized');
        console.log('Session ID:', this.sessionId);
        
        this.initializeEventListeners();
        this.testConnection();
    }

    // Generate unique session ID
    generateSessionId() {
        return 'demo_session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    // Initialize all event listeners
    initializeEventListeners() {
        // Chat toggle button
        const chatToggle = document.getElementById('chat-toggle');
        const chatWidget = document.getElementById('chatbot-widget');
        const closeBtn = document.getElementById('close-btn');
        const minimizeBtn = document.getElementById('minimize-btn');
        const sendBtn = document.getElementById('send-btn');
        const chatInput = document.getElementById('chatbot-input');

        // Toggle chatbot
        chatToggle.addEventListener('click', () => {
            this.openChatbot();
        });

        // Close chatbot
        closeBtn.addEventListener('click', () => {
            this.closeChatbot();
        });

        // Minimize chatbot
        minimizeBtn.addEventListener('click', () => {
            this.minimizeChatbot();
        });

        // Send message on button click
        sendBtn.addEventListener('click', () => {
            this.sendMessage();
        });

        // Send message on Enter key
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Quick action buttons
        document.querySelectorAll('.quick-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const message = btn.getAttribute('data-message');
                this.sendQuickMessage(message);
            });
        });

        // Auto-resize input
        chatInput.addEventListener('input', () => {
            this.updateSendButton();
        });
    }

    // Test connection to backend
    async testConnection() {
        try {
            const response = await fetch(`${this.baseURL}/health`);
            if (response.ok) {
                console.log('✅ Backend connection successful');
                this.updateStatus('online');
            } else {
                console.log('⚠️ Backend responded with error');
                this.updateStatus('offline');
            }
        } catch (error) {
            console.log('❌ Backend connection failed:', error);
            this.updateStatus('offline');
            this.addMessage('bot', '⚠️ I\'m currently offline. Please try again later or contact us directly.', 'error');
        }
    }

    // Update chatbot status
    updateStatus(status) {
        const statusElement = document.getElementById('chatbot-status');
        if (status === 'online') {
            statusElement.textContent = 'Online';
            statusElement.className = 'status-online';
        } else {
            statusElement.textContent = 'Offline';
            statusElement.className = 'status-offline';
        }
    }

    // Get authentication token
    async authenticate() {
        try {
            console.log('🔐 Authenticating with backend...');
            
            const response = await fetch(`${this.baseURL}/auth/token`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    client_id: "ecare_client",
                    client_secret: "ecare_secret_key_2025"
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                this.token = data.access_token;
                console.log('✅ Authentication successful');
                return true;
            } else {
                const error = await response.text();
                console.error('❌ Authentication failed:', error);
                return false;
            }
        } catch (error) {
            console.error('❌ Authentication error:', error);
            return false;
        }
    }

    // Send message to chatbot
    async sendMessageToAPI(userMessage) {
        // Ensure we have authentication
        if (!this.token) {
            const authenticated = await this.authenticate();
            if (!authenticated) {
                throw new Error('Authentication failed');
            }
        }

        try {
            console.log('📤 Sending message:', userMessage);
            
            const response = await fetch(`${this.baseURL}/api/v1/ecare/chatbot`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.token}`
                },
                body: JSON.stringify({
                    message: userMessage,
                    session_id: this.sessionId,
                    user_id: "demo_website_user"
                })
            });

            if (response.ok) {
                const result = await response.json();
                console.log('📥 Received response:', result);
                return result;
            } else if (response.status === 401) {
                // Token expired, re-authenticate
                console.log('🔄 Token expired, re-authenticating...');
                this.token = null;
                const authenticated = await this.authenticate();
                if (authenticated) {
                    return await this.sendMessageToAPI(userMessage); // Retry
                } else {
                    throw new Error('Re-authentication failed');
                }
            } else {
                const error = await response.text();
                throw new Error(`API Error: ${error}`);
            }
        } catch (error) {
            console.error('❌ Message send failed:', error);
            throw error;
        }
    }

    // Open chatbot
    openChatbot() {
        const chatWidget = document.getElementById('chatbot-widget');
        const chatToggle = document.getElementById('chat-toggle');
        
        chatWidget.classList.add('active');
        chatToggle.style.display = 'none';
        
        // Focus on input after animation
        setTimeout(() => {
            document.getElementById('chatbot-input').focus();
        }, 300);
        
        // Hide notification badge
        const badge = document.querySelector('.notification-badge');
        if (badge) {
            badge.style.display = 'none';
        }
    }

    // Close chatbot
    closeChatbot() {
        const chatWidget = document.getElementById('chatbot-widget');
        const chatToggle = document.getElementById('chat-toggle');
        
        chatWidget.classList.remove('active');
        chatToggle.style.display = 'flex';
    }

    // Minimize chatbot
    minimizeChatbot() {
        this.closeChatbot();
    }

    // Send message from input
    async sendMessage() {
        const input = document.getElementById('chatbot-input');
        const message = input.value.trim();
        
        if (!message || this.isTyping) return;
        
        // Clear input
        input.value = '';
        this.updateSendButton();
        
        await this.sendQuickMessage(message);
    }

    // Send quick message
    async sendQuickMessage(message) {
        if (this.isTyping) return;
        
        this.isTyping = true;
        
        // Add user message
        this.addMessage('user', message);
        
        // Show typing indicator
        this.showTyping();
        
        try {
            // Send to API
            const response = await this.sendMessageToAPI(message);
            
            // Hide typing indicator
            this.hideTyping();
            
            // Add bot response
            this.addMessage('bot', response.message, 'response', {
                intent: response.intent,
                confidence: response.data?.confidence,
                source: response.data?.source
            });
            
        } catch (error) {
            this.hideTyping();
            
            // Add error message
            this.addMessage('bot', 
                '❌ Sorry, I encountered an error. Please try again or contact us directly at (555) 123-4567.', 
                'error'
            );
            
            console.error('Chatbot error:', error);
        }
        
        this.isTyping = false;
    }

    // Add message to chat
    addMessage(sender, content, type = 'normal', metadata = {}) {
        const messagesContainer = document.getElementById('chatbot-messages');
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;
        
        // Create avatar
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        
        if (sender === 'bot') {
            avatar.innerHTML = '<i class="fas fa-robot"></i>';
        } else {
            avatar.innerHTML = '<i class="fas fa-user"></i>';
        }
        
        // Create content
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        // Add main message
        const messageText = document.createElement('p');
        messageText.textContent = content;
        messageContent.appendChild(messageText);
        
        // Add metadata for bot responses
        if (sender === 'bot' && metadata.intent && type === 'response') {
            const metadataDiv = document.createElement('div');
            metadataDiv.className = 'message-metadata';
            metadataDiv.innerHTML = `
                <small style="opacity: 0.7; font-size: 0.7rem; margin-top: 0.5rem; display: block;">
                    Intent: ${metadata.intent} ${metadata.confidence ? `• Confidence: ${(metadata.confidence * 100).toFixed(1)}%` : ''}
                </small>
            `;
            messageContent.appendChild(metadataDiv);
        }
        
        // Error styling
        if (type === 'error') {
            messageContent.style.background = '#ffe6e6';
            messageContent.style.borderLeft = '4px solid #ff6b6b';
        }
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(messageContent);
        
        messagesContainer.appendChild(messageDiv);
        
        // Scroll to bottom
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        console.log(`💬 Added ${sender} message:`, content);
    }

    // Show typing indicator
    showTyping() {
        const messagesContainer = document.getElementById('chatbot-messages');
        
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message bot-message typing-indicator';
        typingDiv.id = 'typing-indicator';
        
        typingDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fas fa-robot"></i>
            </div>
            <div class="message-content">
                <div class="typing-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;
        
        messagesContainer.appendChild(typingDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        // Add typing dots animation
        const style = document.createElement('style');
        style.textContent = `
            .typing-dots {
                display: flex;
                gap: 4px;
                padding: 8px 0;
            }
            .typing-dots span {
                width: 8px;
                height: 8px;
                background: #666;
                border-radius: 50%;
                animation: typing 1.4s infinite ease-in-out;
            }
            .typing-dots span:nth-child(1) { animation-delay: -0.32s; }
            .typing-dots span:nth-child(2) { animation-delay: -0.16s; }
            @keyframes typing {
                0%, 80%, 100% { transform: scale(0.8); opacity: 0.5; }
                40% { transform: scale(1); opacity: 1; }
            }
        `;
        document.head.appendChild(style);
    }

    // Hide typing indicator
    hideTyping() {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }

    // Update send button state
    updateSendButton() {
        const input = document.getElementById('chatbot-input');
        const sendBtn = document.getElementById('send-btn');
        
        if (input.value.trim() && !this.isTyping) {
            sendBtn.disabled = false;
            sendBtn.style.opacity = '1';
        } else {
            sendBtn.disabled = true;
            sendBtn.style.opacity = '0.5';
        }
    }

    // Test different message types
    async testChatbot() {
        console.log('🧪 Starting chatbot tests...');
        
        const testMessages = [
            'What are your office hours?',  // RAG info
            'I want to book an appointment',  // Appointment
            'I need a prescription refill',  // Ticket
            'I have a headache, what should I do?'  // General
        ];
        
        for (let i = 0; i < testMessages.length; i++) {
            setTimeout(() => {
                this.sendQuickMessage(testMessages[i]);
            }, i * 3000);  // 3 second delay between messages
        }
    }
}

// Initialize chatbot when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Create global chatbot instance
    window.eChatbot = new EChatbot();
    
    console.log('🏥 E-Care Demo Website with Chatbot Ready!');
    
    // Add test button for development (can be removed for production)
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        const testBtn = document.createElement('button');
        testBtn.textContent = '🧪 Test Chatbot';
        testBtn.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #28a745;
            color: white;
            border: none;
            padding: 10px 15px;
            border-radius: 5px;
            cursor: pointer;
            z-index: 9999;
            font-size: 12px;
        `;
        testBtn.addEventListener('click', () => {
            window.eChatbot.testChatbot();
        });
        document.body.appendChild(testBtn);
    }
});

// Export for use in other scripts
window.EChatbot = EChatbot;
