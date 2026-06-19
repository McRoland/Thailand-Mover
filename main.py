from playwright.sync_api import sync_playwright
import sqlite3
from datetime import date
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import folium


usr_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
geolocator = Nominatim(user_agent="thailand=mover-scraper")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)
today = date.today()
url = 'https://www.fazwaz.com/property-for-rent/thailand/bangkok'


### Start Playwright ###
with sync_playwright() as p:
    print("Launching browser for ya, buddy...")
    
    browser = p.chromium.launch(headless=False)
    
    context = browser.new_context(
        user_agent=usr_agent,
        viewport={"width": 1280, "height": 720},
    )
    page = context.new_page()

    print(f"Navigating to: {url}")

    # Go to the page and wait until the network becomes stable
    page.goto(url, wait_until="networkidle")
    page.wait_for_timeout(3000)


    # Use 'loaded' class and 'data-tk' attribute to wait for listings then make iterable
    outer_div = page.locator("div.loaded").first
    outer_div.wait_for(
        state="attached",
        timeout=15000
    )
    all_items = page.locator("[data-tk='unit-result']").all()
    print(f"Found {len(all_items)} listings")


### Iterate through all 30 rental listings on page and extract result info ###
    listings = []
    for idx, item in enumerate(all_items):
        try:
            name = item.locator("a.unit-name.unit-name--have-project-link").first.inner_text()
        except:
            name = "n/a"
        try:
            price_text = item.locator("div.price-tag").inner_text()
            price_text = price_text.split("\n")[0]  
            
            for char in [",", ".", "$", "฿", "/mo"]:
                price_text = price_text.replace(char, "")
                
            price = float(price_text.strip())
        except:
            price = None
        try:
            location = item.locator("div.location-unit").inner_text()
        except:
            location = "n/a"
        try:
            address =  str(location)
            geolocation = geocode(address, language="en")
            lat = geolocation.latitude
            lon = geolocation.longitude
        except:
            lat = 'n/a'
            lon = 'n/a'



        build_dict = {
            'id': idx + 1,
            'name': name,
            'price': round(price, 2),
            'location': location,
            'lat': lat,
            'lon': lon,
            'date_scraped': str(today)
        }
        listing_dict = {}
        try:
            wrap_info = item.locator("div.wrap-icon-info").inner_text()
            wrap_info_list = wrap_info.splitlines()
            if wrap_info_list[0] == 'Studio':
                bdrms = 0
                baths = float(wrap_info_list[1])
                size_sqm = wrap_info_list[3].split(" ")[0]
                size_sqm = float(size_sqm)
            else:
                bdrms = float(wrap_info_list[0])
                baths = float(wrap_info_list[2])
                size_sqm = wrap_info_list[4].split(" ")[0]
                size_sqm = float(size_sqm)
            listing_dict = build_dict | {'bdrms': bdrms, 'baths': baths, 'size': size_sqm }
        except:
            # print("It's tough 'round here... missing extra info.")
            listing_dict = build_dict | {'bdrms': 'n/a', 'baths': 'n/a', 'size': 'n/a' }
        listings.append(listing_dict)

### SQL Interface ###
    connection = sqlite3.connect("rentals.db")
    cursor = connection.cursor()

    cursor.execute("DROP TABLE IF EXISTS listing")

    # CREATE table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS listing(
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            name TEXT UNIQUE,
            price REAL, 
            location,
            bdrms REAL,
            baths REAL, 
            size REAL,
            lat REAL,
            lon REAL,
            date_scraped)
""")
    # Get extracted data ready for SQL INSERT
    data = []
    for listing in listings:
        data.append((
            listing['name'],
            listing['price'],
            listing['location'],
            listing['bdrms'],
            listing['baths'],
            listing['size'],
            listing['lat'],
            listing['lon'],
            str(listing['date_scraped']))
        )
    # INSERT
    cursor.executemany("INSERT OR IGNORE INTO listing (name, price, location, bdrms, baths, size, lat, lon, date_scraped) VALUES (?,?,?,?,?,?,?,?,?)", data)
    connection.commit()


### Quick lil check ###
    # for row in cursor.execute("SELECT id, name, price FROM listing ORDER BY price ASC"):
    #     print(row)
    # cursor.execute("SELECT COUNT(*) FROM listing")
    # row_count = cursor.fetchone()[0]
    # print(row_count)

    # for row in cursor.execute("SELECT id, name, price FROM listing WHERE bdrms = 1"):
    #     print(row)

### Folium Mapping ###
    m = folium.Map(location=[13.7563, 100.5018], zoom_start=12)
    
    def price_marker(row, pop_output):
        if row[4] < 600:
            folium.CircleMarker(
                location=[row[2], row[3]],
                popup=pop_output,
                color="green",
                fill=True,
                fill_color="green",
                fill_opacity=0.6

            ).add_to(m)
        elif row[4] >= 600 and row[4] <= 900:
            folium.CircleMarker(
                location=[row[2], row[3]],
                popup=pop_output,
                color="yellow",
                fill=True,
                fill_color="gold",
                fill_opacity=0.6

            ).add_to(m)
        elif row[4] > 900:
            folium.CircleMarker(
                location=[row[2], row[3]],
                popup=pop_output,
                color="orange",
                fill=True,
                fill_color="orange",
                fill_opacity=0.6

            ).add_to(m)
        return m
    
    for row in cursor.execute("SELECT id, name, lat, lon, price, bdrms, baths FROM listing ORDER BY price ASC"):
        print(row[1], row[4])
        popup_text = [f"Name: {row[1]}", f"Price: ${row[4]}/mo", f"{row[5]} Bed(s)", f"{row[6]} Bath(s)"]
        pop_output = "<br>".join(popup_text)

        if row[2] and row[3] == 'n/a':
            continue
        else:
            price_marker(row, pop_output)
                    
    m.save("index.html")  

### Close out the browser cleanly ###
    browser.close()
    print("Browser closed safely.")
