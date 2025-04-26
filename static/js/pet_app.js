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
function showLoading(context = 'documents') {
    const loadingState = document.getElementById('loadingState');
    const randomGif = loadingGifs[Math.floor(Math.random() * loadingGifs.length)];
    
    // Different loading messages based on context
    const loadingMessages = {
        documents: 'Analyzing documents...',
        chat: 'Thinking...',
        poop: 'Analyzing image...',
        training: 'Generating training tips...',
        rescue: 'Submitting report...'
    };
    
    loadingState.innerHTML = `
        <div class="bg-white p-4 rounded-lg shadow-xl text-center">
            <img src="${randomGif}" alt="Loading..." class="mx-auto h-24 w-24 object-contain mb-2">
            <p class="text-gray-600 text-sm">${loadingMessages[context] || 'Processing...'}</p>
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

    showLoading('documents');

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
            
            // Add analysis summary to chat
            const summary = `Here's what I found in your documents:\n\n${data.result.synopsis}`;
            addMessageToChat(summary, 'assistant');
            
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
            
            showLoading('poop');
            
            fetch('/analyze_poop', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    document.getElementById('poopSummary').innerHTML = formatSection(data.result.summary);
                    document.getElementById('poopConcerns').innerHTML = formatSection(data.result.concerns);
                    document.getElementById('poopRecommendations').innerHTML = formatSection(data.result.recommendations);
                    document.getElementById('poopAnalysisResult').classList.remove('hidden');
                    
                    // Scroll to results
                    document.getElementById('poopAnalysisResult').scrollIntoView({ behavior: 'smooth' });
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

    // Set up chat functionality
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');

    if (chatForm) {
        chatForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const message = chatInput.value.trim();
            if (!message) return;

            // Add user message to chat
            addMessageToChat(message, 'user');
            chatInput.value = '';

            showLoading('chat');

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ message })
                });

                const data = await response.json();
                if (data.success) {
                    addMessageToChat(data.response, 'assistant');
                } else {
                    throw new Error(data.error || 'Failed to get response');
                }
            } catch (error) {
                console.error('Chat error:', error);
                addMessageToChat('Sorry, I encountered an error. Please try again.', 'assistant');
            } finally {
                hideLoading();
            }
        });
    }

    // Add breed selection for training tips
    const trainingSpecies = document.getElementById('training-species');
    const trainingBreed = document.getElementById('training-breed');
    
    if (trainingSpecies && trainingBreed) {
        trainingSpecies.addEventListener('change', async function() {
            const species = this.value;
            
            if (!species) {
                trainingBreed.innerHTML = '<option value="">Select Species First</option>';
                return;
            }
            
            try {
                const response = await fetch(`/api/breeds/${species}`);
                const breeds = await response.json();
                
                trainingBreed.innerHTML = '<option value="">Select Breed</option>' + 
                    breeds.map(breed => `<option value="${breed}">${breed}</option>`).join('');
            } catch (error) {
                console.error('Error fetching breeds:', error);
                trainingBreed.innerHTML = '<option value="">Error loading breeds</option>';
            }
        });
    }

    // Add training tips function
    window.getTrainingTips = async function() {
        const species = document.getElementById('training-species').value;
        const breed = document.getElementById('training-breed').value;
        
        if (!species || !breed) {
            alert('Please select both species and breed');
            return;
        }
        
        showLoading('training');
        
        try {
            const response = await fetch('/get_training_tips', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ species, breed })
            });
            
            const data = await response.json();
            
            if (data.success) {
                document.getElementById('trainingTips').innerHTML = formatSection(data.result.training);
                document.getElementById('playTips').innerHTML = formatSection(data.result.play);
                document.getElementById('enrichmentTips').innerHTML = formatSection(data.result.enrichment);
                document.getElementById('trainingTipsResult').classList.remove('hidden');
                
                // Scroll to results
                document.getElementById('trainingTipsResult').scrollIntoView({ behavior: 'smooth' });
            } else {
                throw new Error(data.error || 'Failed to get training tips');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Error getting training tips: ' + error.message);
        } finally {
            hideLoading();
        }
    };

    // Add rescue form handler
    const rescueForm = document.getElementById('rescueForm');
    if (rescueForm) {
        rescueForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = {
                name: document.getElementById('rescueName').value,
                phone: document.getElementById('rescuePhone').value,
                location: document.getElementById('rescueLocation').value,
                species: document.getElementById('rescueSpecies').value,
                breed: document.getElementById('rescueBreed').value,
                description: document.getElementById('rescueDescription').value,
                email: document.getElementById('rescueEmail').value
            };

            try {
                showLoading('rescue');
                
                const response = await fetch('/report-rescue', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(formData)
                });

                const data = await response.json();
                hideLoading();
                
                if (data.success) {
                    closeRescueForm();
                    document.getElementById('rescueForm').reset();
                    document.getElementById('successMessage').classList.remove('hidden');
                } else {
                    throw new Error(data.error || 'Failed to submit report');
                }
            } catch (error) {
                hideLoading();
                console.error('Submission error:', error);
                alert('Error submitting report: ' + error.message);
            }
        });
    }
});

// Chat functionality
function addMessageToChat(message, role = 'user') {
    const chatMessages = document.getElementById('chat-messages');
    if (!chatMessages) return;

    const messageDiv = document.createElement('div');
    messageDiv.className = role === 'assistant' ? 
        'bg-blue-50 p-4 rounded-lg chat-message' : 
        'bg-gray-50 p-4 rounded-lg chat-message';

    // Convert line breaks and format lists
    const formattedMessage = message
        .replace(/\n\n/g, '<br><br>')
        .replace(/\n•/g, '<br>•')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    messageDiv.innerHTML = `<div class="prose max-w-none text-gray-700">${formattedMessage}</div>`;
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

// Update the useSuggestedPrompt function to use the chat context
async function useSuggestedPrompt(prompt) {
    const chatInput = document.getElementById('chat-input');
    const chatForm = document.getElementById('chat-form');
    if (!chatInput || !chatForm) return;

    chatInput.value = prompt;
    addMessageToChat(prompt, 'user');
    chatInput.value = '';

    showLoading('chat');  // Use chat context for loading message

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: prompt })
        });

        const data = await response.json();
        if (data.success) {
            addMessageToChat(data.response, 'assistant');
        } else {
            throw new Error(data.error || 'Failed to get response');
        }
    } catch (error) {
        console.error('Chat error:', error);
        addMessageToChat('Sorry, I encountered an error. Please try again.', 'assistant');
    } finally {
        hideLoading();
    }
}

// Add this with the other utility functions
function formatSection(content) {
    if (!content) return '';
    
    // First, clean up any markdown-style headers
    let cleanContent = content
        .replace(/###\s*\d*\.\s*/g, '')  // Remove markdown header numbers
        .replace(/####\s*/g, '')         // Remove extra header marks
        
        // Format the main section headers
        .replace(/(Training Tips|Exercise & Play|Enrichment Activities):/g, 
            '<strong class="block text-lg text-purple-800 mb-3">$1</strong>')
        
        // Format subsection headers
        .replace(/•\s*([^:]+):/g, 
            '<strong class="block text-md text-gray-700 mt-3 mb-2">• $1:</strong>')
        
        // Format regular bullet points
        .replace(/\n-\s/g, '<br>• ')
        
        // Handle line breaks and other formatting
        .replace(/\n\n/g, '<br><br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong class="font-medium">$1</strong>');

    return cleanContent;
}

// Add these functions to pet_app.js

function openRescueForm() {
    document.getElementById('rescueFormModal').classList.remove('hidden');
}

function closeRescueForm() {
    document.getElementById('rescueFormModal').classList.add('hidden');
}

function getCurrentLocation() {
    if (navigator.geolocation) {
        // Show searching message
        const locationInput = document.getElementById('rescueLocation');
        const originalPlaceholder = locationInput.placeholder;
        locationInput.placeholder = '📍 Searching for your location...';
        locationInput.disabled = true;

        navigator.geolocation.getCurrentPosition(
            position => {
                // Get address from coordinates using reverse geocoding
                fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${position.coords.latitude}&lon=${position.coords.longitude}`)
                    .then(response => response.json())
                    .then(data => {
                        locationInput.value = data.display_name;
                        locationInput.disabled = false;
                        locationInput.placeholder = originalPlaceholder;
                    })
                    .catch(error => {
                        console.error('Error getting location:', error);
                        alert('Could not get address. Please enter manually.');
                        locationInput.disabled = false;
                        locationInput.placeholder = originalPlaceholder;
                    });
            },
            error => {
                console.error('Error:', error);
                alert('Could not get location. Please enter address manually.');
                locationInput.disabled = false;
                locationInput.placeholder = originalPlaceholder;
            }
        );
    } else {
        alert('Geolocation is not supported by your browser');
    }
}

// Add this function
function closeSuccessMessage() {
    document.getElementById('successMessage').classList.add('hidden');
}

// Function to handle pet selection
function selectActivePet(petId) {
    showLoading();
    
    fetch(`/set_active_pet/${petId}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        } else {
            throw new Error(data.error || 'Failed to select pet');
        }
    })
    .catch(error => {
        console.error('Error selecting pet:', error);
        alert('Error selecting pet: ' + error.message);
    })
    .finally(() => {
        hideLoading();
    });
}

// Function to fetch pet files and display in UI
function loadPetFiles(petId, fileType = null) {
    if (!petId) return;
    
    let url = `/get_pet_files/${petId}`;
    if (fileType) {
        url += `?type=${fileType}`;
    }
    
    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                displayPetFiles(data.files, fileType);
            } else {
                throw new Error(data.error || 'Failed to fetch pet files');
            }
        })
        .catch(error => {
            console.error('Error fetching pet files:', error);
            const fileContainer = document.getElementById('pet-files-container');
            if (fileContainer) {
                fileContainer.innerHTML = `<p class="text-red-500">Error loading files: ${error.message}</p>`;
            }
        });
}

// Function to display pet files in the UI
function displayPetFiles(files, fileType) {
    const fileContainer = document.getElementById('pet-files-container');
    if (!fileContainer) return;
    
    if (!files || files.length === 0) {
        fileContainer.innerHTML = '<p class="text-gray-500 text-center py-4">No files found</p>';
        return;
    }
    
    // Group files by file type if no specific type is requested
    if (!fileType) {
        const groupedFiles = {};
        
        // Group files by type
        files.forEach(file => {
            if (!groupedFiles[file.file_type]) {
                groupedFiles[file.file_type] = [];
            }
            groupedFiles[file.file_type].push(file);
        });
        
        // Generate HTML for each group
        let html = '';
        
        // Define the display order and friendly names
        const fileTypeOrder = ['avatar', 'health_record', 'poop'];
        const fileTypeTitles = {
            'avatar': 'Avatars',
            'health_record': 'Health Records',
            'poop': 'Health Monitoring Images'
        };
        
        fileTypeOrder.forEach(type => {
            if (groupedFiles[type] && groupedFiles[type].length > 0) {
                html += `
                    <div class="mb-6">
                        <h3 class="text-lg font-medium text-gray-800 mb-2">${fileTypeTitles[type] || type}</h3>
                        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                            ${getFilesHTML(groupedFiles[type])}
                        </div>
                    </div>
                `;
            }
        });
        
        fileContainer.innerHTML = html;
    } else {
        // Display specific file type
        fileContainer.innerHTML = `
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                ${getFilesHTML(files)}
            </div>
        `;
    }
    
    // Add click handlers for file previews
    document.querySelectorAll('.pet-file-card').forEach(card => {
        card.addEventListener('click', function() {
            const fileId = this.dataset.fileId;
            const filePath = this.dataset.filePath;
            const fileType = this.dataset.fileType;
            const fileName = this.dataset.fileName;
            
            // Handle different file types
            if (fileType === 'avatar') {
                previewImage(filePath, fileName);
            } else if (fileType === 'health_record') {
                if (fileName.toLowerCase().endsWith('.pdf')) {
                    previewPdf(filePath, fileName);
                } else {
                    previewImage(filePath, fileName);
                }
            } else if (fileType === 'poop') {
                previewImage(filePath, fileName, true); // true indicates analysis is available
            }
        });
    });
}

// Generate HTML for file cards
function getFilesHTML(files) {
    return files.map(file => {
        const fileExtension = file.original_filename.split('.').pop().toLowerCase();
        let thumbnailHTML = '';
        
        // Determine appropriate thumbnail based on file type and extension
        if (file.file_type === 'avatar' || 
            ['jpg', 'jpeg', 'png', 'gif'].includes(fileExtension)) {
            thumbnailHTML = `<img src="${file.s3_path}" alt="${file.original_filename}" class="w-full h-32 object-cover rounded-t-lg" onerror="this.src='/static/img/pet_logo.png'">`;
        } else if (fileExtension === 'pdf') {
            thumbnailHTML = `<div class="w-full h-32 bg-red-50 flex items-center justify-center rounded-t-lg">
                              <svg class="w-16 h-16 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M9 2a2 2 0 00-2 2v8a2 2 0 002 2h6a2 2 0 002-2V6.414A2 2 0 0016.414 5L14 2.586A2 2 0 0012.586 2H9z"></path>
                                <path d="M3 8a2 2 0 012-2h2a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V8z"></path>
                              </svg>
                            </div>`;
        } else {
            thumbnailHTML = `<div class="w-full h-32 bg-gray-100 flex items-center justify-center rounded-t-lg">
                              <svg class="w-16 h-16 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
                                <path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clip-rule="evenodd"></path>
                              </svg>
                            </div>`;
        }
        
        // Format date
        const fileDate = new Date(file.created_at);
        const formattedDate = fileDate.toLocaleDateString();
        
        // Create card HTML
        return `
            <div class="pet-file-card bg-white rounded-lg shadow-md overflow-hidden cursor-pointer hover:shadow-lg transition-shadow"
                 data-file-id="${file.id}"
                 data-file-path="${file.s3_path}"
                 data-file-type="${file.file_type}"
                 data-file-name="${file.original_filename}">
                ${thumbnailHTML}
                <div class="p-3">
                    <p class="text-sm font-medium text-gray-700 truncate">${file.original_filename}</p>
                    <p class="text-xs text-gray-500">${formattedDate}</p>
                    ${file.has_analysis ? '<span class="text-xs bg-green-100 text-green-800 px-2 py-1 rounded-full">Analysis Available</span>' : ''}
                </div>
            </div>
        `;
    }).join('');
}

// Function to preview an image
function previewImage(imagePath, fileName, hasAnalysis = false) {
    // Create modal for image preview
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4';
    
    // Create modal content
    modal.innerHTML = `
        <div class="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            <div class="p-4 border-b border-gray-200 flex justify-between items-center">
                <h3 class="text-lg font-medium text-gray-900">${fileName}</h3>
                <button class="text-gray-400 hover:text-gray-500" id="close-preview">
                    <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
            </div>
            <div class="flex-1 overflow-auto p-4 flex flex-col md:flex-row gap-4">
                <div class="flex-1">
                    <img src="${imagePath}" alt="${fileName}" class="max-w-full h-auto mx-auto" onerror="this.src='/static/img/pet_logo.png'">
                </div>
                ${hasAnalysis ? `
                <div class="md:w-1/3 bg-gray-50 p-4 rounded-lg">
                    <h4 class="font-medium text-gray-900 mb-2">Analysis</h4>
                    <div id="analysis-content" class="text-sm text-gray-700">
                        <p class="text-gray-500 italic">Loading analysis...</p>
                    </div>
                </div>` : ''}
            </div>
            <div class="p-4 border-t border-gray-200 flex justify-end">
                <button class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700" id="close-button">Close</button>
            </div>
        </div>
    `;
    
    // Add modal to body
    document.body.appendChild(modal);
    
    // Add event listeners to close the modal
    document.getElementById('close-preview').addEventListener('click', () => {
        document.body.removeChild(modal);
    });
    
    document.getElementById('close-button').addEventListener('click', () => {
        document.body.removeChild(modal);
    });
    
    // Close on background click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            document.body.removeChild(modal);
        }
    });
    
    // If there's analysis, fetch it
    if (hasAnalysis) {
        // This would be a call to get the analysis from the backend
        // For now, we'll just simulate with a placeholder
        
        setTimeout(() => {
            const analysisContent = document.getElementById('analysis-content');
            if (analysisContent) {
                analysisContent.innerHTML = `
                    <div class="space-y-3">
                        <div>
                            <h5 class="font-medium">Summary</h5>
                            <p>Normal healthy stool sample with good consistency.</p>
                        </div>
                        <div>
                            <h5 class="font-medium">Concerns</h5>
                            <p>No concerns detected in this sample.</p>
                        </div>
                        <div>
                            <h5 class="font-medium">Recommendations</h5>
                            <p>Continue with current diet and monitoring routine.</p>
                        </div>
                    </div>
                `;
            }
        }, 1000);
    }
}

// Function to preview a PDF
function previewPdf(pdfPath, fileName) {
    // Create modal for PDF preview
    const modal = document.createElement('div');
    modal.className = 'fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4';
    
    // Create modal content with embedded PDF viewer
    modal.innerHTML = `
        <div class="bg-white rounded-lg shadow-xl max-w-4xl w-full h-[90vh] overflow-hidden flex flex-col">
            <div class="p-4 border-b border-gray-200 flex justify-between items-center">
                <h3 class="text-lg font-medium text-gray-900">${fileName}</h3>
                <button class="text-gray-400 hover:text-gray-500" id="close-preview">
                    <svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
            </div>
            <div class="flex-1 overflow-hidden">
                <iframe src="${pdfPath}" class="w-full h-full border-0"></iframe>
            </div>
            <div class="p-4 border-t border-gray-200 flex justify-between">
                <a href="${pdfPath}" target="_blank" class="px-4 py-2 bg-gray-100 text-gray-800 rounded hover:bg-gray-200">Open in New Tab</a>
                <button class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700" id="close-button">Close</button>
            </div>
        </div>
    `;
    
    // Add modal to body
    document.body.appendChild(modal);
    
    // Add event listeners to close the modal
    document.getElementById('close-preview').addEventListener('click', () => {
        document.body.removeChild(modal);
    });
    
    document.getElementById('close-button').addEventListener('click', () => {
        document.body.removeChild(modal);
    });
    
    // Close on background click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            document.body.removeChild(modal);
        }
    });
}
