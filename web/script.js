// ==================== SUPABASE AUTH & DATABASE ====================
let currentUser = null;
let supabaseClient = null;

// Initialize Supabase and auth
function initializeSupabase() {
    if (window.supabaseClient) {
        supabaseClient = window.supabaseClient;

        // Set up auth state listener
        supabaseClient.auth.onAuthStateChange((event, session) => {
            console.log('Auth state changed:', event);
            if (event === 'SIGNED_IN' && session) {
                currentUser = session.user;
                hideLoginModal();
                if (userInfo && userEmail) {
                    userEmail.textContent = currentUser.email;
                    userInfo.style.display = 'flex';
                }
                // Only init if not already initialized
                if (!window.appInitialized) {
                    window.appInitialized = true;
                    init();
                }
            } else if (event === 'SIGNED_OUT') {
                currentUser = null;
                if (userInfo) {
                    userInfo.style.display = 'none';
                }
                showLoginModal();
            }
        });

        // Check current session
        checkAuth();
    } else {
        console.error('Supabase client not found!');
    }

    // Add Google login button listener
    if (googleLoginBtn) {
        googleLoginBtn.addEventListener('click', signInWithGoogle);
    }

    // Add Sign out button listener
    if (signOutBtn) {
        signOutBtn.addEventListener('click', signOut);
    }
}

async function checkAuth() {
    if (!supabaseClient) return;

    const { data: { session }, error } = await supabaseClient.auth.getSession();
    if (error) {
        console.error('Error getting session:', error);
        showLoginModal();
        return;
    }

    if (session) {
        currentUser = session.user;
        console.log('User logged in:', currentUser.email);
        hideLoginModal();
        if (userInfo && userEmail) {
            userEmail.textContent = currentUser.email;
            userInfo.style.display = 'flex';
        }
        if (!window.appInitialized) {
            window.appInitialized = true;
            init();
        }
    } else {
        console.log('No active session');
        if (userInfo) {
            userInfo.style.display = 'none';
        }
        showLoginModal();
    }
}

function showLoginModal() {
    const loginOverlay = document.getElementById('login-overlay');
    if (loginOverlay) {
        loginOverlay.classList.add('show');
    }
}

function hideLoginModal() {
    const loginOverlay = document.getElementById('login-overlay');
    if (loginOverlay) {
        loginOverlay.classList.remove('show');
    }
}

async function signInWithGoogle() {
    if (!supabaseClient) {
        alert('Authentication not initialized. Please refresh the page.');
        return;
    }

    const { error } = await supabaseClient.auth.signInWithOAuth({
        provider: 'google',
        options: {
            redirectTo: window.location.origin
        }
    });

    if (error) {
        console.error('Error signing in:', error);
        alert('Failed to sign in: ' + error.message);
    }
}

async function signOut() {
    if (!supabaseClient) return;
    await supabaseClient.auth.signOut();
    location.reload();
}

// Initialize on window load
window.addEventListener('load', initializeSupabase);

// ==================== SUPABASE CONVERSATION STORAGE ====================

async function saveConversationToSupabase(conversation) {
    if (!currentUser) return;

    const { data, error } = await supabaseClient
        .from('conversations')
        .upsert({
            id: conversation.id,
            user_id: currentUser.id,
            title: conversation.title,
            messages: conversation.messages,
            updated_at: new Date().toISOString(),
            figure_id: conversation.figureId || null,
            figure_avatar: conversation.figureAvatar || '💬',
            figure_name: conversation.figureName || 'Unknown'
        })
        .select();

    if (error) {
        console.error('Error saving conversation:', error);
    }
    return data;
}

async function loadConversationsFromSupabase() {
    if (!currentUser) return [];

    const { data, error } = await supabaseClient
        .from('conversations')
        .select('*')
        .eq('user_id', currentUser.id)
        .order('updated_at', { ascending: false });

    if (error) {
        console.error('Error loading conversations:', error);
        return [];
    }
    return data || [];
}

async function deleteConversationFromSupabase(conversationId) {
    if (!currentUser) return;

    const { error } = await supabaseClient
        .from('conversations')
        .delete()
        .eq('id', conversationId)
        .eq('user_id', currentUser.id);

    if (error) {
        console.error('Error deleting conversation:', error);
    }
}

async function generateConversationTitle(firstMessage) {
    // Generate a smart, concise title based on the first user message
    if (!firstMessage || firstMessage.length === 0) {
        return 'New Conversation';
    }

    // For very short messages (greetings), generate descriptive title
    const lowerMsg = firstMessage.toLowerCase().trim();
    if (lowerMsg.length <= 10 || lowerMsg === 'hi' || lowerMsg === 'hello' || lowerMsg === 'hey') {
        return `Chat with ${currentFigure ? currentFigure.name : 'Historical Figure'}`;
    }

    // For short messages (under 35 chars), use them as-is
    if (firstMessage.length <= 35) {
        return firstMessage;
    }

    // Smart extraction: Remove common question starters and filler words
    let cleaned = firstMessage
        .replace(/^(what|how|why|when|where|who|can you|could you|would you|should|do you|tell me about|explain|help me with|help me understand|I need help with|I want to know|I'm wondering|I have a question about|can I ask about)\s+/gi, '')
        .replace(/\?$/g, '')
        .replace(/^(the|a|an)\s+/gi, '');

    // If we removed too much, use original
    if (cleaned.length < 10) {
        cleaned = firstMessage;
    }

    // Capitalize first letter
    cleaned = cleaned.charAt(0).toUpperCase() + cleaned.slice(1);

    // Limit to 45 characters for clean titles
    const title = cleaned.substring(0, 45).trim();

    // Add ellipsis only if we cut off in the middle of a word
    if (title.length < cleaned.length && !cleaned[title.length]?.match(/\s/)) {
        return title + '...';
    }

    return title.length < cleaned.length ? title + '...' : title;
}

// ==================== UUID GENERATOR (Browser Compatibility) ====================
function generateUUID() {
    // Use crypto.randomUUID if available (modern browsers)
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
        return crypto.randomUUID();
    }

    // Fallback: Generate UUID v4 manually
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// DOM Elements
const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const clearBtn = document.getElementById('clear-btn');
const newChatBtn = document.getElementById('new-chat-btn');
const toggleSidebarBtn = document.getElementById('toggle-sidebar-btn');
const mobileSidebarToggle = document.getElementById('mobile-sidebar-toggle');
const sidebar = document.getElementById('sidebar');
const sidebarCloseBtn = document.getElementById('sidebar-close-btn');
const sidebarOverlay = document.getElementById('sidebar-overlay');
const conversationList = document.getElementById('conversation-list');
const modeAuthenticBtn = document.getElementById('mode-authentic');
const modeParaphrasedBtn = document.getElementById('mode-paraphrased');
const languageSelector = document.getElementById('language-selector');
const figureCardsContainer = document.getElementById('figure-cards-container');
const figureSelectorOverlay = document.getElementById('figure-selector-overlay');
const changeFigureBtn = document.getElementById('change-figure-btn');
const currentFigureAvatar = document.getElementById('current-figure-avatar');
const currentFigureName = document.getElementById('current-figure-name');
const googleLoginBtn = document.getElementById('google-login-btn');
const userInfo = document.getElementById('user-info');
const userEmail = document.getElementById('user-email');
const signOutBtn = document.getElementById('sign-out-btn');

// API Configuration
const API_URL = 'http://84.8.128.149'; // Oracle VM deployment

// State
let currentConversationId = null;
let conversations = {};
let currentMode = 'authentic'; // 'authentic' or 'paraphrased'
let currentLanguage = 'en'; // Default language: English
let availableFigures = []; // List of available figures from API
let currentFigure = null; // Currently selected figure

// Initialize (called after successful login)
async function init() {
    // Create expand sidebar button for desktop
    createExpandSidebarButton();

    // Load figures from API
    await fetchFigures();

    // Load saved figure or show selector
    const savedFigureId = localStorage.getItem('historical_chat_figure');
    if (savedFigureId && availableFigures.find(f => f.id === savedFigureId)) {
        selectFigure(savedFigureId);
    } else {
        showFigureSelector();
    }

    // Load mode preference
    const savedMode = localStorage.getItem('historical_chat_mode');
    if (savedMode) {
        switchMode(savedMode);
    }

    // Load language preference
    const savedLanguage = localStorage.getItem('historical_chat_language');
    if (savedLanguage) {
        currentLanguage = savedLanguage;
        languageSelector.value = savedLanguage;
    }

    // Load conversations from Supabase
    await loadConversations();

    // Create new conversation if none exist
    if (Object.keys(conversations).length === 0) {
        createNewConversation();
    } else {
        // Load the most recent conversation
        const sortedConvos = Object.keys(conversations).sort((a, b) =>
            conversations[b].updatedAt - conversations[a].updatedAt
        );
        loadConversation(sortedConvos[0]);
    }

    // Render conversation list
    renderConversationList();

    // Event listeners
    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
    clearBtn.addEventListener('click', clearCurrentChat);
    newChatBtn.addEventListener('click', createNewConversation);
    toggleSidebarBtn.addEventListener('click', toggleSidebar);
    mobileSidebarToggle.addEventListener('click', toggleSidebar);
    sidebarCloseBtn.addEventListener('click', toggleSidebar);
    sidebarOverlay.addEventListener('click', toggleSidebar);
    modeAuthenticBtn.addEventListener('click', () => switchMode('authentic'));
    modeParaphrasedBtn.addEventListener('click', () => switchMode('paraphrased'));
    languageSelector.addEventListener('change', (e) => changeLanguage(e.target.value));
    changeFigureBtn.addEventListener('click', showFigureSelector);

    // Close button for figure selector
    const figureSelectorClose = document.getElementById('figure-selector-close');
    if (figureSelectorClose) {
        figureSelectorClose.addEventListener('click', hideFigureSelector);
    }
}

function hideFigureSelector() {
    if (figureSelectorOverlay) {
        figureSelectorOverlay.style.display = 'none';
    }
}

// ==================== FIGURE SELECTION ====================

async function fetchFigures() {
    try {
        const response = await fetch(API_URL + '/figures');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        
        if (data && Array.isArray(data.figures)) {
            availableFigures = data.figures;
        } else {
            console.error("API response did not contain a 'figures' array:", data);
            const container = document.getElementById('figure-cards-container');
            if (container) {
                container.innerHTML = '<p class="error-message">Could not load figures: Invalid API response.</p>';
            }
        }
    } catch (error) {
        console.error("Could not fetch figures:", error);
        const container = document.getElementById('figure-cards-container');
        if (container) {
            container.innerHTML = '<p class="error-message">Could not load figures. Make sure the API server is running and accessible.</p>';
        }
    }
}

function showFigureSelector() {
    if (!figureCardsContainer) return;

    figureCardsContainer.innerHTML = ''; // Clear existing cards

    // Filter out hidden figures
    const visibleFigures = availableFigures.filter(fig => !fig.hidden);

    visibleFigures.forEach(fig => {
        const card = document.createElement('div');
        card.className = 'figure-card';
        if (!fig.trained) {
            card.className += ' not-trained';
        }
        card.style.setProperty('--figure-color', fig.color);

        // Only allow click if trained
        if (fig.trained) {
            card.onclick = () => selectFigure(fig.id);
        } else {
            card.style.cursor = 'not-allowed';
            card.style.opacity = '0.7';
        }

        const trainedBadge = fig.trained
            ? ''
            : '<div class="coming-soon-badge">Coming Soon</div>';

        card.innerHTML = `
            ${trainedBadge}
            <div class="figure-avatar">${fig.avatar}</div>
            <div class="figure-name">${fig.name}</div>
            <div class="figure-role">${fig.role}</div>
            <div class="figure-description">${fig.description}</div>
        `;
        figureCardsContainer.appendChild(card);
    });

    if (figureSelectorOverlay) {
        figureSelectorOverlay.style.display = 'flex';
    }
}

async function selectFigure(figureId) {
    const figure = availableFigures.find(f => f.id === figureId);
    if (!figure) return;

    const previousFigureId = currentFigure?.id;

    // IMPORTANT: Save current conversation BEFORE switching figures
    if (previousFigureId && previousFigureId !== figureId && currentConversationId) {
        await saveConversations();
    }

    currentFigure = figure;
    localStorage.setItem('historical_chat_figure', figureId);

    // Update UI
    if (currentFigureAvatar) currentFigureAvatar.textContent = figure.avatar;
    if (currentFigureName) currentFigureName.textContent = figure.name;

    // Hide the figure selector
    if (figureSelectorOverlay) {
        figureSelectorOverlay.style.display = 'none';
    }

    // If switching figures, find or create a conversation for this figure
    if (previousFigureId !== figureId) {
        // Look for existing conversations with this figure
        const existingConv = Object.values(conversations).find(c => c.figureId === figureId);

        if (existingConv) {
            // Load existing conversation
            loadConversation(existingConv.id);
        } else {
            // Create new conversation for this figure
            await createNewConversation();
            const greeting = figure.greeting[currentLanguage] || figure.greeting['en'];
            chatBox.innerHTML = '';
            appendMessage('bot', greeting);
        }
    }

    // Re-render conversation list to show filtered results
    renderConversationList();
}


// Get greeting message based on language
function getGreetingMessage(language) {
    // This function is now dynamic based on the selected figure
    if (currentFigure && currentFigure.greeting) {
        return currentFigure.greeting[language] || currentFigure.greeting['en'];
    }
    // Fallback greeting
    return "Hello! Please select a figure to begin.";
}


// Language Change Handler
function changeLanguage(language) {
    currentLanguage = language;
    localStorage.setItem('historical_chat_language', language);

    // Update placeholder text based on language
    const placeholders = {
        'en': 'Ask a question...',
        'af': 'Vra \'n vraag...',
        'es': 'Haz una pregunta...',
        'fr': 'Posez une question...',
        'de': 'Stellen Sie eine Frage...',
        'pt': 'Faça uma pergunta...',
        'it': 'Fai una domanda...',
        'nl': 'Stel een vraag...',
        'ru': 'Задайте вопрос...',
        'zh': '提问...',
        'ja': '質問してください...',
        'ko': '질문하세요...',
        'ar': 'اطرح سؤالا...'
    };

    userInput.placeholder = placeholders[language] || 'Ask a question...';

    // Reload conversation to update greeting if on empty conversation
    if (currentConversationId) {
        const conversation = conversations[currentConversationId];
        if (conversation && conversation.messages.length === 0) {
            loadConversation(currentConversationId);
        }
    }
}

// Mode Switching
function switchMode(mode) {
    currentMode = mode;

    // Update button states
    if (mode === 'authentic') {
        modeAuthenticBtn.classList.add('active');
        modeParaphrasedBtn.classList.remove('active');
    } else {
        modeAuthenticBtn.classList.remove('active');
        modeParaphrasedBtn.classList.add('active');
    }

    // Save mode preference
    localStorage.setItem('historical_chat_mode', mode);

    // Reload current conversation to show mode-specific formatting
    if (currentConversationId) {
        loadConversation(currentConversationId);
    }
}

// Conversation Management
async function loadConversations() {
    const supabaseConversations = await loadConversationsFromSupabase();
    conversations = {};
    supabaseConversations.forEach(conv => {
        conversations[conv.id] = {
            id: conv.id,
            title: conv.title,
            messages: conv.messages,
            createdAt: new Date(conv.created_at).getTime(),
            updatedAt: new Date(conv.updated_at).getTime(),
            userId: conv.user_id,
            figureId: conv.figure_id || null,
            figureAvatar: conv.figure_avatar || '💬',
            figureName: conv.figure_name || 'Unknown'
        };
    });
}

async function saveConversations() {
    // Save current conversation to Supabase
    if (currentConversationId && conversations[currentConversationId]) {
        await saveConversationToSupabase(conversations[currentConversationId]);
    }
}

async function createNewConversation() {
    const id = generateUUID();
    const conversation = {
        id: id,
        title: currentFigure ? `Chat with ${currentFigure.name}` : 'New Conversation',
        messages: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
        userId: currentUser ? currentUser.id : null,
        figureId: currentFigure ? currentFigure.id : null,
        figureAvatar: currentFigure ? currentFigure.avatar : '💬',
        figureName: currentFigure ? currentFigure.name : 'Unknown'
    };

    conversations[id] = conversation;
    currentConversationId = id;

    await saveConversations();
    renderConversationList();
    loadConversation(id);

    // Close sidebar on mobile
    if (window.innerWidth <= 768) {
        sidebar.classList.remove('open');
        sidebarOverlay.classList.remove('open');
    }
}

function loadConversation(id) {
    currentConversationId = id;
    const conversation = conversations[id];

    if (!conversation) return;

    // Switch to conversation's figure if it has one and it's different from current
    if (conversation.figureId && conversation.figureId !== currentFigure?.id) {
        const figure = availableFigures.find(f => f.id === conversation.figureId);
        if (figure) {
            currentFigure = figure;
            localStorage.setItem('historical_chat_figure', figure.id);
            if (currentFigureAvatar) currentFigureAvatar.textContent = figure.avatar;
            if (currentFigureName) currentFigureName.textContent = figure.name;
        }
    }

    // Clear chat box
    chatBox.innerHTML = '';

    // Load messages
    if (conversation.messages.length === 0) {
        appendMessage('bot', getGreetingMessage(currentLanguage));
    } else {
        conversation.messages.forEach(msg => {
            if (msg.sources) {
                appendMessageWithSources(msg.sender, msg.text, msg.sources, msg.sourceCount, msg.copyrightSafe, msg.similarityScore);
            } else {
                appendMessage(msg.sender, msg.text);
            }
        });
    }

    // Update active state
    renderConversationList();
}

async function deleteConversation(id, event) {
    event.stopPropagation();

    if (!confirm('Delete this conversation?')) return;

    // Delete from Supabase
    await deleteConversationFromSupabase(id);

    delete conversations[id];

    // If deleting current conversation, create a new one
    if (currentConversationId === id) {
        if (Object.keys(conversations).length === 0) {
            await createNewConversation();
        } else {
            const sortedConvos = Object.keys(conversations).sort((a, b) =>
                conversations[b].updatedAt - conversations[a].updatedAt
            );
            loadConversation(sortedConvos[0]);
        }
    }

    renderConversationList();
}

function renderConversationList() {
    conversationList.innerHTML = '';

    // Sort conversations by updatedAt (most recent first)
    const sortedIds = Object.keys(conversations).sort((a, b) =>
        conversations[b].updatedAt - conversations[a].updatedAt
    );

    // Filter to show only current figure's conversations (or all if no figure selected)
    const filteredIds = currentFigure
        ? sortedIds.filter(id => conversations[id].figureId === currentFigure.id || !conversations[id].figureId)
        : sortedIds;

    if (filteredIds.length === 0) {
        const emptyMsg = document.createElement('div');
        emptyMsg.className = 'conversation-empty';
        emptyMsg.textContent = 'No conversations yet';
        conversationList.appendChild(emptyMsg);
        return;
    }

    filteredIds.forEach(id => {
        const conv = conversations[id];
        const item = document.createElement('div');
        item.className = 'conversation-item' + (id === currentConversationId ? ' active' : '');
        item.onclick = () => loadConversationWithFigure(id);

        const avatar = document.createElement('span');
        avatar.className = 'conversation-avatar';
        avatar.textContent = conv.figureAvatar || '💬';

        const titleContainer = document.createElement('div');
        titleContainer.className = 'conversation-title-container';

        const title = document.createElement('div');
        title.className = 'conversation-title';
        title.textContent = conv.title;

        const date = document.createElement('div');
        date.className = 'conversation-date';
        date.textContent = new Date(conv.updatedAt).toLocaleDateString();

        titleContainer.appendChild(title);
        titleContainer.appendChild(date);

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'conversation-delete';
        deleteBtn.innerHTML = '×';
        deleteBtn.onclick = (e) => deleteConversation(id, e);

        item.appendChild(deleteBtn);
        item.appendChild(avatar);
        item.appendChild(titleContainer);
        conversationList.appendChild(item);
    });
}

// Load conversation and switch to its figure if needed
function loadConversationWithFigure(id) {
    const conv = conversations[id];
    if (conv && conv.figureId && conv.figureId !== currentFigure?.id) {
        // Switch to conversation's figure
        const figure = availableFigures.find(f => f.id === conv.figureId);
        if (figure) {
            currentFigure = figure;
            localStorage.setItem('historical_chat_figure', figure.id);
            if (currentFigureAvatar) currentFigureAvatar.textContent = figure.avatar;
            if (currentFigureName) currentFigureName.textContent = figure.name;
        }
    }
    loadConversation(id);
}

async function updateConversationTitle(firstMessage) {
    const conversation = conversations[currentConversationId];
    if (conversation && conversation.messages.length === 1) { // First user message
        conversation.title = await generateConversationTitle(firstMessage);
        await saveConversations();
        renderConversationList();
    }
}

// Sidebar Toggle
function toggleSidebar() {
    if (window.innerWidth <= 768) {
        sidebar.classList.toggle('open');
        sidebarOverlay.classList.toggle('open');
    } else {
        sidebar.classList.toggle('collapsed');
        updateExpandButtonVisibility();
    }
}

// Show/hide expand button based on sidebar state
function updateExpandButtonVisibility() {
    const expandBtn = document.getElementById('expand-sidebar-btn');
    if (expandBtn) {
        if (sidebar.classList.contains('collapsed')) {
            expandBtn.style.display = 'flex';
        } else {
            expandBtn.style.display = 'none';
        }
    }
}

// Create expand sidebar button (called on init)
function createExpandSidebarButton() {
    const expandBtn = document.createElement('button');
    expandBtn.id = 'expand-sidebar-btn';
    expandBtn.className = 'expand-sidebar-btn';
    expandBtn.innerHTML = '☰';
    expandBtn.title = 'Show conversations';
    expandBtn.onclick = toggleSidebar;
    expandBtn.style.display = 'none'; // Hidden by default
    document.body.appendChild(expandBtn);
}

// Clear current chat
function clearCurrentChat() {
    if (!confirm('Clear all chat history? This will start a new conversation.')) {
        return;
    }

    const conversation = conversations[currentConversationId];
    if (conversation) {
        // Clear history on server
        fetch(API_URL + '/clear-history/' + conversation.userId, {
            method: 'POST',
        }).catch(error => console.error('Error clearing server history:', error));

        // Clear local conversation
        conversation.messages = [];
        conversation.updatedAt = Date.now();
        saveConversations();
        loadConversation(currentConversationId);
    }
}

// Send Message
async function sendMessage() {
    const question = userInput.value.trim();
    if (question === '') return;

    const conversation = conversations[currentConversationId];
    if (!conversation) return;

    // Ensure a figure is selected
    if (!currentFigure) {
        appendMessage('bot', 'Please select a historical figure to begin the conversation.');
        showFigureSelector();
        return;
    }

    // Add user message
    appendMessage('user', question);
    conversation.messages.push({ sender: 'user', text: question });

    // Update title if first message
    if (conversation.messages.length === 1) {
        await updateConversationTitle(question);
    }

    userInput.value = '';

    // Show loading
    const loadingDiv = appendMessage('bot', 'Thinking...');
    loadingDiv.classList.add('loading');

    // Send to API with current mode
    try {
        const response = await fetch(API_URL + '/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question: question,
                user_id: currentUser ? currentUser.id : conversation.userId,
                figure_id: currentFigure?.id || 'lrh',
                mode: currentMode,
                language: currentLanguage
            }),
        });

        const data = await response.json();
        loadingDiv.remove();

        // Add bot response
        appendMessageWithSources('bot', data.response, data.sources, data.source_count, data.copyright_safe, data.similarity_score);
        conversation.messages.push({
            sender: 'bot',
            text: data.response,
            sources: data.sources,
            sourceCount: data.source_count,
            copyrightSafe: data.copyright_safe,
            similarityScore: data.similarity_score
        });

        // Update conversation
        conversation.updatedAt = Date.now();
        await saveConversations();
        renderConversationList();
    } catch (error) {
        console.error('Error:', error);
        loadingDiv.remove();
        appendMessage('bot', 'Sorry, something went wrong. Please try again.');
    }
}

// Message Display Functions
function appendMessage(sender, message) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', `${sender}-message`);
    messageElement.innerText = message;
    chatBox.appendChild(messageElement);
    chatBox.scrollTop = chatBox.scrollHeight;
    return messageElement;
}

function appendMessageWithSources(sender, message, sources, sourceCount, copyrightSafe, similarityScore) {
    const messageContainer = document.createElement('div');
    messageContainer.classList.add('message-container');

    // Main message
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', `${sender}-message`);
    messageElement.innerText = message;
    messageContainer.appendChild(messageElement);

    // Copyright safety indicator (both modes)
    if (copyrightSafe !== null && copyrightSafe !== undefined) {
        const safetyIndicator = document.createElement('div');
        safetyIndicator.classList.add('copyright-indicator');

        if (copyrightSafe) {
            safetyIndicator.innerHTML = `✅ Copyright Safe (${Math.round((1 - similarityScore) * 100)}% different from source)`;
            safetyIndicator.classList.add('safe');
        } else {
            safetyIndicator.innerHTML = `⚠️ Warning: May be too similar to source (${Math.round(similarityScore * 100)}% similarity)`;
            safetyIndicator.classList.add('warning');
        }

        messageContainer.appendChild(safetyIndicator);
    }

    // Source citations
    if (sources && sources.length > 0) {
        const sourcesContainer = document.createElement('div');
        sourcesContainer.classList.add('sources-container');

        // Different header text based on mode
        const figureName = currentFigure ? currentFigure.name : 'historical';
        const headerText = currentMode === 'paraphrased'
            ? `📚 Citations: ${sourceCount} source${sourceCount > 1 ? 's' : ''}`
            : `📚 Sources: ${sourceCount} passage${sourceCount > 1 ? 's' : ''} from ${figureName}'s writings`;

        const sourcesHeader = document.createElement('div');
        sourcesHeader.classList.add('sources-header');
        sourcesHeader.innerHTML = `${headerText} <span class="toggle-icon">▼</span>`;
        sourcesHeader.onclick = function() {
            const content = sourcesContainer.querySelector('.sources-content');
            const icon = sourcesHeader.querySelector('.toggle-icon');
            if (content.style.display === 'none') {
                content.style.display = 'block';
                icon.innerText = '▲';
            } else {
                content.style.display = 'none';
                icon.innerText = '▼';
            }
        };
        sourcesContainer.appendChild(sourcesHeader);

        const sourcesContent = document.createElement('div');
        sourcesContent.classList.add('sources-content');
        sourcesContent.style.display = 'none';

        sources.forEach((source, index) => {
            const sourceItem = document.createElement('div');
            sourceItem.classList.add('source-item');

            const sourceNumber = document.createElement('div');
            sourceNumber.classList.add('source-number');
            sourceNumber.innerText = currentMode === 'paraphrased' ? `Citation ${index + 1}` : `Source ${index + 1}`;
            sourceItem.appendChild(sourceNumber);

            // Only show full text in authentic mode
            if (currentMode === 'authentic' && source.text) {
                const sourceText = document.createElement('div');
                sourceText.classList.add('source-text');
                sourceText.innerText = source.text;
                sourceItem.appendChild(sourceText);
            }

            const sourceInfo = document.createElement('div');
            sourceInfo.classList.add('source-info');
            sourceInfo.innerText = `📄 ${source.source}`;
            sourceItem.appendChild(sourceInfo);

            sourcesContent.appendChild(sourceItem);
        });

        sourcesContainer.appendChild(sourcesContent);
        messageContainer.appendChild(sourcesContainer);
    }

    chatBox.appendChild(messageContainer);
    chatBox.scrollTop = chatBox.scrollHeight;
    return messageContainer;
}
