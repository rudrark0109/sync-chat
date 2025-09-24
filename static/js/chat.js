document.addEventListener('DOMContentLoaded', function() {
    const socket = io();
    
    const userList = document.querySelector('.user-list');
    const messagesContainer = document.getElementById('messages-container');
    const chatWithUsername = document.getElementById('chat-with-username');
    const messageForm = document.getElementById('message-form');
    const messageInput = document.getElementById('message-input');
    const currentUserId = document.querySelector('.chat-container').dataset.currentUserId;
    const userSearchInput = document.getElementById('user-search');

    let activeRecipientId = null;

    function addUserToList(user) {
        const li = document.createElement('li');
        li.className = 'user-list-item';
        li.dataset.userId = user.id;
        li.dataset.username = user.username;
        li.textContent = user.username;

        li.addEventListener('click', function() {
            activeRecipientId = this.dataset.userId;
            const username = this.dataset.username;

            document.querySelectorAll('.user-list-item').forEach(el => el.classList.remove('active'));
            this.classList.add('active');

            chatWithUsername.textContent = 'Chat with ' + username;
            messageForm.style.display = 'flex';
            
            const unreadSpan = this.querySelector('.unread-count');
            if (unreadSpan) { unreadSpan.remove(); }
            
            fetchMessages(activeRecipientId);
        });
        userList.appendChild(li);
    }

    socket.on('connect', () => {
        console.log('Socket.IO connected successfully!');
    });

    socket.on('new_user_joined', function(newUser) {
        console.log('Received new_user_joined event:', newUser); 
        addUserToList(newUser);
    });

    socket.on('online_status_update', function(onlineUserIds) {
        document.querySelectorAll('.user-list-item').forEach(item => {
            const userId = item.dataset.userId;
            if (onlineUserIds.includes(parseInt(userId))) {
                item.classList.add('online');
            } else {
                item.classList.remove('online');
            }
        });
    });

    socket.on('new_message', function(data) {
        if (data.sender_id === parseInt(activeRecipientId)) {
            appendMessage(data);
        } else {
            const userListItem = document.querySelector(`.user-list-item[data-user-id='${data.sender_id}']`);
            if (userListItem) {
                let unreadSpan = userListItem.querySelector('.unread-count');
                if (!unreadSpan) {
                    unreadSpan = document.createElement('span');
                    unreadSpan.className = 'unread-count';
                    userListItem.appendChild(unreadSpan);
                }
                let currentCount = parseInt(unreadSpan.textContent || '0');
                unreadSpan.textContent = currentCount + 1;
            }
        }
    });

    document.querySelectorAll('.user-list-item').forEach(item => {
        item.addEventListener('click', function() {
            activeRecipientId = this.dataset.userId;
            const username = this.dataset.username;
            document.querySelectorAll('.user-list-item').forEach(el => el.classList.remove('active'));
            this.classList.add('active');
            chatWithUsername.textContent = 'Chat with ' + username;
            messageForm.style.display = 'flex';
            const unreadSpan = this.querySelector('.unread-count');
            if (unreadSpan) { unreadSpan.remove(); }
            fetchMessages(activeRecipientId);
        });
    });
    
    userSearchInput.addEventListener('keyup', function() {
        const searchTerm = this.value.toLowerCase();
        document.querySelectorAll('.user-list-item').forEach(item => {
            const username = item.dataset.username.toLowerCase();
            if (username.includes(searchTerm)) {
                item.style.display = '';
            } else {
                item.style.display = 'none';
            }
        });
    });

    messageForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const message = messageInput.value.trim();
        if (message && activeRecipientId) {
            socket.emit('private_message', {
                'recipient_id': parseInt(activeRecipientId),
                'message': message
            });
            const messageData = { sender_id: parseInt(currentUserId), content: message, is_media: false };
            appendMessage(messageData);
            messageInput.value = '';
        }
    });
    
    async function fetchMessages(userId) {
        const response = await fetch('/get_messages/' + userId);
        const messages = await response.json();
        displayMessages(messages);
    }

    function displayMessages(messages) {
        messagesContainer.innerHTML = '';
        messages.forEach(msg => appendMessage(msg));
    }

    function appendMessage(msg) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message');
        if (msg.sender_id === parseInt(currentUserId)) {
            messageDiv.classList.add('sent');
        } else {
            messageDiv.classList.add('received');
        }
        const contentDiv = document.createElement('div');
        contentDiv.classList.add('content');
        if (msg.is_media) {
            const image = document.createElement('img');
            image.src = msg.content;
            image.style.maxWidth = '200px';
            image.style.borderRadius = '10px';
            contentDiv.appendChild(image);
        } else {
            contentDiv.textContent = msg.content;
        }
        messageDiv.appendChild(contentDiv);
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
});