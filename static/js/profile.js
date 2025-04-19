// State-city mapping with proper labels and only the states/cities we have vets for
const stateData = {
    'PA': {
        label: 'Pennsylvania',
        cities: ['Philadelphia']
    },
    'CA': {
        label: 'California',
        cities: ['Woodland Hills', 'Walnut Creek', 'Sacramento']
    },
    'NY': {
        label: 'New York',
        cities: ['New York']
    },
    'MA': {
        label: 'Massachusetts',
        cities: ['Melrose', 'Middleboro', 'Beverly']
    },
    'PR': {
        label: 'Puerto Rico',
        cities: ['San Juan', 'Cabo Rojo', 'Aguadilla']
    }
};

// Populate state dropdown on page load
document.addEventListener('DOMContentLoaded', function() {
    const stateSelect = document.getElementById('state');
    stateSelect.innerHTML = '<option value="">Select State</option>' + 
        Object.entries(stateData).map(([code, data]) => 
            `<option value="${code}">${data.label}</option>`
        ).join('');
});

// Update cities when state changes
document.getElementById('state').addEventListener('change', function() {
    const cities = stateData[this.value]?.cities || [];
    const citySelect = document.getElementById('city');
    citySelect.innerHTML = '<option value="">Select City</option>' + 
        cities.map(city => `<option value="${city}">${city}</option>`).join('');
});

// Update vets when city changes
document.getElementById('city').addEventListener('change', async function() {
    const state = document.getElementById('state').value;
    const city = this.value;
    
    if (!state || !city) return;
    
    try {
        const response = await fetch(`/api/vets/${state}/${city}`);
        const vets = await response.json();
        
        document.getElementById('nearby-vets').innerHTML = `
            ${vets.map(vet => `
                <div class="bg-white p-4 rounded-lg shadow hover:shadow-md transition-shadow">
                    <h4 class="font-medium text-lg text-blue-800">${vet.name}</h4>
                    <p class="text-gray-600 mt-1">${vet.address}</p>
                    <div class="mt-3 flex flex-wrap gap-3">
                        <a href="tel:${vet.phone}" 
                           class="inline-flex items-center text-blue-600 hover:text-blue-800">
                            <span class="mr-1">📞</span> ${vet.phone}
                        </a>
                        <a href="mailto:${vet.email}" 
                           class="inline-flex items-center text-blue-600 hover:text-blue-800">
                            <span class="mr-1">✉️</span> ${vet.email}
                        </a>
                    </div>
                    <a href="${vet.website}" 
                       target="_blank" 
                       class="mt-2 inline-block text-sm text-blue-600 hover:text-blue-800 hover:underline">
                        Visit Website
                    </a>
                </div>
            `).join('')}
            
            <div class="mt-8 text-center p-6 bg-gray-50 rounded-lg border-2 border-dashed border-gray-200">
                <div class="text-2xl mb-2">🏗️</div>
                <h3 class="text-lg font-medium text-gray-800 mb-1">More Veterinarians Coming Soon!</h3>
                <p class="text-gray-600">We're expanding our network of trusted veterinary partners.</p>
            </div>
        `;
    } catch (error) {
        console.error('Error fetching vets:', error);
    }
}); 
