from playwright.sync_api import sync_playwright
import sqlite3
from datetime import date


today = date.today()
url = 'https://www.fazwaz.com/property-for-rent/thailand/bangkok'


### Start Playwright ###
with sync_playwright() as p:
    print("Launching browser for ya, buddy...")
    
    browser = p.chromium.launch(headless=False)
    
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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

        build_dict = {
            'id': idx + 1,
            'name': name,
            'price': round(price, 2),
            'location': location,
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
            print("It's tough 'round here... missing extra info.")
            listing_dict = build_dict | {'bdrms': 'n/a', 'baths': 'n/a', 'size': 'n/a' }
        listings.append(listing_dict)
    print(listings)

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
            str(listing['date_scraped']))
        )
    # INSERT
    cursor.executemany("INSERT OR IGNORE INTO listing (name, price, location, bdrms, baths, size, date_scraped) VALUES (?,?,?,?,?,?,?)", data)
    connection.commit()

    # Quick lil check
    for row in cursor.execute("SELECT id, name, price FROM listing ORDER BY price ASC"):
        print(row)
    cursor.execute("SELECT COUNT(*) FROM listing")
    row_count = cursor.fetchone()[0]
    print(row_count)

    for row in cursor.execute("SELECT id, name, price FROM listing WHERE bdrms = 1"):
        print(row)
    for row in cursor.execute("SELECT id, name, price, price / size AS ppsm FROM listing"):
        print(row)
    

        
    
    ### Close out the browser cleanly ###
    browser.close()
    print("Browser closed safely.")
