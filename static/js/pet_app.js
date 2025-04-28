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
            
            // Show loading state
            const submitButton = this.querySelector('button[type="submit"]');
            const originalButtonText = submitButton.innerHTML;
            submitButton.disabled = true;
            submitButton.innerHTML = `
                <img src="/static/img/GIFs/spot.gif" alt="Loading..." class="h-6 w-6 inline mr-2">
                Submitting Report...
            `;
            
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
                const response = await fetch('/report-rescue', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(formData)
                });

                const data = await response.json();
                
                // Reset button state
                submitButton.disabled = false;
                submitButton.innerHTML = originalButtonText;
                
                if (data.success) {
                    closeRescueForm();
                    document.getElementById('rescueForm').reset();
                    document.getElementById('successMessage').classList.remove('hidden');
                } else {
                    throw new Error(data.error || 'Failed to submit report');
                }
            } catch (error) {
                // Reset button state
                submitButton.disabled = false;
                submitButton.innerHTML = originalButtonText;
                
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

function searchRescues() {
    const zipcode = document.getElementById('searchZipcode').value.trim();
    const resultsContainer = document.getElementById('rescueResults');
    
    if (!zipcode || !/^\d{5}$/.test(zipcode)) {
        alert('Please enter a valid 5-digit zipcode');
        return;
    }
    
    // Show loading state
    resultsContainer.innerHTML = '<div class="text-center py-4"><img src="/static/img/GIFs/cleo.gif" alt="Loading..." class="mx-auto h-12 w-12"></div>';
    
    fetch(`/search-rescues?zipcode=${zipcode}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                if (data.rescues.length === 0) {
                    resultsContainer.innerHTML = `
                        <div class="text-center py-4 text-gray-600">
                            No rescue tickets found in zipcode ${zipcode}
                        </div>
                    `;
                    return;
                }
                
                resultsContainer.innerHTML = data.rescues.map(rescue => `
                    <div class="bg-white p-4 rounded-xl shadow-md hover:shadow-lg transition-shadow mb-4">
                        <div class="flex justify-between items-start mb-3">
                            <h3 class="font-semibold text-lg text-purple-800">${rescue.ticket_name}</h3>
                            <span class="text-sm text-gray-500">${new Date(rescue.date).toLocaleDateString()}</span>
                        </div>
                        <p class="text-gray-600 mb-3">${rescue.description}</p>
                        <div class="flex flex-wrap gap-2 mb-3">
                            <span class="inline-block bg-purple-100 text-purple-800 text-sm px-2 py-1 rounded">
                                ${rescue.species}
                            </span>
                            ${rescue.breed ? `
                                <span class="inline-block bg-blue-100 text-blue-800 text-sm px-2 py-1 rounded">
                                    ${rescue.breed}
                                </span>
                            ` : ''}
                            <span class="inline-block bg-gray-100 text-gray-800 text-sm px-2 py-1 rounded">
                                📍 ${rescue.zipcode}
                            </span>
                        </div>
                        <!-- Contact Information Section -->
                        <div class="border-t pt-3 mb-2">
                            <button onclick="toggleContactInfo('contact-${rescue.id}')"
                                    class="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded-lg transition-colors w-full flex items-center justify-center gap-2">
                                <span class="text-lg">📞</span> Contact
                            </button>
                            <div id="contact-${rescue.id}" class="hidden mt-3 bg-gray-50 p-3 rounded-lg">
                                <div class="space-y-2">
                                    ${rescue.contact_name ? `
                                        <p class="flex items-center gap-2">
                                            <span class="font-medium">👤 Contact:</span> 
                                            ${rescue.contact_name}
                                        </p>
                                    ` : ''}
                                    ${rescue.contact_phone ? `
                                        <p class="flex items-center gap-2">
                                            <span class="font-medium">📱 Phone:</span>
                                            <a href="tel:${rescue.contact_phone}" class="text-blue-600 hover:underline">
                                                ${rescue.contact_phone}
                                            </a>
                                        </p>
                                    ` : ''}
                                    ${rescue.contact_email ? `
                                        <p class="flex items-center gap-2">
                                            <span class="font-medium">📧 Email:</span>
                                            <a href="mailto:${rescue.contact_email}" class="text-blue-600 hover:underline">
                                                ${rescue.contact_email}
                                            </a>
                                        </p>
                                    ` : ''}
                                    ${rescue.contact_address ? `
                                        <p class="flex items-center gap-2">
                                            <span class="font-medium">📍 Location:</span>
                                            ${rescue.contact_address}
                                        </p>
                                    ` : ''}
                                </div>
                            </div>
                        </div>
                        <!-- PetFinder Orgs Section -->
                        <div>
                            <button id="orgs-btn-${rescue.id}" data-open="false"
                                onclick="toggleOrgs('${rescue.id}', '${rescue.zipcode}')"
                                class="bg-yellow-500 hover:bg-yellow-600 text-white px-4 py-2 rounded-lg transition-colors w-full flex items-center justify-center gap-2">
                                <span class="text-lg">🏢</span> Show Nearby Organizations
                            </button>
                            <div id="orgs-${rescue.id}" class="hidden mt-3"></div>
                        </div>
                    </div>
                `).join('');
            } else {
                resultsContainer.innerHTML = `
                    <div class="text-center py-4 text-red-600">
                        ${data.error || 'Failed to search rescues. Please try again.'}
                    </div>
                `;
            }
        })
        .catch(error => {
            console.error('Error:', error);
            resultsContainer.innerHTML = `
                <div class="text-center py-4 text-red-600">
                    Failed to search rescues. Please try again.
                </div>
            `;
        });
}

// Add this function to toggle contact information visibility
function toggleContactInfo(contactId) {
    const contactDiv = document.getElementById(contactId);
    if (contactDiv.classList.contains('hidden')) {
        // Hide any other open contact info first
        document.querySelectorAll('[id^="contact-"]').forEach(div => {
            if (div.id !== contactId) {
                div.classList.add('hidden');
            }
        });
        // Show this contact info
        contactDiv.classList.remove('hidden');
    } else {
        contactDiv.classList.add('hidden');
    }
}

// Add event listener for Enter key on zipcode input
document.getElementById('searchZipcode')?.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        searchRescues();
    }
});

function fetchPetfinderOrgs(zipcode) {
    const orgsContainer = document.getElementById('petfinderOrgs');
    if (orgsContainer) {
        orgsContainer.innerHTML = '<div class="text-center py-2"><img src="/static/img/GIFs/cleo.gif" class="mx-auto h-8 w-8"></div>';
    }
    fetch(`/api/petfinder/organizations?zipcode=${zipcode}`)
        .then(res => res.json())
        .then(data => {
            if (data.success && data.organizations.length > 0) {
                orgsContainer.innerHTML = data.organizations.map(org => `
                    <div class="bg-yellow-50 p-3 rounded-lg mb-2 shadow">
                        <div class="font-semibold text-yellow-900">${org.name}</div>
                        <div class="text-sm text-gray-700">${org.address?.city || ''}, ${org.address?.state || ''} ${org.address?.postcode || ''}</div>
                        ${org.phone ? `<div class="text-sm">📞 <a href="tel:${org.phone}" class="text-blue-700">${org.phone}</a></div>` : ''}
                        ${org.email ? `<div class="text-sm">📧 <a href="mailto:${org.email}" class="text-blue-700">${org.email}</a></div>` : ''}
                        ${org.url ? `<div class="text-sm"><a href="${org.url}" target="_blank" class="text-blue-700 underline">View on PetFinder</a></div>` : ''}
                    </div>
                `).join('');
            } else {
                orgsContainer.innerHTML = '<div class="text-gray-500 text-sm">No organizations found nearby.</div>';
            }
        })
        .catch(() => {
            orgsContainer.innerHTML = '<div class="text-red-500 text-sm">Could not load organizations.</div>';
        });
}

function toggleOrgs(ticketId, zipcode) {
    const orgsDiv = document.getElementById(`orgs-${ticketId}`);
    const btn = document.getElementById(`orgs-btn-${ticketId}`);
    const isOpen = btn.getAttribute('data-open') === 'true';

    if (!isOpen) {
        // Hide all other orgs sections and reset their buttons
        document.querySelectorAll('[id^="orgs-"]').forEach(div => {
            if (div.id !== `orgs-${ticketId}`) div.classList.add('hidden');
        });
        document.querySelectorAll('[id^="orgs-btn-"]').forEach(button => {
            if (button.id !== `orgs-btn-${ticketId}`) {
                button.innerHTML = `<span class="text-lg">🏢</span> Show Nearby Organizations`;
                button.setAttribute('data-open', 'false');
            }
        });

        orgsDiv.classList.remove('hidden');
        btn.innerHTML = `<span class="text-lg">🏢</span> Hide Nearby Organizations`;
        btn.setAttribute('data-open', 'true');

        // Only fetch if not already loaded
        if (!orgsDiv.dataset.loaded) {
            orgsDiv.innerHTML = '<div class="text-center py-2"><img src="/static/img/GIFs/cleo.gif" class="mx-auto h-8 w-8"></div>';
            fetch(`/api/petfinder/organizations?zipcode=${zipcode}`)
                .then(res => res.json())
                .then(data => {
                    if (data.success && data.organizations.length > 0) {
                        orgsDiv.innerHTML = data.organizations.map(org => `
                            <div class="bg-yellow-50 p-3 rounded-lg mb-2 shadow">
                                <div class="font-semibold text-yellow-900">${org.name}</div>
                                <div class="text-sm text-gray-700">${org.address?.city || ''}, ${org.address?.state || ''} ${org.address?.postcode || ''}</div>
                                ${org.phone ? `<div class="text-sm">📞 <a href="tel:${org.phone}" class="text-blue-700">${org.phone}</a></div>` : ''}
                                ${org.email ? `<div class="text-sm">📧 <a href="mailto:${org.email}" class="text-blue-700">${org.email}</a></div>` : ''}
                                ${org.url ? `<div class="text-sm"><a href="${org.url}" target="_blank" class="text-blue-700 underline">View on PetFinder</a></div>` : ''}
                            </div>
                        `).join('');
                    } else {
                        orgsDiv.innerHTML = '<div class="text-gray-500 text-sm">No organizations found nearby.</div>';
                    }
                    orgsDiv.dataset.loaded = "true";
                })
                .catch(() => {
                    orgsDiv.innerHTML = '<div class="text-red-500 text-sm">Could not load organizations.</div>';
                });
        }
    } else {
        orgsDiv.classList.add('hidden');
        btn.innerHTML = `<span class="text-lg">🏢</span> Show Nearby Organizations`;
        btn.setAttribute('data-open', 'false');
    }
} 
