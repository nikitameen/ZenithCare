#!/usr/bin/env python3
"""
Comprehensive Company Location Extractor
---------------------------------------
Extracts ALL available company details including multiple locations, executives, financials, and more.
Uses a multi-source, multi-pass approach to ensure maximum data collection.
"""

import csv
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


class ComprehensiveCompanyExtractor:
    def __init__(self):
        # Configuration
        self.ollama_model = "llama3:70b"  # Use a more powerful model
        self.batch_size = 1
        self.workers = 8  # Increased parallel workers
        self.max_retries = 3  # Retry failed requests
        self.request_delay = 1  # Seconds between requests to avoid rate limiting
        
        # Enhanced CSV fields
        self.csv_fields = [
            "company_name",
            "legal_name",
            "state",
            "country",
            "website",
            "industry",
            "founded_year",
            "company_type",
            "revenue_range",
            "total_employees",
            "total_locations",
            "description",
            "linkedin_url",
            "crunchbase_url",
            "location_id",
            "location_type",
            "is_headquarters",
            "address_line1",
            "address_line2",
            "city",
            "state_province",
            "zip_postal",
            "country",
            "latitude",
            "longitude",
            "phone",
            "fax",
            "location_employees",
            "year_established",
            "facility_size",
            "products_services",
            "executive_name",
            "executive_title",
            "executive_email",
            "source",
            "last_updated",
            "data_quality_score"
        ]
        
        # Files and directories
        self.script_dir = os.path.dirname(os.path.abspath(__file__)) or "."
        self.input_file = os.path.join(self.script_dir, "companies.json")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_csv = os.path.join(self.script_dir, f"company_data_{timestamp}.csv")
        self.raw_dir = os.path.join(self.script_dir, "raw_data")
        self.log_file = os.path.join(self.script_dir, f"extraction_log_{timestamp}.txt")
        
        os.makedirs(self.raw_dir, exist_ok=True)
        
        # Enhanced web request settings
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.timeout = 15
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # Data source configurations
        self.data_sources = {
            "google": {
                "base_url": "https://www.google.com/search?q=",
                "queries": [
                    "{company} {state} site:linkedin.com/company",
                    "{company} {state} site:crunchbase.com",
                    "{company} {state} site:zoominfo.com",
                    "{company} {state} site:bloomberg.com",
                    "{company} {state} site:sec.gov",
                    "{company} {state} official website",
                    "{company} {state} locations offices",
                    "{company} {state} executives leadership team",
                    "{company} {state} annual report"
                ]
            },
            "api": {
                "crunchbase": "https://api.crunchbase.com/api/v4/entities/organizations/{company}",
                "zoominfo": "https://api.zoominfo.com/companies/{company}"
            }
        }
        
        # Check system requirements
        self._check_requirements()
        
    def _check_requirements(self):
        """Verify all system requirements are met"""
        try:
            # Check Ollama
            result = subprocess.run(["ollama", "list"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            if result.returncode != 0:
                raise Exception("Ollama not running or not installed")
                
            # Check BeautifulSoup
            from bs4 import BeautifulSoup
            print("System requirements verified")
            
        except Exception as e:
            print(f"ERROR: System requirement check failed: {e}")
            sys.exit(1)
    
    def _log(self, message):
        """Log messages to file and console"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        
        print(log_message)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_message + "\n")
    
    def _make_request(self, url, retry=0):
        """Robust request handling with retries"""
        try:
            time.sleep(self.request_delay)  # Rate limiting
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Check for blocking (e.g., captcha)
            if any(indicator in response.text.lower() for indicator in ['captcha', 'access denied', 'robot check']):
                raise Exception("Request blocked by CAPTCHA")
                
            return response
            
        except Exception as e:
            if retry < self.max_retries:
                delay = (retry + 1) * 5
                self._log(f"Retry {retry + 1} for {url} after {delay} seconds (error: {e})")
                time.sleep(delay)
                return self._make_request(url, retry + 1)
            else:
                self._log(f"Failed to fetch {url} after {self.max_retries} retries")
                return None
    
    def _fetch_google_results(self, query):
        """Fetch Google search results"""
        try:
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            response = self._make_request(url)
            
            if not response:
                return None
                
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Extract organic search results
            for g in soup.find_all('div', class_='g'):
                anchor = g.find('a')
                if anchor and anchor.get('href'):
                    title = g.find('h3')
                    snippet = g.find('div', class_='VwiC3b')
                    
                    results.append({
                        'title': title.text if title else '',
                        'url': anchor.get('href'),
                        'snippet': snippet.text if snippet else ''
                    })
            
            return results[:10]  # Return top 10 results
            
        except Exception as e:
            self._log(f"Error fetching Google results: {e}")
            return None
    
    def _fetch_company_website(self, company_name, state):
        """Find and fetch company website content"""
        try:
            # First try to find official website
            query = f"{company_name} {state} official website"
            results = self._fetch_google_results(query)
            
            if not results:
                return None
                
            # Look for likely official website in results
            official_site = None
            for result in results:
                url = result['url'].lower()
                if any(domain in url for domain in ['linkedin.com', 'crunchbase.com', 'zoominfo.com']):
                    continue
                    
                if company_name.lower().replace(' ', '') in url:
                    official_site = result['url']
                    break
                    
            if not official_site:
                official_site = results[0]['url']
                
            # Fetch website content
            response = self._make_request(official_site)
            if not response:
                return None
                
            # Extract relevant pages
            content = response.text[:100000]  # Limit size
            
            # Try to find About, Contact, Locations pages
            about_pages = self._extract_internal_links(response.text, ['about', 'company', 'contact', 'locations'])
            
            additional_content = ""
            for page in about_pages[:3]:  # Fetch up to 3 additional pages
                try:
                    page_url = page if page.startswith('http') else f"{official_site.rstrip('/')}/{page.lstrip('/')}"
                    page_response = self._make_request(page_url)
                    if page_response:
                        additional_content += f"\n\n--- PAGE: {page_url} ---\n{page_response.text[:50000]}"
                except:
                    continue
                    
            return {
                'main_page': content,
                'additional_pages': additional_content,
                'url': official_site
            }
            
        except Exception as e:
            self._log(f"Error fetching company website: {e}")
            return None
    
    def _extract_internal_links(self, html, keywords):
        """Extract internal links containing keywords"""
        soup = BeautifulSoup(html, 'html.parser')
        links = set()
        
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            if any(keyword in href for keyword in keywords):
                links.add(a['href'])
                
        return list(links)
    
    def _fetch_linkedin_data(self, company_name, state):
        """Fetch LinkedIn company data"""
        try:
            # Find LinkedIn profile
            query = f"{company_name} {state} site:linkedin.com/company"
            results = self._fetch_google_results(query)
            
            if not results:
                return None
                
            linkedin_url = None
            for result in results:
                if 'linkedin.com/company/' in result['url'].lower():
                    linkedin_url = result['url']
                    break
                    
            if not linkedin_url:
                return None
                
            # Fetch LinkedIn page
            response = self._make_request(linkedin_url)
            if not response:
                return None
                
            # Extract basic info
            soup = BeautifulSoup(response.text, 'html.parser')
            
            data = {
                'url': linkedin_url,
                'description': '',
                'employees': '',
                'industries': '',
                'locations': []
            }
            
            # Try to extract description
            desc_tag = soup.find('div', class_='about-us__description')
            if desc_tag:
                data['description'] = desc_tag.get_text(strip=True)
                
            # Try to extract employee count
            emp_tag = soup.find('div', {'data-test-id': 'about-us__employee-count'})
            if emp_tag:
                data['employees'] = emp_tag.get_text(strip=True)
                
            # Try to extract industries
            industry_tags = soup.find_all('li', class_='about-us__industry')
            if industry_tags:
                data['industries'] = ', '.join(tag.get_text(strip=True) for tag in industry_tags)
                
            return data
            
        except Exception as e:
            self._log(f"Error fetching LinkedIn data: {e}")
            return None
    
    def _fetch_crunchbase_data(self, company_name):
        """Fetch Crunchbase data"""
        try:
            # Find Crunchbase profile
            query = f"{company_name} site:crunchbase.com"
            results = self._fetch_google_results(query)
            
            if not results:
                return None
                
            crunchbase_url = None
            for result in results:
                if 'crunchbase.com/organization/' in result['url'].lower():
                    crunchbase_url = result['url']
                    break
                    
            if not crunchbase_url:
                return None
                
            # Fetch Crunchbase page
            response = self._make_request(crunchbase_url)
            if not response:
                return None
                
            # Extract JSON-LD data if available
            soup = BeautifulSoup(response.text, 'html.parser')
            ld_json = soup.find('script', type='application/ld+json')
            
            data = {
                'url': crunchbase_url,
                'data': {}
            }
            
            if ld_json:
                try:
                    data['data'] = json.loads(ld_json.string)
                except:
                    pass
                    
            return data
            
        except Exception as e:
            self._log(f"Error fetching Crunchbase data: {e}")
            return None
    
    def _fetch_sec_data(self, company_name):
        """Fetch SEC EDGAR data with enhanced parsing"""
        try:
            # Step 1: Search for company
            search_url = f"https://www.sec.gov/cgi-bin/browse-edgar?company={company_name.replace(' ', '+')}&owner=exclude&action=getcompany"
            response = self._make_request(search_url)
            
            if not response:
                return None
                
            # Step 2: Extract CIK
            cik_match = re.search(r'CIK=(\d+)', response.text)
            if not cik_match:
                return None
                
            cik = cik_match.group(1).zfill(10)
            
            # Step 3: Get all filings
            filings_url = f"https://www.sec.gov/Archives/edgar/data/{cik[:10]}/{cik}-index.html"
            filings_response = self._make_request(filings_url)
            
            if not filings_response:
                return None
                
            # Find most recent 10-K or 10-Q
            filing_types = ['10-K', '10-Q', '8-K', 'S-1']
            filings = []
            
            for filing_type in filing_types:
                matches = re.findall(f'<a href="([^"]*{filing_type}[^"]*\.htm)"', filings_response.text)
                if matches:
                    filings.extend(matches[:2])  # Get up to 2 of each type
                    
            if not filings:
                return None
                
            # Process filings
            sec_data = {
                'cik': cik,
                'filings': []
            }
            
            for filing in filings[:3]:  # Process up to 3 filings
                try:
                    filing_url = f"https://www.sec.gov{filing}" if not filing.startswith('http') else filing
                    filing_response = self._make_request(filing_url)
                    
                    if filing_response:
                        # Extract relevant sections
                        soup = BeautifulSoup(filing_response.text, 'html.parser')
                        
                        # Get all text for processing
                        filing_text = soup.get_text('\n', strip=True)
                        
                        # Find business address
                        address_pattern = r'principal\s*executive\s*offices?[:\s]*([^\n]+)\n([^\n]+)\n([^\n]+)'
                        address_match = re.search(address_pattern, filing_text, re.IGNORECASE)
                        
                        address = None
                        if address_match:
                            address = {
                                'line1': address_match.group(1).strip(),
                                'line2': address_match.group(2).strip(),
                                'city_state_zip': address_match.group(3).strip()
                            }
                            
                        sec_data['filings'].append({
                            'url': filing_url,
                            'type': filing_type,
                            'text': filing_text[:50000],  # Limit size
                            'address': address
                        })
                except:
                    continue
                    
            return sec_data if sec_data['filings'] else None
            
        except Exception as e:
            self._log(f"Error fetching SEC data: {e}")
            return None
    
    def _fetch_zoominfo_data(self, company_name, state):
        """Attempt to fetch ZoomInfo data"""
        try:
            # Find ZoomInfo profile
            query = f"{company_name} {state} site:zoominfo.com"
            results = self._fetch_google_results(query)
            
            if not results:
                return None
                
            zoominfo_url = None
            for result in results:
                if 'zoominfo.com/c/' in result['url'].lower():
                    zoominfo_url = result['url']
                    break
                    
            if not zoominfo_url:
                return None
                
            # Fetch ZoomInfo page
            response = self._make_request(zoominfo_url)
            if not response:
                return None
                
            # Extract basic info
            soup = BeautifulSoup(response.text, 'html.parser')
            
            data = {
                'url': zoominfo_url,
                'description': '',
                'employees': '',
                'revenue': '',
                'industries': '',
                'locations': []
            }
            
            # Try to extract description
            desc_tag = soup.find('div', class_='companyDescription')
            if desc_tag:
                data['description'] = desc_tag.get_text(strip=True)
                
            # Try to extract key metrics
            metric_tags = soup.find_all('div', class_='metric')
            for tag in metric_tags:
                label = tag.find('div', class_='label').get_text(strip=True).lower()
                value = tag.find('div', class_='value').get_text(strip=True)
                
                if 'employee' in label:
                    data['employees'] = value
                elif 'revenue' in label:
                    data['revenue'] = value
                    
            return data
            
        except Exception as e:
            self._log(f"Error fetching ZoomInfo data: {e}")
            return None
    
    def _fetch_all_sources(self, company_name, state):
        """Fetch data from all available sources in parallel"""
        self._log(f"Starting data collection for: {company_name} ({state})")
        
        # Prepare source functions
        sources = [
            ('website', lambda: self._fetch_company_website(company_name, state)),
            ('linkedin', lambda: self._fetch_linkedin_data(company_name, state)),
            ('crunchbase', lambda: self._fetch_crunchbase_data(company_name)),
            ('sec', lambda: self._fetch_sec_data(company_name)),
            ('zoominfo', lambda: self._fetch_zoominfo_data(company_name, state)),
            ('google', lambda: self._fetch_google_results(f"{company_name} {state}"))
        ]
        
        # Execute in parallel
        results = {}
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {executor.submit(func): name for name, func in sources}
            
            for future in futures:
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    self._log(f"Error in {name} source: {e}")
                    results[name] = None
                    
        # Combine all data
        combined_data = {
            'company_name': company_name,
            'state': state,
            'sources': results,
            'raw_text': ''
        }
        
        # Build raw text for LLM processing
        raw_text = f"COMPANY: {company_name}\nSTATE: {state}\n\n"
        
        for source_name, data in results.items():
            if data:
                if isinstance(data, dict):
                    raw_text += f"\n--- {source_name.upper()} DATA ---\n{json.dumps(data, indent=2)[:10000]}\n"
                elif isinstance(data, list):
                    raw_text += f"\n--- {source_name.upper()} RESULTS ---\n"
                    for item in data[:5]:  # Limit to top 5 results
                        raw_text += f"{json.dumps(item, indent=2)}\n"
                else:
                    raw_text += f"\n--- {source_name.upper()} ---\n{str(data)[:10000]}\n"
        
        combined_data['raw_text'] = raw_text
        
        # Save raw data
        raw_file = os.path.join(self.raw_dir, f"{company_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(raw_file, 'w', encoding='utf-8') as f:
            json.dump(combined_data, f, indent=2)
            
        self._log(f"Completed data collection for {company_name}. Saved raw data to {raw_file}")
        
        return combined_data
    
    def _generate_extraction_prompt(self, company_name, state, raw_text):
        """Generate a comprehensive extraction prompt for the LLM"""
        return f"""
Extract ALL available information about "{company_name}" from {state} from the provided data sources.
Include every possible detail about the company and its locations.

Return a JSON object with this structure:
{{
  "company_name": "{company_name}",
  "legal_name": "official legal name if different",
  "state": "{state}",
  "country": "primary country of operation",
  "website": "official website URL",
  "industry": "primary industry",
  "industries": ["array", "of", "all", "industries"],
  "founded_year": "year founded",
  "company_type": "public/private/ngo/etc.",
  "revenue_range": "annual revenue estimate",
  "total_employees": "total number of employees",
  "employee_range": "employee count range",
  "total_locations": "total number of locations",
  "description": "company description",
  "linkedin_url": "LinkedIn company page",
  "crunchbase_url": "Crunchbase profile URL",
  "executives": [
    {{
      "name": "executive name",
      "title": "job title",
      "email": "email if available",
      "linkedin": "LinkedIn profile if available"
    }}
  ],
  "locations": [
    {{
      "location_id": 1,
      "location_type": "Headquarters/Branch/Subsidiary/Factory/Office/etc.",
      "is_headquarters": true/false,
      "address_line1": "street address",
      "address_line2": "suite or floor if applicable",
      "city": "city name",
      "state_province": "state or province",
      "zip_postal": "zip or postal code",
      "country": "country name",
      "latitude": "geocoordinates if available",
      "longitude": "geocoordinates if available",
      "phone": "phone number if available",
      "fax": "fax number if available",
      "location_employees": "number of employees at this location",
      "year_established": "year this location was established",
      "facility_size": "square footage if available",
      "products_services": "specific to this location",
      "source": "where this information was found"
    }}
  ],
  "financials": {{
    "revenue": "annual revenue if available",
    "profit": "profit if available",
    "funding": "total funding if startup",
    "valuation": "company valuation if available"
  }},
  "products_services": ["array", "of", "offerings"],
  "competitors": ["array", "of", "competitors"],
  "source_data_quality": {{
    "website": 0-100,
    "linkedin": 0-100,
    "crunchbase": 0-100,
    "sec": 0-100,
    "zoominfo": 0-100
  }},
  "last_updated": "{datetime.now().isoformat()}"
}}

IMPORTANT RULES:
1. Include EVERY location mentioned in any source
2. Include ALL available details for each location
3. Never omit information - if a field is missing, use null
4. Never invent information - only use what's in the sources
5. For locations without addresses but with city names, include them
6. Mark the most complete address as headquarters if not specified
7. Include all executives found in any source
8. Include all financial data points found
9. Score each source's data quality (0-100)

DATA TO ANALYZE:
{raw_text[:50000]}

Return ONLY the JSON object without any commentary or explanation.
"""
    
    def _extract_with_llm(self, prompt):
        """Extract data using Ollama with enhanced error handling"""
        try:
            self._log("Starting LLM extraction...")
            
            # Call Ollama with the prompt
            cmd = ["ollama", "run", self.ollama_model, prompt]
            
            start_time = time.time()
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120  # 2 minute timeout
            )
            elapsed = time.time() - start_time
            
            output = result.stdout.decode('utf-8', errors='ignore')
            
            if result.returncode != 0:
                self._log(f"LLM error: {result.stderr.decode('utf-8')}")
                return None
                
            self._log(f"LLM extraction completed in {elapsed:.1f} seconds")
            
            # Try to extract JSON
            json_data = self._extract_json(output)
            
            if not json_data:
                self._log("Failed to extract valid JSON from LLM output")
                return None
                
            return json_data
            
        except subprocess.TimeoutExpired:
            self._log("LLM extraction timed out after 2 minutes")
            return None
            
        except Exception as e:
            self._log(f"Error in LLM extraction: {e}")
            return None
    
    def _extract_json(self, text):
        """Robust JSON extraction from text"""
        try:
            # Try parsing directly first
            try:
                return json.loads(text)
            except:
                pass
                
            # Try extracting from markdown code block
            code_match = re.search(r'```(?:json)?\s*({[\s\S]*?})\s*```', text)
            if code_match:
                return json.loads(code_match.group(1))
                
            # Try finding the first/last JSON object
            brace_match = re.search(r'({[\s\S]*})', text)
            if brace_match:
                return json.loads(brace_match.group(1))
                
            return None
            
        except Exception as e:
            self._log(f"JSON extraction error: {e}")
            return None
    
    def _create_fallback_data(self, company_name, state):
        """Create minimal fallback data structure"""
        return {
            "company_name": company_name,
            "state": state,
            "locations": [
                {
                    "location_id": 1,
                    "location_type": "Unknown",
                    "is_headquarters": None,
                    "city": None,
                    "state_province": state,
                    "source": "fallback"
                }
            ]
        }
    
    def _transform_to_csv_rows(self, company_data):
        """Transform the extracted data into CSV rows"""
        rows = []
        
        if not company_data or 'locations' not in company_data:
            return rows
            
        # Base company info
        base_info = {
            "company_name": company_data.get("company_name", ""),
            "legal_name": company_data.get("legal_name", ""),
            "state": company_data.get("state", ""),
            "country": company_data.get("country", ""),
            "website": company_data.get("website", ""),
            "industry": company_data.get("industry", ""),
            "founded_year": company_data.get("founded_year", ""),
            "company_type": company_data.get("company_type", ""),
            "revenue_range": company_data.get("revenue_range", ""),
            "total_employees": company_data.get("total_employees", ""),
            "total_locations": len(company_data.get("locations", [])),
            "description": company_data.get("description", ""),
            "linkedin_url": company_data.get("linkedin_url", ""),
            "crunchbase_url": company_data.get("crunchbase_url", ""),
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_quality_score": company_data.get("source_data_quality", {}).get("overall", 0)
        }
        
        # Process each location
        for location in company_data.get("locations", []):
            row = base_info.copy()
            row.update({
                "location_id": location.get("location_id", ""),
                "location_type": location.get("location_type", ""),
                "is_headquarters": location.get("is_headquarters", ""),
                "address_line1": location.get("address_line1", ""),
                "address_line2": location.get("address_line2", ""),
                "city": location.get("city", ""),
                "state_province": location.get("state_province", ""),
                "zip_postal": location.get("zip_postal", ""),
                "country": location.get("country", ""),
                "latitude": location.get("latitude", ""),
                "longitude": location.get("longitude", ""),
                "phone": location.get("phone", ""),
                "fax": location.get("fax", ""),
                "location_employees": location.get("location_employees", ""),
                "year_established": location.get("year_established", ""),
                "facility_size": location.get("facility_size", ""),
                "products_services": location.get("products_services", ""),
                "source": location.get("source", "")
            })
            
            # Add executive info if available
            executives = company_data.get("executives", [])
            if executives:
                row.update({
                    "executive_name": executives[0].get("name", ""),
                    "executive_title": executives[0].get("title", ""),
                    "executive_email": executives[0].get("email", "")
                })
            
            rows.append(row)
            
        return rows
    
    def process_company(self, company_data):
        """Process a single company through the full pipeline"""
        company_name = company_data.get("Company") or company_data.get("company_name")
        state = company_data.get("State") or company_data.get("state")
        
        if not company_name:
            self._log("Skipping company with no name")
            return []
            
        self._log(f"\nStarting processing for: {company_name} ({state})")
        
        try:
            # Step 1: Fetch data from all sources
            start_time = time.time()
            combined_data = self._fetch_all_sources(company_name, state)
            fetch_time = time.time() - start_time
            
            # Step 2: Extract structured data with LLM
            prompt = self._generate_extraction_prompt(company_name, state, combined_data['raw_text'])
            
            llm_start = time.time()
            extracted_data = self._extract_with_llm(prompt)
            llm_time = time.time() - llm_start
            
            if not extracted_data:
                self._log("LLM extraction failed, using fallback data")
                extracted_data = self._create_fallback_data(company_name, state)
                
            # Step 3: Transform to CSV rows
            rows = self._transform_to_csv_rows(extracted_data)
            
            total_time = time.time() - start_time
            self._log(f"Completed processing for {company_name} in {total_time:.1f} seconds "
                     f"(fetch: {fetch_time:.1f}s, LLM: {llm_time:.1f}s). "
                     f"Found {len(rows)} locations.")
                     
            return rows
            
        except Exception as e:
            self._log(f"Error processing {company_name}: {e}")
            return self._transform_to_csv_rows(self._create_fallback_data(company_name, state))
    
    def load_companies(self):
        """Load companies from input file with validation"""
        try:
            if os.path.exists(self.input_file):
                with open(self.input_file, 'r', encoding='utf-8') as f:
                    companies = json.load(f)
                    
                # Validate structure
                valid_companies = []
                for company in companies:
                    if isinstance(company, dict) and ('Company' in company or 'company_name' in company):
                        valid_companies.append(company)
                        
                self._log(f"Loaded {len(valid_companies)} valid companies from {self.input_file}")
                return valid_companies
                
            else:
                self._log(f"Input file not found: {self.input_file}")
                # Return example data
                return [
                    {"Company": "Stripe", "State": "CA"},
                    {"Company": "Palantir Technologies", "State": "CO"},
                    {"Company": "Snowflake Inc.", "State": "CA"},
                    {"Company": "SpaceX", "State": "CA"},
                    {"Company": "Robinhood Markets", "State": "CA"}
                ]
                
        except Exception as e:
            self._log(f"Error loading companies: {e}")
            return []
    
    def initialize_output(self):
        """Initialize the output CSV file"""
        try:
            with open(self.output_csv, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.csv_fields)
                writer.writeheader()
                
            self._log(f"Initialized output CSV: {self.output_csv}")
            return True
            
        except Exception as e:
            self._log(f"Error initializing CSV: {e}")
            return False
    
    def write_results(self, rows):
        """Write results to CSV"""
        if not rows:
            return
            
        try:
            with open(self.output_csv, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.csv_fields)
                
                for row in rows:
                    # Clean None values
                    clean_row = {k: (v if v is not None else "") for k, v in row.items()}
                    writer.writerow(clean_row)
                    
            self._log(f"Wrote {len(rows)} rows to CSV")
            
        except Exception as e:
            self._log(f"Error writing to CSV: {e}")
    
    def run(self):
        """Run the full extraction pipeline"""
        self._log("\n=== Comprehensive Company Data Extractor ===")
        self._log(f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Step 1: Load companies
        companies = self.load_companies()
        if not companies:
            self._log("No companies to process. Exiting.")
            return
            
        # Step 2: Initialize output
        if not self.initialize_output():
            self._log("Failed to initialize output. Exiting.")
            return
            
        # Step 3: Process companies
        total_companies = len(companies)
        total_locations = 0
        start_time = time.time()
        
        self._log(f"Processing {total_companies} companies...\n")
        
        for i, company in enumerate(companies, 1):
            company_name = company.get("Company") or company.get("company_name")
            self._log(f"\n[{i}/{total_companies}] Processing: {company_name}")
            
            # Process the company
            rows = self.process_company(company)
            
            # Write results
            if rows:
                total_locations += len(rows)
                self.write_results(rows)
                
        # Final summary
        total_time = time.time() - start_time
        avg_time = total_time / total_companies if total_companies > 0 else 0
        
        self._log("\n=== Extraction Complete ===")
        self._log(f"Processed {total_companies} companies")
        self._log(f"Extracted {total_locations} total locations")
        self._log(f"Average processing time: {avg_time:.1f} seconds per company")
        self._log(f"Total elapsed time: {total_time:.1f} seconds")
        self._log(f"Results saved to: {self.output_csv}")
        self._log(f"Raw data saved to: {self.raw_dir}")
        self._log(f"Log file: {self.log_file}")


if __name__ == "__main__":
    extractor = ComprehensiveCompanyExtractor()
    extractor.run()
    