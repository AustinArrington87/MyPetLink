import asyncio
from crawl4ai import AsyncWebCrawler
import json

async def scrape_vca_hospitals():
    try:
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(
                url="https://vcahospitals.com/find-a-hospital/location-directory",
                wait_for_selector=".hospital-list"  # Adjust based on actual page structure
            )
            
            # Process and structure the data
            hospitals = []
            # Add processing logic here based on the actual response structure
            
            return hospitals
            
    except Exception as e:
        print(f"Error scraping VCA hospitals: {e}")
        # Fallback to hardcoded data
        return get_hardcoded_vets()

def get_hardcoded_vets():
    return [
        {
            "name": "Philadelphia Animal Hospital",
            "city": "Philadelphia",
            "state": "PA",
            "address": "7401 Holstein Ave",
            "phone": "(215) 724-5550",
            "website": "https://www.philadelphiaanimalhospital.com/",
            "email": "info@philadelphiaanimalhospital.com"
        },
        {
            "name": "Liberty Veterinary Clinic",
            "city": "Philadelphia",
            "state": "PA",
            "address": "8919 Ridge Ave",
            "phone": "(215) 483-1066",
            "website": "https://www.libvetclinic.com/",
            "email": "libertyveterinaryclinic@gmail.com"
        },
        {
            "name": "Wissahickon Creek Veterinary Hospital",
            "city": "Philadelphia",
            "state": "PA",
            "address": "7376 Ridge Ave",
            "phone": "(215) 483-9896",
            "website": "https://www.wcvh.org/",
            "email": "info@wcvh.org"
        },
        {
            "name": "Southern California Veterinary Hospital",
            "city": "Woodland Hills",
            "state": "CA",
            "address": "23287 Ventura Blvd",
            "phone": "(818) 999-1290",
            "website": "https://socalvet.com/",
            "email": "scvh@yourvetdoc.com"
        },
        {
            "name": "Geary Veterinary Hospital",
            "city": "Walnut Creek",
            "state": "CA",
            "address": "1514 Palos Verdes Mall",
            "phone": "(925) 938-8010",
            "website": "https://www.gearyveterinaryhospital.com/",
            "email": "Staff@gearyveterinaryhospital.com"
        },
        {
            "name": "Sacramento Animal Hospital",
            "city": "Sacramento",
            "state": "CA",
            "address": "5701 H Street",
            "phone": "(916) 451-7213",
            "website": "https://www.mysacvet.com/",
            "email": "info@mysacvet.com"
        },
        {
            "name": "Inwood Animal Clinic",
            "city": "New York",
            "state": "NY",
            "address": "4846 Broadway",
            "phone": "(212) 304-8387",
            "website": "https://www.inwoodanimalclinic.com/",
            "email": "info@inwoodanimalclinic.com"
        },
        {
            "name": "Lincoln Square Veterinary Hospital",
            "city": "New York",
            "state": "NY",
            "address": "140 W 67th St",
            "phone": "(212) 712-9600",
            "website": "https://www.lsvets.com/",
            "email": "LincolnSquareVH@yourvetdoc.com"
        },
        {
            "name": "The Village Veterinarian",
            "city": "New York",
            "state": "NY",
            "address": "318 East 11th St",
            "phone": "(212) 979-9870",
            "website": "https://villageveterinarian.com/",
            "email": "customercare@villageveterinarian.com"
        },
        {
            "name": "Melrose Animal Clinic",
            "city": "Melrose",
            "state": "MA",
            "address": "26 Essex St",
            "phone": "(781) 662-4888",
            "website": "https://melroseanimalclinic.com/",
            "email": "customerservice@melroseanimalclinic.com"
        },
        {
            "name": "Chase Veterinary Clinic",
            "city": "Middleboro",
            "state": "MA",
            "address": "66 East Grove St",
            "phone": "(508) 947-9400",
            "website": "https://chasevetclinic.com/",
            "email": "chasevc@yourvetdoc.com"
        },
        {
            "name": "Farms Veterinary Clinic",
            "city": "Beverly",
            "state": "MA",
            "address": "642 Hale St",
            "phone": "(978) 927-0317",
            "website": "https://farmsveterinaryclinic.com/",
            "email": "staff@farmsveterinaryclinic.com"
        },
        {
            "name": "Miramar Animal Hospital",
            "city": "San Juan",
            "state": "PR",
            "address": "Av. Ponce de León",
            "phone": "(787) 725-3637",
            "website": "https://www.miramaranimalhospital.net/",
            "email": "info@miramaranimalhospital.net"
        },
        {
            "name": "Animal Medical Hospital",
            "city": "Cabo Rojo",
            "state": "PR",
            "address": "Calle José de Diego",
            "phone": "(787) 255-3316",
            "website": "https://www.animalmedicalhospital.org/",
            "email": "recepcion@animalmedicalhospital.org"
        },
        {
            "name": "Aguadilla Veterinary Clinic",
            "city": "Aguadilla",
            "state": "PR",
            "address": "Carr. 107, Km. 3.2",
            "phone": "(787) 819-4609",
            "website": "https://aguadillavc.com/",
            "email": "avcveterinary@gmail.com"
        }
    ]

# Add route to get vets by location
@app.route('/api/vets/<state>/<city>')
def get_vets_by_location(state, city):
    vets = get_hardcoded_vets()
    filtered_vets = [v for v in vets if v['state'] == state and v['city'] == city]
    return jsonify(filtered_vets) 
