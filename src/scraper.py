import undetected_chromedriver as uc
import time
from bs4 import BeautifulSoup
import json
from urllib.parse import urljoin
import csv
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def extract(driver):
    # Get the page source
    page_content = driver.page_source
    soup = BeautifulSoup(page_content, "html.parser")

    # Extract all content sections
    data = {}
    if soup.find(string="Department of Smart Computing and Cyber Resilience") or soup.find(string="Department of Data Science and Artificial Intelligence"):
        content_list = soup.find_all("div", class_="view-staff-profile-detail-page")

    # Define the sections to extract
    sections = {
        "email": {"tag": "a", "class": "emailicon"},
        "name": {"tag": "span", "class": "field-content", "child": "h1"},
        "biography": {"tag": "h2", "text": "Biography", "next_sibling": "div"},
        "academic_and_professional_qualifications": {"tag": "h2", "text": "Academic & Professional Qualifications", "next_sibling": "div", "list": "true"},
        "research_interests": {"tag": "h2", "text": "Research Interests", "next_sibling": "div", "list": "true"},
        "teaching_areas": {"tag": "h2", "text": "Teaching Areas", "next_sibling": "div", "list": "true"},
        "courses_taught": {"tag": "h2", "text": "Courses Taught", "next_sibling": "div", "list": "true"},
        "notable_publications": {"tag": "h2", "text": "Notable Publications", "next_sibling": "span", "child": {"tag": "div", "class": "views-field-field-publication-details", "child": "p"}, "list": "true"},
    }

    # Loop through the content list and extract data
    for div in content_list:
        keys_to_remove = []
        for key, params in sections.items():
            if "text" in params:  # For sections identified by text (e.g., Biography)
                section = div.find(params["tag"], string=params["text"])
                if section and "next_sibling" in params:
                    content = section.find_next_sibling(params["next_sibling"])
                    if content:
                        if "list" in params:
                            if content and "child" in params:
                                contents = content.find_all(params["child"]["tag"], class_=params["child"]["class"])
                                extracted_contents = [content.get_text(strip=True) for content in contents]  # Extract text from each <li>
                                data[key] = extracted_contents  # Store the list of extracted items in the data dictionary
                                keys_to_remove.append(key)  # Mark key for removal
                            else:
                                items = content.find_all("li") 
                                extracted_items = [item.get_text(strip=True) for item in items]  # Extract text from each <li>
                                data[key] = extracted_items  # Store the list of extracted items in the data dictionary
                                keys_to_remove.append(key)  # Mark key for removal
                        else:
                            data[key] = content.get_text(strip=True)
                            keys_to_remove.append(key)  # Mark key for removal
                    else:
                        data[key] = ""
                else:
                    data[key] = ""
            elif "class" in params:  # For sections identified by class
                section = div.find(params["tag"], class_=params["class"])
                if section and "child" in params:
                    content = section.find(params["child"])
                    if content:
                        data[key] = content.get_text(strip=True)
                        keys_to_remove.append(key)  # Mark key for removal
                    else:
                        data[key] = ""
                elif section:
                    data[key] = section.get_text(strip=True)
                    print(data[key])
                    keys_to_remove.append(key)
                else:
                    data[key] = ""

        # Remove keys after the inner loop
        for key in keys_to_remove:
            sections.pop(key)

    # Convert to JSON
    json_data = json.dumps(data, indent=4)
    return json_data

def get_links(staff_links, driver):
    check_url = "/school-of-engineering-technology/staff-profiles/"

    # Get the page source
    page_content = driver.page_source
    soup = BeautifulSoup(page_content, "html.parser")

    # Extract all <a> tags with href matching the base URL
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if href.startswith(check_url):  # Check if the link matches the desired pattern
            staff_links.add(href)

# URL to scrape
URL = "https://sunwayuniversity.edu.my/school-of-engineering-technology/staff-profiles"

# Set up undetected ChromeDriver
options = uc.ChromeOptions()
options.add_argument("--disable-gpu")  # Disable GPU acceleration
options.add_argument("--no-sandbox")  # Bypass OS security model
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
)
options.binary_location = r"c:\Users\seanh\Documents\University\CAPSTONE 2\CAPSTONE-2\src\chrome-win64\chrome.exe"

# Initialize undetected ChromeDriver
driver = uc.Chrome(options=options, driver_executable_path="src/chromedriver-win64/chromedriver.exe")

try:
    # Open the URL
    driver.get(URL)

    # Wait for Cloudflare to process
    time.sleep(10)

    # Find and access all staff profile links
    staff_links = set()
    base_url = "https://sunwayuniversity.edu.my/"

    get_links(staff_links, driver)

    for i in range(1,7):
        page = f"?page={i}"
        driver.get(urljoin(URL, page))
        WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, "block-sunway-content")))
        get_links(staff_links, driver)

    with open("src\\data\\staff_profiles.csv", mode="w", newline="", encoding="utf-8") as csv_file:
        # Define the CSV writer
        fieldnames = ["email", "name", "biography", "academic_and_professional_qualifications", "research_interests", "teaching_areas", "courses_taught", "notable_publications"]
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

        # Write the header row
        writer.writeheader()

        # Visit each staff profile link and extract data
        for link in staff_links:
            print(f"Accessing: {link}")
            full_url = urljoin(base_url, link)
            driver.get(full_url)  # Navigate to the staff profile page
            WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CLASS_NAME, "profileitem")))  # Wait for the page to load
            
            soup = BeautifulSoup(driver.page_source, "html.parser")
            div = soup.find("div", class_="profileitem")
            if div and (div.get_text().strip() == "Department of Smart Computing and Cyber Resilience" or div.get_text().strip() == "Department of Data Science and Artificial Intelligence"):
                # Extract data from the page
                json_data = extract(driver)

                 # Convert JSON string to a Python dictionary
                data_dict = json.loads(json_data)

                # Write the data to the CSV file
                print("WRITING")
                writer.writerow(data_dict)
finally:
    # Close the browser
    driver.quit()