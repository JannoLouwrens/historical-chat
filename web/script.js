const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');

const API_URL = 'YOUR_API_URL'; // Replace with your Render API URL

sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

function sendMessage() {
    const question = userInput.value.trim();
    if (question === '') return;

    appendMessage('user', question);
    userInput.value = '';

    fetch(API_URL + '/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ question: question, user_id: 'webapp-user' }),
    })
    .then(response => response.json())
    .then(data => {
        appendMessage('bot', data.response);
    })
    .catch(error => {
        console.error('Error:', error);
        appendMessage('bot', 'Sorry, something went wrong.');
    });
}

function appendMessage(sender, message) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', `${sender}-message`);
    messageElement.innerText = message;
    chatBox.appendChild(messageElement);
    chatBox.scrollTop = chatBox.scrollHeight;
}
