import requests
from bs4 import BeautifulSoup
import csv
import time
import os
import argparse
import logging
from datetime import datetime
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor

def scrape_edgar_companies(state_code, pages=5, records_per_page=100):
    """
    Scrape company information from SEC EDGAR database for a specific state.
    
    Args:
        state_code (str): Two-letter state code (e.g., 'TX')
        pages (int): Number of pages to scrape (default 5, which gives 500 records)
        records_per_page (int): Number of records per page (default 100)
    
    Returns:
        list: List of dictionaries containing company information
    """
    logger = logging.getLogger(__name__)
    all_companies = []
    base_url = "https://www.sec.gov/cgi-bin/browse-edgar"
    
    # Create directory for saving files if it doesn't exist
    os.makedirs('sec_data', exist_ok=True)
    
    # Define headers to mimic a browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    # Add an option to save partial results after each page
    partial_file = f"sec_data/partial_{state_code}.csv"
    fieldnames = ['CIK', 'Company', 'State_Country', 'CIK_Link']
    
    # Iterate through pages
    for page_num in tqdm(range(pages), desc=f"Scraping {state_code} pages"):
        start_record = page_num * records_per_page
        
        # Prepare parameters for the request
        params = {
            'action': 'getcompany',
            'State': state_code,
            'owner': 'exclude',
            'match': '',
            'start': start_record,
            'count': records_per_page,
            'hidefilings': 0
        }
        
        # Make the request with exponential backoff
        max_retries = 5
        retry_delay = 1
        success = False
        
        for retry in range(max_retries):
            try:
                response = requests.get(base_url, params=params, headers=headers, timeout=30)
                response.raise_for_status()  # Raise exception for bad status codes
                success = True
                break
            except requests.exceptions.RequestException as e:
                logger.warning(f"Error on page {page_num+1} for state {state_code} (attempt {retry+1}/{max_retries}): {e}")
                wait_time = retry_delay * (2 ** retry)
                logger.info(f"Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
        
        if not success:
            logger.error(f"Failed to retrieve page {page_num+1} for state {state_code} after {max_retries} attempts")
            continue
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the table containing company data
        table = soup.find('table', class_='tableFile2')
        
        if not table:
            logger.warning(f"No table found on page {page_num+1} for state {state_code}")
            continue
            
        # Extract company data from table rows
        rows = table.find_all('tr')
        page_companies = []
        
        # Skip header row
        for row in rows[1:]:
            cells = row.find_all('td')
            if len(cells) >= 3:  # Ensure we have enough cells
                # Get CIK with link
                cik_cell = cells[0]
                cik = cik_cell.text.strip()
                
                # Try to get the CIK link
                cik_link = ""
                a_tag = cik_cell.find('a')
                if a_tag and 'href' in a_tag.attrs:
                    cik_link = "https://www.sec.gov" + a_tag['href'] if a_tag['href'].startswith('/') else a_tag['href']
                
                company_name = cells[1].text.strip()
                state_country = cells[2].text.strip() if len(cells) > 2 else ""
                
                # Clean up CIK by removing leading zeros
                cik_clean = cik.lstrip('0')
                
                company_data = {
                    'CIK': cik_clean,
                    'Company': company_name,
                    'State_Country': state_country,
                    'CIK_Link': cik_link
                }
                all_companies.append(company_data)
                page_companies.append(company_data)
        
        # Save partial results after each page
        if page_companies:
            save_mode = 'a' if os.path.exists(partial_file) and page_num > 0 else 'w'
            with open(partial_file, save_mode, newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter='|')
                
                # Write header only for the first page
                if save_mode == 'w':
                    writer.writeheader()
                
                writer.writerows(page_companies)
            
            logger.info(f"Page {page_num+1}/{pages} for {state_code}: Added {len(page_companies)} companies (Total: {len(all_companies)})")
        else:
            logger.warning(f"No companies found on page {page_num+1} for state {state_code}")
        
        # Be nice to the SEC server
        time.sleep(2)
    
    return all_companies

def save_to_csv(companies, state_code):
    """
    Save company data to a CSV file with pipe delimiter.
    
    Args:
        companies (list): List of dictionaries containing company information
        state_code (str): Two-letter state code
    """
    logger = logging.getLogger(__name__)
    
    if not companies:
        logger.warning(f"No companies to save for state {state_code}")
        return
        
    # Create output directory if it doesn't exist
    output_dir = "sec_data"
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate timestamp for filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{output_dir}/sec_companies_{state_code}_{timestamp}.csv"
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = companies[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter='|')
        
        writer.writeheader()
        writer.writerows(companies)
        
    logger.info(f"Saved {len(companies)} companies to {filename}")
    
    # Also save a simplified version with just the main fields
    simplified_filename = f"{output_dir}/sec_companies_{state_code}_simplified_{timestamp}.csv"
    
    with open(simplified_filename, 'w', newline='', encoding='utf-8') as csvfile:
        simplified_fieldnames = ['CIK', 'Company', 'State_Country']
        writer = csv.DictWriter(csvfile, fieldnames=simplified_fieldnames, delimiter='|')
        
        writer.writeheader()
        for company in companies:
            simplified_company = {field: company.get(field, '') for field in simplified_fieldnames}
            writer.writerow(simplified_company)
    
    logger.info(f"Saved simplified data to {simplified_filename}")
    
    # Remove partial file if it exists
    partial_file = f"{output_dir}/partial_{state_code}.csv"
    if os.path.exists(partial_file):
        try:
            os.remove(partial_file)
            logger.info(f"Removed partial file {partial_file}")
        except OSError as e:
            logger.warning(f"Could not remove partial file {partial_file}: {e}")
    
    return filename

def setup_logging():
    """Set up logging configuration"""
    log_dir = "sec_logs"
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"sec_scraper_{timestamp}.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)

def process_state(state, pages_per_state):
    """Process a single state"""
    logger = logging.getLogger(__name__)
    logger.info(f"Starting to scrape data for state: {state}")
    
    try:
        companies = scrape_edgar_companies(state, pages=pages_per_state)
        save_to_csv(companies, state)
        logger.info(f"Completed scraping for state: {state} - Found {len(companies)} companies")
        return True
    except Exception as e:
        logger.error(f"Error processing state {state}: {str(e)}")
        return False

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Scrape SEC EDGAR database for company information')
    parser.add_argument('--state', type=str, help='Two-letter state code to scrape (e.g., TX)')
    parser.add_argument('--pages', type=int, default=5, help='Number of pages to scrape per state (default: 5)')
    parser.add_argument('--all-states', action='store_true', help='Scrape all states')
    parser.add_argument('--parallel', type=int, default=1, help='Number of parallel scraping processes (default: 1)')
    args = parser.parse_args()
    
    # Set up logging
    logger = setup_logging()
    
    # List of all state codes
    all_state_codes = [
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
    ]
    
    # Determine which states to scrape
    if args.state:
        state_codes = [args.state.upper()]
    elif args.all_states:
        state_codes = all_state_codes
    else:
        # Default to TX if no state is specified
        state_codes = ['TX']
    
    # Number of pages to fetch for each state (default 5 pages * 100 records = 500 records)
    pages_per_state = args.pages
    
    logger.info(f"Starting SEC EDGAR scraper for states: {', '.join(state_codes)}")
    logger.info(f"Scraping {pages_per_state} pages per state ({pages_per_state * 100} companies per state)")
    
    # Process states
    if args.parallel > 1 and len(state_codes) > 1:
        logger.info(f"Using parallel processing with {args.parallel} workers")
        with ThreadPoolExecutor(max_workers=args.parallel) as executor:
            futures = {executor.submit(process_state, state, pages_per_state): state for state in state_codes}
            for future in tqdm(futures, desc="Processing states"):
                state = futures[future]
                try:
                    result = future.result()
                    if result:
                        logger.info(f"Successfully processed state: {state}")
                    else:
                        logger.warning(f"Failed to process state: {state}")
                except Exception as e:
                    logger.error(f"Exception processing state {state}: {str(e)}")
    else:
        for state in state_codes:
            process_state(state, pages_per_state)

if __name__ == "__main__":
    main()