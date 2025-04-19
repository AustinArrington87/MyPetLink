console.log('pet_app.js loaded');

// Array of pet-related loading GIFs
const loadingGifs = [
    '/static/img/GIFs/cleo.gif',
    '/static/img/GIFs/spot.gif'
];

// Suggested prompts based on context
const suggestedPrompts = {
    default: [
        "What vaccinations does my pet need?",
        "How often should I feed my pet?",
        "What are signs of a healthy pet?"
    ],
    healthConcerns: [
        "Has your pet's appetite changed recently?",
        "Is your pet drinking more water than usual?",
        "Have you noticed any changes in energy level?"
    ],
    poopAnalysis: [
        "What color is normal for pet poop?",
        "How often should my pet poop?",
        "What does runny poop indicate?"
    ],
    training: {
        dog: [
            "How can I stop my dog from pulling on leash?",
            "What's the best way to crate train?",
            "How do I stop my dog from barking?"
        ],
        cat: [
            "How do I litter train my kitten?",
            "How can I stop my cat from scratching furniture?",
            "Tips for introducing a new cat?"
        ]
    },
    analysis: {
        general: [
            "Can you explain what these results mean?",
            "What should I watch out for?",
            "How serious are these findings?"
        ],
        medication: [
            "What are the side effects of this medication?",
            "How should I administer the medication?",
            "Can I give other medications at the same time?"
        ],
        followup: [
            "When should I schedule the next checkup?",
            "What preventive care is recommended?",
            "Should I monitor anything specific?"
        ]
    }
};

// Basic utilities
function showLoading() {
    const loadingState = document.getElementById('loadingState');
    const randomGif = loadingGifs[Math.floor(Math.random() * loadingGifs.length)];
    
    loadingState.innerHTML = `
        <div class="bg-white p-4 rounded-lg shadow-xl text-center">
            <img src="${randomGif}" alt="Loading..." class="mx-auto h-24 w-24 object-contain mb-2">
            <p class="text-gray-600 text-sm">Analyzing documents...</p>
        </div>
    `;
    
    loadingState.classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loadingState').classList.add('hidden');
}

// Tab switching functionality
function switchTab(tabName) {
    console.log('Switching to tab:', tabName);
    
    // Hide all tab contents
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.add('hidden');
    });
    
    // Remove active state from all tabs
    document.querySelectorAll('.tab-button').forEach(tab => {
        tab.classList.remove('border-blue-500', 'text-blue-600');
        tab.classList.add('border-gray-200', 'text-gray-500');
    });
    
    // Show selected tab content
    const selectedContent = document.getElementById(`${tabName}-content`);
    if (selectedContent) {
        selectedContent.classList.remove('hidden');
    }
    
    // Activate selected tab
    const selectedTab = document.getElementById(`${tabName}-tab`);
    if (selectedTab) {
        selectedTab.classList.remove('border-gray-200', 'text-gray-500');
        selectedTab.classList.add('border-blue-500', 'text-blue-600');
    }
}

// File upload handling
function handleFiles(files) {
    if (!files.length) return;

    const formData = new FormData();
    for (const file of files) {
        formData.append('files[]', file);
    }

    showLoading();

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const analysisResult = document.getElementById('analysisResult');
            document.getElementById('synopsis').innerHTML = data.result.synopsis;
            document.getElementById('insights-anomalies').innerHTML = data.result.insights_anomalies;
            document.getElementById('followup-actions').innerHTML = data.result.followup_actions;
            analysisResult.classList.remove('hidden');
            
            // Generate and display dynamic prompts based on the analysis
            const dynamicPrompts = generateDynamicPrompts(data.result);
            displayPrompts(dynamicPrompts);
            
            analysisResult.scrollIntoView({ behavior: 'smooth' });
        } else {
            throw new Error(data.error || 'Failed to analyze documents');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Error analyzing documents: ' + error.message);
    })
    .finally(() => {
        hideLoading();
    });
}

// Initialize everything when the DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, setting up handlers');
    
    // Set up tab switching with logging
    document.querySelectorAll('.tab-button').forEach(button => {
        console.log('Setting up tab button:', button.id);
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const tabName = this.dataset.tab;
            console.log('Tab clicked:', tabName);
            switchTab(tabName);
        });
    });

    // Set up file upload with logging
    const fileInput = document.getElementById('fileInput');
    const dropZone = document.getElementById('dropZone');

    if (fileInput && dropZone) {
        fileInput.addEventListener('change', function(e) {
            handleFiles(e.target.files);
        });

        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('border-blue-500');
        });

        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('border-blue-500');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('border-blue-500');
            handleFiles(e.dataTransfer.files);
        });
    }

    // Set up poop analyzer
    const poopFileInput = document.getElementById('poopFileInput');
    if (poopFileInput) {
        poopFileInput.addEventListener('change', function(e) {
            if (e.target.files.length === 0) return;
            
            const file = e.target.files[0];
            const formData = new FormData();
            formData.append('image', file);
            
            showLoading();
            
            fetch('/analyze-poop', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    addMessageToChat(data.analysis, 'assistant');
                } else {
                    throw new Error(data.error || 'Failed to analyze image');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error analyzing image: ' + error.message);
            })
            .finally(() => {
                hideLoading();
            });
        });
    }

    // Add chat form submission handler
    const chatForm = document.getElementById('chat-form');
    if (chatForm) {
        chatForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const chatInput = document.getElementById('chat-input');
            const message = chatInput.value.trim();
            
            if (!message) return;

            // Add user message to chat
            addMessageToChat(message, 'user');
            
            // Clear input
            chatInput.value = '';

            // Show chat loading indicator
            showChatLoading();

            // Send message to backend
            fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    hideChatLoading();
                    addMessageToChat(data.response, 'assistant');
                    
                    // If there's a medical error risk, show warning
                    if (data.medical_error_risk) {
                        addMessageToChat('⚠️ Note: This information is for general guidance only. Please consult with your veterinarian for specific medical advice.', 'assistant');
                    }
                } else {
                    throw new Error(data.error || 'Failed to get response');
                }
            })
            .catch(error => {
                console.error('Chat error:', error);
                hideChatLoading();
                addMessageToChat('Sorry, I encountered an error. Please try again.', 'assistant');
            })
            .finally(() => {
                // Scroll to bottom of chat
                const chatMessages = document.getElementById('chat-messages');
                if (chatMessages) {
                    chatMessages.scrollTop = chatMessages.scrollHeight;
                }
            });
        });
    }
});

// Chat functionality
function addMessageToChat(message, role = 'user') {
    const chatMessages = document.getElementById('chat-messages');
    if (!chatMessages) return;

    const messageDiv = document.createElement('div');
    messageDiv.className = role === 'assistant' ? 
        'bg-blue-50 p-4 rounded-lg' : 
        'bg-gray-50 p-4 rounded-lg';

    const messageContent = document.createElement('p');
    messageContent.className = 'text-gray-700 whitespace-pre-line';
    messageContent.textContent = message;

    messageDiv.appendChild(messageContent);
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Update suggested prompts based on context
function updateSuggestedPrompts(context = 'default') {
    const promptsContainer = document.getElementById('suggestedPrompts');
    let prompts = suggestedPrompts[context];
    
    if (!prompts) prompts = suggestedPrompts.default;
    
    promptsContainer.innerHTML = prompts.map(prompt => `
        <button onclick="useSuggestedPrompt('${prompt}')" 
                class="bg-blue-100 hover:bg-blue-200 text-blue-800 text-sm px-3 py-1 rounded-full transition-colors">
            ${prompt}
        </button>
    `).join('');
}

// Handle breed selection
document.getElementById('petType').addEventListener('change', function() {
    const breedSection = document.getElementById('breedSection');
    const breedSelect = document.getElementById('breedSelect');
    const petType = this.value;
    
    if (!petType) {
        breedSection.classList.add('hidden');
        return;
    }
    
    // Show breed section
    breedSection.classList.remove('hidden');
    
    // Update prompts for pet type
    if (suggestedPrompts.training[petType]) {
        updateSuggestedPrompts(`training.${petType}`);
    }
    
    // Populate breeds based on pet type
    fetch(`/api/breeds/${petType}`)
        .then(response => response.json())
        .then(breeds => {
            breedSelect.innerHTML = '<option value="">Select breed</option>' +
                breeds.map(breed => `<option value="${breed}">${breed}</option>`).join('');
        })
        .catch(error => console.error('Error loading breeds:', error));
});

// Add function to generate dynamic prompts based on analysis
function generateDynamicPrompts(analysisData) {
    const dynamicPrompts = [];
    
    // Extract key terms from the analysis
    const allText = (analysisData.synopsis + ' ' + 
                    analysisData.insights_anomalies + ' ' + 
                    analysisData.followup_actions).toLowerCase();

    // Check for specific conditions and add relevant prompts
    if (allText.includes('medication') || allText.includes('prescribed')) {
        dynamicPrompts.push(...suggestedPrompts.analysis.medication);
    }
    
    if (allText.includes('follow') || allText.includes('next visit')) {
        dynamicPrompts.push(...suggestedPrompts.analysis.followup);
    }

    // Add condition-specific prompts
    if (allText.includes('blood')) {
        dynamicPrompts.push("What do these blood test results mean?");
    }
    if (allText.includes('diet') || allText.includes('food')) {
        dynamicPrompts.push("What diet changes are recommended?");
    }
    if (allText.includes('weight')) {
        dynamicPrompts.push("How can I help manage my pet's weight?");
    }
    if (allText.includes('dental') || allText.includes('teeth')) {
        dynamicPrompts.push("What dental care is needed?");
    }

    // Always add some general analysis prompts
    dynamicPrompts.push(...suggestedPrompts.analysis.general);

    return dynamicPrompts;
}

// Function to display prompts
function displayPrompts(prompts) {
    const promptsContainer = document.getElementById('suggestedPrompts');
    if (!promptsContainer) return;

    promptsContainer.innerHTML = prompts.map(prompt => `
        <button onclick="useSuggestedPrompt('${prompt}')" 
                class="bg-blue-100 hover:bg-blue-200 text-blue-800 text-sm px-3 py-1 rounded-full transition-colors">
            ${prompt}
        </button>
    `).join('');
}

// Update the useSuggestedPrompt function
function useSuggestedPrompt(prompt) {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    if (chatInput && chatForm) {
        chatInput.value = prompt;
        // Create and dispatch submit event
        const submitEvent = new Event('submit', {
            'bubbles': true,
            'cancelable': true
        });
        chatForm.dispatchEvent(submitEvent);
    }
}

// Add a new function for chat loading indicator
function showChatLoading() {
    const chatMessages = document.getElementById('chat-messages');
    if (!chatMessages) return;

    const loadingDiv = document.createElement('div');
    loadingDiv.id = 'chat-loading';
    loadingDiv.className = 'bg-blue-50 p-4 rounded-lg flex items-center gap-2';
    loadingDiv.innerHTML = `
        <div class="flex gap-1">
            <div class="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></div>
            <div class="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
            <div class="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style="animation-delay: 0.4s"></div>
        </div>
        <span class="text-gray-600 text-sm">Thinking...</span>
    `;
    
    chatMessages.appendChild(loadingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function hideChatLoading() {
    const loadingDiv = document.getElementById('chat-loading');
    if (loadingDiv) {
        loadingDiv.remove();
    }
}

function formatAnalysisResults(results) {
    return `
    <div class="space-y-6">
        <div class="bg-blue-50 p-4 rounded-xl">
            <h3 class="font-semibold text-blue-800 mb-2">📋 Synopsis</h3>
            <div class="space-y-2">
                <p><span class="font-medium">Key Findings:</span> ${results.key_findings}</p>
                <p><span class="font-medium">Health Metrics:</span> ${results.health_metrics}</p>
                <p><span class="font-medium">Medication:</span> ${results.medication}</p>
            </div>
        </div>

        <div class="bg-purple-50 p-4 rounded-xl">
            <h3 class="font-semibold text-purple-800 mb-2">🔍 Insights & Anomalies</h3>
            <div class="space-y-2">
                <p><span class="font-medium">Analysis:</span> ${results.analysis}</p>
                <p><span class="font-medium">Patterns:</span> ${results.patterns}</p>
                <p><span class="font-medium">Recommendations:</span> ${results.recommendations}</p>
            </div>
        </div>

        <div class="bg-green-50 p-4 rounded-xl">
            <h3 class="font-semibold text-green-800 mb-2">✅ Follow-up Actions</h3>
            <div class="space-y-2">
                <p><span class="font-medium">Next Steps:</span> ${results.next_steps}</p>
                <p><span class="font-medium">Preventive Measures:</span> ${results.preventive}</p>
                <p><span class="font-medium">Next Check-up:</span> ${results.next_checkup}</p>
            </div>
        </div>
    </div>`;
}

function formatChatResponse(response) {
    // Convert markdown-style bold (**text**) to HTML bold tags
    response = response.replace(/\*\*(.*?)\*\*/g, '<strong class="font-bold">$1</strong>');
    
    // Format lists with proper spacing and bullets
    response = response.replace(/(\d+\.) /g, '<br>$1 ');
    
    return `
    <div class="bg-white p-4 rounded-xl shadow-sm">
        <p class="text-gray-700 leading-relaxed space-y-2">${response}</p>
    </div>`;
}
