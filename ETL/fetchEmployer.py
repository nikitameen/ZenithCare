#!/usr/bin/env python3
"""
Ollama Company Information Extractor
-----------------------------------
Extracts detailed company information using Ollama LLM from web searches.
Uses a configuration file instead of command-line arguments.

Usage:
    python fetchEmployer.py
"""

import json
import logging
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pandas as pd
import requests
from tqdm import tqdm


class CompanyInfoExtractor:
    """Extract company information using Ollama and web searches"""
    
    def __init__(self, config=None):
        """
        Initialize the extractor with settings from config file
        
        Args:
            config: Dictionary of configuration settings (if None, loads from config.json)
        """
        # Set default configuration
        self.config = {
            "ollama_model": "llama3",
            "batch_size": 10,
            "workers": 4,
            "log_level": "INFO",
            "input_file": "companies.csv",
            "output_file": None,
            "max_companies": None
        }
        
        # Load config file if no config provided
        if config is None:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "config.json")
            try:
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        loaded_config = json.load(f)
                        self.config.update(loaded_config)
                else:
                    print(f"Config file not found at {config_path}, using defaults")
                    # Create config directory and file with defaults
                    os.makedirs(os.path.dirname(config_path), exist_ok=True)
                    with open(config_path, 'w', encoding='utf-8') as f:
                        json.dump(self.config, f, indent=2)
            except Exception as e:
                print(f"Error loading config: {str(e)}, using defaults")
        else:
            self.config.update(config)
        
        # Extract config values
        self.ollama_model = self.config.get("ollama_model", "llama3")
        self.batch_size = self.config.get("batch_size", 10)
        self.workers = self.config.get("workers", 4)
        self.input_file = self.config.get("input_file", "companies.csv") 
        self.output_file = self.config.get("output_file")
        self.max_companies = self.config.get("max_companies")
        
        # Set up logging
        log_level_str = self.config.get("log_level", "INFO")
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)
        self.setup_logging(log_level)
        
        # Create output directories
        self.create_output_dirs()
        
    def setup_logging(self, log_level):
        """Set up logging"""
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"extraction_{timestamp}.log")
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initialized company information extractor with {self.ollama_model} model")
        self.logger.info(f"Using configuration: {self.config}")
        
    def create_output_dirs(self):
        """Create required output directories"""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(base_dir, "data")
        self.raw_text_dir = os.path.join(base_dir, "raw_text")
        
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.raw_text_dir, exist_ok=True)
        
        self.logger.info(f"Output directories created: {self.data_dir}, {self.raw_text_dir}")
        
    def query_ollama(self, prompt):
        """Send a query to Ollama and get the response"""
        try:
            # Command to query Ollama
            cmd = ["ollama", "run", self.ollama_model, prompt]
            
            # Run the command and capture output
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                self.logger.warning(f"Ollama query failed: {result.stderr}")
                return None
                
            return result.stdout.strip()
            
        except subprocess.TimeoutExpired:
            self.logger.warning("Ollama query timed out after 120 seconds")
            return None
        except Exception as e:
            self.logger.error(f"Error querying Ollama: {str(e)}")
            return None
    
    def search_company_info(self, company_name, state=None):
        """Search for company information online"""
        self.logger.info(f"Searching for information on {company_name}")
        
        # Construct search query
        search_query = company_name
        if state:
            search_query += f" {state}"
            
        # Add informational terms to get relevant results
        search_query += " company employees headquarters contacts business"
        
        # URLs to check (can add more sources here)
        sources = [
            f"https://www.google.com/search?q={search_query.replace(' ', '+')}",
            f"https://www.bloomberg.com/search?query={search_query.replace(' ', '+')}",
            f"https://www.zoominfo.com/c/{company_name.lower().replace(' ', '-')}",
            f"https://www.dnb.com/business-directory/company-profiles.{company_name.lower().replace(' ', '-')}.html"
        ]
        
        combined_text = ""
        
        # Define headers to avoid being blocked
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        # Search each source
        for url in sources:
            try:
                response = requests.get(url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    # Extract text content
                    text = response.text
                    combined_text += f"\n\nSource: {url}\n" + text[:50000]  # Limit text size
                
                # Be nice to servers
                time.sleep(1)
                
            except Exception as e:
                self.logger.warning(f"Error fetching {url}: {str(e)}")
        
        # Add specific searches for employee information
        employee_search_query = f"{company_name} number of employees locations staff count"
        try:
            employee_url = f"https://www.google.com/search?q={employee_search_query.replace(' ', '+')}"
            response = requests.get(employee_url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                combined_text += f"\n\nEmployee Info Source: {employee_url}\n" + response.text[:30000]
                
        except Exception as e:
            self.logger.warning(f"Error fetching employee info: {str(e)}")
            
        # Add specific searches for contact information
        contact_search_query = f"{company_name} contact email phone address"
        try:
            contact_url = f"https://www.google.com/search?q={contact_search_query.replace(' ', '+')}"
            response = requests.get(contact_url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                combined_text += f"\n\nContact Info Source: {contact_url}\n" + response.text[:30000]
                
        except Exception as e:
            self.logger.warning(f"Error fetching contact info: {str(e)}")
            
        # Save raw text for debugging
        self._save_raw_text(company_name, combined_text)
        
        return combined_text
    
    def _save_raw_text(self, company_name, text):
        """Save raw text to a file for debugging"""
        safe_name = re.sub(r'[^\w\-\.]', '_', company_name)
        file_path = os.path.join(self.raw_text_dir, f"{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(text)
            
        self.logger.debug(f"Saved raw text to {file_path}")
        
    def extract_company_details(self, company_name, text, state=None):
        """Extract structured company details from text using Ollama"""
        if not text.strip():
            self.logger.warning(f"No text to analyze for {company_name}")
            return {}
            
        # Create the prompt for Ollama
        prompt = f"""
You are an expert at extracting specific company information from text.

I need you to analyze this text about "{company_name}" and extract ONLY the following information:

1. Total number of employees (overall and at specific locations if mentioned)
2. Primary line of business and what the company does
3. Complete headquarters address with postal code
4. Other office locations (up to 3)
5. Key executives or contacts with their names, positions, and contact info (email/phone)

Format your response as a valid JSON object with these fields (use null for missing information):

{{
  "company_name": "{company_name}",
  "employees": {{
    "total": [total employee count or null],
    "locations": [
      {{
        "location": [location name],
        "count": [employee count at this location or null]
      }}
    ]
  }},
  "business": {{
    "description": [1-2 sentence description of what the company does],
    "industry": [primary industry or sector],
    "products_services": [list of main products or services]
  }},
  "headquarters": {{
    "address_line1": [street address],
    "address_line2": [suite/floor if applicable],
    "city": [city],
    "state_province": [state or province],
    "postal_code": [zip or postal code],
    "country": [country]
  }},
  "other_locations": [list of up to 3 other office addresses as strings],
  "key_contacts": [
    {{
      "name": [full name],
      "position": [job title],
      "email": [email address or null],
      "phone": [phone number or null]
    }}
  ]
}}

Analyze ONLY this text:
{text[:20000]}
"""

        # Query Ollama for extraction
        response = self.query_ollama(prompt)
        
        if not response:
            self.logger.warning(f"Failed to extract information for {company_name}")
            return {}
            
        # Try to parse JSON from the response
        try:
            # Try to find a JSON block in the response
            json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
            json_match = re.search(json_pattern, response)
            
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                # Try to find any JSON-like structure with curly braces
                json_pattern = r'({[\s\S]*})'
                json_match = re.search(json_pattern, response)
                
                if json_match:
                    json_str = json_match.group(1).strip()
                else:
                    # Use the whole response (assuming it's just JSON)
                    json_str = response
                    
            # Parse the JSON
            company_data = json.loads(json_str)
            
            # Add state if provided
            if state:
                company_data['state'] = state
                
            return company_data
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON from Ollama response for {company_name}: {str(e)}")
            self.logger.debug(f"Ollama response: {response}")
            return {}
        except Exception as e:
            self.logger.error(f"Unexpected error processing Ollama response for {company_name}: {str(e)}")
            return {}
            
    def process_company(self, company_data):
        """Process a single company to extract information"""
        company_name = company_data.get('Company', company_data.get('company_name', ''))
        state = company_data.get('State', company_data.get('state', company_data.get('State_Country', '')))
        
        if not company_name:
            self.logger.warning("Missing company name in input data")
            return {}
            
        self.logger.info(f"Processing company: {company_name} ({state if state else 'no state'})")
        
        # Search for company information
        text = self.search_company_info(company_name, state)
        
        # Extract company details
        extracted_data = self.extract_company_details(company_name, text, state)
        
        # Combine with original data
        if extracted_data:
            # Add original state if not already in extracted data
            if state and 'state' not in extracted_data:
                extracted_data['state'] = state
                
            self.logger.info(f"Successfully extracted data for {company_name}")
            return extracted_data
        else:
            # Return minimal data if extraction failed
            self.logger.warning(f"Failed to extract data for {company_name}")
            return {
                "company_name": company_name,
                "state": state,
                "extraction_status": "failed"
            }

    def process_companies(self):
        """Process companies from input file and save results to output file"""
        input_file = self.input_file
        
        # Determine output file if not specified
        output_file = self.output_file
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(self.data_dir, f"company_info_{timestamp}.json")
            
        self.logger.info(f"Processing companies from {input_file}")
        self.logger.info(f"Results will be saved to {output_file}")
            
        # Determine delimiter based on file extension and contents
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                sample = f.read(1024)
                if '|' in sample:
                    delimiter = '|'
                else:
                    delimiter = ','
        except Exception as e:
            self.logger.error(f"Error reading input file {input_file}: {str(e)}")
            return None
        
        try:
            # Read the input file
            df = pd.read_csv(input_file, delimiter=delimiter)
            
            # Check for company name column
            name_column = None
            for col in df.columns:
                if col.lower() in ['company', 'company_name', 'name', 'organization']:
                    name_column = col
                    break
                    
            if not name_column:
                self.logger.warning("Could not find standard company name column, using first column")
                name_column = df.columns[0]
                
            # Rename column for consistency
            df = df.rename(columns={name_column: 'Company'})
            
            # Check for state column
            state_column = None
            for col in df.columns:
                if col.lower() in ['state', 'state_code', 'state_country', 'region', 'location']:
                    state_column = col
                    break
                    
            if state_column:
                df = df.rename(columns={state_column: 'State'})
            else:
                self.logger.info("No state column found in data")
                # Add empty state column if none exists
                df['State'] = None
            
            # Limit to max_companies if specified
            if self.max_companies and self.max_companies > 0:
                df = df.head(self.max_companies)
                
            # Process companies in batches to avoid memory issues with large files
            all_results = []
            companies = df.to_dict('records')
            
            self.logger.info(f"Processing {len(companies)} companies in batches of {self.batch_size}")
            
            # Process in batches
            for i in range(0, len(companies), self.batch_size):
                batch = companies[i:i + self.batch_size]
                self.logger.info(f"Processing batch {i//self.batch_size + 1} ({len(batch)} companies)")
                
                batch_results = []
                with ThreadPoolExecutor(max_workers=self.workers) as executor:
                    futures = {executor.submit(self.process_company, company): company for company in batch}
                    
                    for future in tqdm(futures, desc=f"Batch {i//self.batch_size + 1}"):
                        company = futures[future]
                        try:
                            result = future.result()
                            if result:
                                batch_results.append(result)
                        except Exception as e:
                            self.logger.error(f"Error processing {company.get('Company', 'unknown')}: {str(e)}")
                
                # Save intermediate results
                all_results.extend(batch_results)
                
                # Save after each batch in case of interruption
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(all_results, f, indent=2)
                self.logger.info(f"Saved {len(all_results)} companies to {output_file}")
                
                # Sleep between batches to give the system a break
                if i + self.batch_size < len(companies):
                    time.sleep(5)
            
            self.logger.info(f"Completed processing {len(all_results)} companies")
            return output_file
            
        except Exception as e:
            self.logger.error(f"Error processing file {input_file}: {str(e)}")
            return None


def main():
    """Main function to run the extractor"""
    extractor = CompanyInfoExtractor()
    extractor.process_companies()


if __name__ == "__main__":
    main()