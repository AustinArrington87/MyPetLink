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
    }
};

// Basic utilities
function showLoading() {
    const loadingState = document.getElementById('loadingState');
    if (loadingState) loadingState.classList.remove('hidden');
}

function hideLoading() {
    const loadingState = document.getElementById('loadingState');
    if (loadingState) loadingState.classList.add('hidden');
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

    // Show loading state
    document.getElementById('loadingState').classList.remove('hidden');

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
        document.getElementById('loadingState').classList.add('hidden');
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