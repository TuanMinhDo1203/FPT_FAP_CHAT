from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from webdriver_manager.microsoft import EdgeChromiumDriverManager
import pandas as pd
import re
import time
import logging
from typing import List, Optional, Dict, Any

from .constants import (
    TEXT_FIELDS, COLUMNS_TO_REMOVE, 
    ASSESSMENT_CATEGORIES, TEXT_COLUMNS_TO_DROP
)
from .models import SubjectInfo, ParsedBlock

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FLMScraper:
    def __init__(self, edge_driver_path, user_data_dir):
        """Initialize the FLM scraper with necessary configurations."""
        self.edge_driver_path = edge_driver_path
        self.user_data_dir = user_data_dir
        self.driver = None
        self.data = []
        self.headers = []
        self.df = None
        self.parsed_df = None
        self.final_df = None
        self.text_fields_clean = [
            f.replace(' ', '_').replace('(', '').replace(')', '').replace("'", '') 
            for f in TEXT_FIELDS
        ]

    def setup_driver(self):
        """Set up the Edge WebDriver with custom options."""
        try:
            options = Options()
            options.add_argument(f"user-data-dir={self.user_data_dir}")
            options.add_argument("--disable-blink-features=AutomationControlled")

            # Use webdriver_manager to automatically download and manage the correct driver version
            service = Service(EdgeChromiumDriverManager().install())
            self.driver = webdriver.Edge(service=service, options=options)
            logger.info("WebDriver setup successful")
        except Exception as e:
            logger.error(f"Failed to setup WebDriver: {str(e)}")
            raise

    def wait_and_find_element(self, by, value, timeout=10):
        """Wait for and find an element with explicit wait."""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            logger.error(f"Timeout waiting for element: {value}")
            raise
        except NoSuchElementException:
            logger.error(f"Element not found: {value}")
            raise

    def login_to_flm(self):
        """Handle the login process to FLM."""
        try:
            # Navigate to FLM
            self.driver.get("https://flm.fpt.edu.vn/")
            logger.info("Navigated to FLM homepage")
            time.sleep(4)  # Allow page to load

            # Click login button
            login_button = self.wait_and_find_element(
                By.XPATH, '//a[@href="/Home/LoginWithFEID"]'
            )
            login_button.click()
            logger.info("Clicked login button")
            time.sleep(3)

            # Click Gmail button
            gmail_btn = self.wait_and_find_element(
                By.XPATH, 
                "//a[contains(@href, 'External/Challenge') and contains(@href, 'scheme=Google')]"
            )
            gmail_btn.click()
            logger.info("Clicked Gmail login button")
            time.sleep(1)

        except Exception as e:
            logger.error(f"Error during login process: {str(e)}")
            raise

    def search_curriculum(self, keyword):
        """Search for curriculum using the given keyword."""
        try:
            # Navigate to curriculum
            curriculum_link = self.wait_and_find_element(
                By.XPATH, 
                '//*[@id="panelStudentFeatures"]/div/div/div/div/div/div/div/div/a[1]'
            )
            curriculum_link.click()
            logger.info("Navigated to curriculum page")
            time.sleep(2)

            # Enter search keyword
            input_box = self.wait_and_find_element(By.ID, "txtKeyword")
            input_box.send_keys(keyword)
            logger.info(f"Entered search keyword: {keyword}")
            time.sleep(1)

            # Click search button
            search_btn = self.wait_and_find_element(By.ID, 'btnSearch')
            search_btn.click()
            logger.info("Clicked search button")
            time.sleep(3)

        except Exception as e:
            logger.error(f"Error during curriculum search: {str(e)}")
            raise

    def get_first_program_details(self):
        """Get details of the first program in search results."""
        try:
            first_program = self.wait_and_find_element(
                By.XPATH, 
                '//a[contains(@href, "CurriculumDetails.aspx")]'
            )
            program_name = first_program.text
            program_href = first_program.get_attribute('href')
            
            # Navigate to program details
            self.driver.get(program_href)
            logger.info(f"Navigated to program: {program_name}")

            # Wait for subjects table and process it
            table = self.wait_and_find_element(By.ID, "gvSubs")
            self._process_subject_table(table)
            
            # Create initial DataFrame
            self.df = pd.DataFrame(self.data, columns=self.headers)
            
            # Start HTML analysis
            return self.analyze_html()

        except Exception as e:
            logger.error(f"Error getting program details: {str(e)}")
            raise

    def _process_subject_table(self, table):
        """Process the main subject table and extract data."""
        # Get headers
        self.headers = [th.text.strip() for th in table.find_elements(By.TAG_NAME, "th")]
        self.headers.extend(["SubjectLink", "RawHTML", "ParentSubject", "BelongToCombo"])

        # Process rows
        rows = table.find_elements(By.TAG_NAME, "tr")[1:]  # Skip header row
        for i in range(len(rows)):
            table = self.wait_and_find_element(By.ID, "gvSubs")
            rows = table.find_elements(By.TAG_NAME, "tr")[1:]
            row = rows[i]
            self._process_subject_row(row)

    def _process_subject_row(self, row):
        """Process a single subject row and handle special cases."""
        subject_info = self._extract_subject_info(row)
        
        if self._is_combo_subject(subject_info.name):
            self._handle_combo_subject(subject_info)
        elif self._is_elective_subject(subject_info.name):
            self._handle_elective_subject(subject_info)
        else:
            self._handle_regular_subject(subject_info)

    def _extract_subject_info(self, row) -> SubjectInfo:
        """Extract basic subject information from row."""
        cols = row.find_elements(By.TAG_NAME, "td")
        return SubjectInfo(
            name=cols[0].text.strip(),
            data=[col.text.strip() for col in cols],
            link=self._get_subject_link(cols[1])
        )

    def _get_subject_link(self, cell) -> Optional[str]:
        """Extract subject link from cell if exists."""
        a_tags = cell.find_elements(By.TAG_NAME, "a")
        return a_tags[0].get_attribute("href") if a_tags else None

    def _is_combo_subject(self, subject_name: str) -> bool:
        """Check if subject is a combo subject."""
        return "COM" in subject_name

    def _is_elective_subject(self, subject_name: str) -> bool:
        """Check if subject is an elective subject."""
        return "ELE" in subject_name

    def _handle_combo_subject(self, subject_info: SubjectInfo):
        """Handle combo subjects (COM)."""
        try:
            # Add parent combo subject
            self._add_subject_data(subject_info.data, subject_info.link, "", subject_info.name, "")
            
            if subject_info.link:
                self.driver.get(subject_info.link)
                time.sleep(1)
                
                # Process combo sections
                sub_subjects = self._collect_combo_subjects()
                self._process_combo_subjects(sub_subjects, subject_info)
                
                # Return to main page
                self.driver.back()
                self.wait_and_find_element(By.ID, "gvSubs")
                
        except Exception as e:
            logger.error(f"Error processing combo subject: {str(e)}")
            raise

    def _collect_combo_subjects(self) -> List[Dict[str, Any]]:
        """Collect information about combo subjects."""
        sub_list = []
        combos = self.driver.find_elements(By.CSS_SELECTOR, "div.auto-style11 > h3")
        
        for combo in combos:
            combo_name = combo.text.strip()
            table_element = combo.find_element(By.XPATH, "following-sibling::table[1]")
            sub_rows = table_element.find_elements(By.TAG_NAME, "tr")[1:]
            
            for sub_row in sub_rows:
                sub_info = self._extract_combo_subject_info(sub_row, combo_name)
                if sub_info:
                    sub_list.append(sub_info)
        
        return sub_list

    def _extract_combo_subject_info(self, sub_row, combo_name: str) -> Optional[Dict[str, Any]]:
        """Extract information about a single combo subject."""
        sub_cols = sub_row.find_elements(By.TAG_NAME, "td")
        if len(sub_cols) < 2:
            return None
            
        sub_data = [col.text.strip() for col in sub_cols[:2]]
        a_sub = sub_cols[1].find_elements(By.TAG_NAME, "a")
        sub_link = a_sub[0].get_attribute("href") if a_sub else None
        
        return {
            'data': sub_data,
            'link': sub_link,
            'combo_name': combo_name
        }

    def _process_combo_subjects(self, sub_subjects: List[Dict[str, Any]], parent_info: SubjectInfo):
        """Process each combo subject's HTML content."""
        for sub in sub_subjects:
            raw_html = ""
            if sub['link']:
                self.driver.get(sub['link'])
                time.sleep(1)
                raw_html = self.driver.page_source
                self.driver.back()
                time.sleep(1)
            
            # Add parent subject information to sub_data
            sub_data = sub['data']
            sub_data.extend([
                parent_info.data[2],  # semester
                parent_info.data[3],  # credits
                parent_info.data[4]   # prerequisites
            ])
            
            self._add_subject_data(sub_data, sub['link'], raw_html, parent_info.name, sub['combo_name'])

    def _handle_elective_subject(self, subject_info: SubjectInfo):
        """Handle elective subjects (ELE/DBI)."""
        try:
            # Add parent elective subject
            self._add_subject_data(subject_info.data, subject_info.link, "", subject_info.name, "")
            
            if subject_info.link:
                self.driver.get(subject_info.link)
                time.sleep(1)
                
                # First pass: collect all sub-subject info
                sub_info_list = []
                sub_table = self.driver.find_element(By.CSS_SELECTOR, "table[style*='margin-bottom']")
                sub_rows = sub_table.find_elements(By.TAG_NAME, "tr")[1:]
                
                for sub_row in sub_rows:
                    sub_cols = sub_row.find_elements(By.TAG_NAME, "td")
                    sub_data = [col.text.strip() for col in sub_cols[:2]]
                    
                    # Add parent subject information
                    sub_data.extend([
                        subject_info.data[2],  # semester
                        subject_info.data[3],  # credits
                        subject_info.data[4]   # prerequisites
                    ])
                    
                    # Get subject link
                    a_sub = sub_cols[1].find_elements(By.TAG_NAME, "a")
                    sub_link = a_sub[0].get_attribute("href") if a_sub else ""
                    
                    # Store info for later processing
                    sub_info_list.append((sub_data, sub_link))
                
                # Second pass: process each sub-subject's HTML content
                for sub_data, sub_link in sub_info_list:
                    raw_html = ""
                    if sub_link:
                        self.driver.get(sub_link)
                        time.sleep(1)
                        raw_html = self.driver.page_source
                        self.driver.back()
                        time.sleep(1)
                    
                    self._add_subject_data(sub_data, sub_link, raw_html, subject_info.name, "")
                
                # Return to main page
                self.driver.back()
                self.wait_and_find_element(By.ID, "gvSubs")
                
        except Exception as e:
            logger.error(f"Error processing elective subject: {str(e)}")
            raise

    def _handle_regular_subject(self, subject_info: SubjectInfo):
        """Handle regular subjects."""
        try:
            raw_html = ""
            if subject_info.link:
                # Navigate to subject page
                self.driver.get(subject_info.link)
                time.sleep(1)

                try:
                    # Check for sub-table and get additional link if exists
                    sub_table = self.driver.find_element(By.CSS_SELECTOR, "table[style*='margin-bottom']")
                    sub_rows = sub_table.find_elements(By.TAG_NAME, "tr")[1]
                    sub_cols = sub_rows.find_elements(By.TAG_NAME, "td")
                    a_sub = sub_cols[1].find_elements(By.TAG_NAME, "a")
                    sub_link = a_sub[0].get_attribute("href") if a_sub else ""

                    # If sub-link exists, get its HTML content
                    if sub_link:
                        self.driver.get(sub_link)
                        time.sleep(1)
                        raw_html = self.driver.page_source
                        self.driver.back()
                        time.sleep(1)
                except Exception as e:
                    logger.debug(f"No sub-table found for subject: {str(e)}")
                    raw_html = self.driver.page_source

                # Return to main page
                self.driver.back()
                self.wait_and_find_element(By.ID, "gvSubs")

            # Add data to the list
            self._add_subject_data(subject_info.data, subject_info.link, raw_html, "", "")
        except Exception as e:
            logger.error(f"Error processing regular subject: {str(e)}")
            raise

    

    def _add_subject_data(self, row_data, subject_link, raw_html, parent_subject, belong_to_combo):
        """Add processed subject data to the data list."""
        row_data.extend([subject_link, raw_html, parent_subject, belong_to_combo])
        self.data.append(row_data)

    # HTML Analysis Methods
    def parse_single_html(self, html):
        """Parse a single HTML content and extract structured data."""
        if pd.isna(html):
            logger.debug("Empty HTML content")
            return {}

        try:
            soup = BeautifulSoup(html, 'html.parser')
            tables = soup.find_all('table')
            result = {}

            if not tables:
                logger.debug("No tables found in HTML")
                return result

            # Process main information table
            self._process_main_html_table(tables[0], result)
            
            # Process additional tables
            self._process_additional_html_tables(tables[1:], result)

            return result

        except Exception as e:
            logger.error(f"Error parsing HTML: {str(e)}")
            return {}

    def _process_main_html_table(self, table, result):
        """Process the main information table from HTML."""
        try:
            for row in table.find_all('tr'):
                cols = row.find_all(['td', 'th'])
                if len(cols) >= 2:
                    key = cols[0].get_text(strip=True)
                    value = cols[1].get_text(strip=True)
                    result[key] = value
        except Exception as e:
            logger.error(f"Error processing main HTML table: {str(e)}")

    def _process_additional_html_tables(self, tables, result):
        """Process additional tables from HTML with green headers."""
        try:
            for table in tables:
                if table is None:
                    continue

                prev = table.find_previous(
                    lambda tag: tag.has_attr('style') and '#23AC68' in tag['style']
                )
                
                if prev:
                    title_text = prev.get_text(strip=True)
                    title_clean = self._clean_title(title_text)
                    result[title_clean] = str(table)
        except Exception as e:
            logger.error(f"Error processing additional HTML tables: {str(e)}")

    def _html_table_to_text(self, html):
        """Convert HTML table to plain text format."""
        if pd.isna(html):
            return ""
        soup = BeautifulSoup(html, "html.parser")
        lines = []
        for row in soup.find_all("tr"):
            cols = []
            for col in row.find_all(['td', 'th']):
                text = col.get_text(strip=True).replace('\n', ' ')
                # Nếu nội dung có dấu phẩy thì bao trong dấu ngoặc kép
                if ',' in text:
                    text = f'"{text}"'
                cols.append(text)
            line = ",".join(cols)
            lines.append(line)
        return "\n".join(lines)
    def _combine_text_fields(self, row):
        """Combine all text fields into a single content field with headers."""
        try:
            parts = []
            for field in TEXT_FIELDS:
                content = row.get(field + '_text', '').strip()
                if content:
                    parts.append(f"### {field}\n{content}")
            return "\n\n".join(parts)
        except Exception as e:
            logger.error(f"Error combining text fields: {str(e)}")
            return ""

    @staticmethod
    def _clean_title(title):
        """Clean and format table titles."""
        return re.sub(r'^\d+\s*', '', title).strip().lower()

    def analyze_html(self):
        """Analyze the HTML content in the DataFrame."""
        try:
            # Parse HTML data
            logger.info("Starting HTML analysis")
            parsed_data = self.df['RawHTML'].apply(self.parse_single_html)
            self.parsed_df = pd.DataFrame(parsed_data.tolist())
            
            # Clean and process the parsed data
            self._clean_parsed_data()
            
            # Process HTML tables to text
            self._process_html_tables()
            
            # Create final DataFrame
            self._create_final_dataframe()
            
            logger.info("HTML analysis completed successfully")
            return self.final_df

        except Exception as e:
            logger.error(f"Error during HTML analysis: {str(e)}")
            raise

    def _process_html_tables(self):
        """Process HTML tables and create text and content fields."""
        try:
            logger.info("Processing HTML tables to text")
            
            # Convert HTML tables to text for each field
            for field in TEXT_FIELDS:
                self.parsed_df[field + '_text'] = self.parsed_df[field].apply(
                    self._html_table_to_text
                )
            
            # Create combined content field
            self.parsed_df['content'] = self.parsed_df.apply(
                self._combine_text_fields, 
                axis=1
            )
            
            logger.info("HTML table processing completed")
            
        except Exception as e:
            logger.error(f"Error processing HTML tables: {str(e)}")
            raise

    def _clean_parsed_data(self):
        """Clean and process the parsed data."""
        try:
            # Handle sessions column
            self._process_sessions_column()
            
            # Remove unnecessary columns
            self._remove_unnecessary_columns()
            
            logger.info("Data cleaning completed")

        except Exception as e:
            logger.error(f"Error during data cleaning: {str(e)}")
            raise

    def _process_sessions_column(self):
        """Process and clean the sessions column."""
        try:
            # Fill missing sessions values
            self.parsed_df["sessions (45'/session)"] = self.parsed_df.apply(
                lambda row: row[''] if pd.isna(row["sessions (45'/session)"]) 
                and pd.notna(row['']) else row["sessions (45'/session)"],
                axis=1
            )

            # Clear used values from empty column
            self.parsed_df.loc[
                self.parsed_df["sessions (45'/session)"].notna() & 
                self.parsed_df[''].notna(), 
                ''
            ] = pd.NA

            # Remove empty column if all values are NA
            if self.parsed_df[''].isna().all():
                self.parsed_df = self.parsed_df.drop(columns=[''])

        except Exception as e:
            logger.error(f"Error processing sessions column: {str(e)}")
            raise

    def _remove_unnecessary_columns(self):
        """Remove unnecessary columns from parsed data."""
        columns_to_remove = [
            'Syllabus Name:', 
            'Syllabus English:',
            'Subject Code:',
            'NoCredit:', 
            'Pre-Requisite:'
        ]
        self.parsed_df = self.parsed_df.drop(columns=columns_to_remove)

    def _create_final_dataframe(self):
        """Create the final DataFrame by combining original and parsed data."""
        self.final_df = pd.concat([self.df, self.parsed_df], axis=1)

    def save_to_csv(self, filename="analyzed_subjects.csv"):
        """Save the analyzed data to a CSV file."""
        if self.final_df is not None:
            self.final_df.to_csv(filename, index=False, encoding="utf-8-sig")
            logger.info(f"Data saved to {filename}")
        else:
            logger.warning("No analyzed data available to save")

    def close(self):
        """Close the WebDriver."""
        if self.driver:
            self.driver.quit()
            logger.info("WebDriver closed")

    def process_subject_data(self):
        """Process and clean the subject data after HTML analysis."""
        if self.final_df is None:
            logger.warning("No data available to process")
            return

        # Create copy of original order
        self.final_df['_original_order'] = range(len(self.final_df))

        # Group duplicate subject codes
        self._group_duplicate_subjects()

        # Process text blocks for each field
        self._process_text_blocks()

        # Clean up columns
        self._cleanup_columns()

        logger.info("Subject data processing completed")

    def _group_duplicate_subjects(self):
        """Group and merge rows with duplicate subject codes."""
        try:
            # Define aggregation rules
            columns = self.final_df.columns.tolist()
            agg_dict = {
                col: 'first' for col in columns 
                if col not in ['SubjectCode', 'ParentSubject', '_original_order']
            }
            agg_dict['ParentSubject'] = lambda x: ', '.join(x.dropna().unique())

            # Group duplicate subjects
            df_grouped = self.final_df.groupby('SubjectCode', as_index=False).agg(agg_dict)

            # Remove old duplicate rows
            df_cleaned = self.final_df[~self.final_df['SubjectCode'].isin(df_grouped['SubjectCode'])]

            # Combine and restore original order
            self.final_df = pd.concat([df_cleaned, df_grouped], ignore_index=True)
            self.final_df = (self.final_df.sort_values(by='_original_order')
                           .drop(columns='_original_order')
                           .reset_index(drop=True))

            logger.info("Duplicate subjects grouped successfully")
        except Exception as e:
            logger.error(f"Error grouping duplicate subjects: {str(e)}")
            raise

    def _parse_text_block(self, text, subject_code):
        """Parse a text block into structured data."""
        blocks = re.split(r'\n-{3,}\n', text.strip())
        result = []

        for block in blocks:
            entry = {'SubjectCode': subject_code}
            lines = block.strip().split('\n')
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    entry[key.strip()] = value.strip()
            result.append(entry)
        
        return result

    def _extract_df_by_column(self, col_name):
        """Extract structured data from a specific column."""
        all_rows = []
        for _, row in self.final_df.iterrows():
            subject_code = row['SubjectCode']
            content = row[col_name]
            if pd.notna(content):
                parsed = self._parse_text_block(content, subject_code)
                all_rows.extend(parsed)
        return pd.DataFrame(all_rows)

    def _process_text_blocks(self):
        """Process text blocks for all relevant columns."""
        try:
            # Extract data from each text column
            self.df_materials = self._extract_df_by_column('material(s)_text_processed')
            self.df_los = self._extract_df_by_column('lo(s)_text_processed')
            self.df_sessions = self._extract_df_by_column("sessions (45'/session)_text_processed")
            self.df_assessments = self._extract_df_by_column('assessment(s)_text_processed')
            self.df_questions = self._extract_df_by_column('constructive question(s)_text_processed')

            # Normalize assessment categories if assessments exist
            if hasattr(self, 'df_assessments') and not self.df_assessments.empty:
                self._normalize_assessment_categories()

            logger.info("Text blocks processed successfully")
        except Exception as e:
            logger.error(f"Error processing text blocks: {str(e)}")
            raise

    def _normalize_assessment_categories(self):
        """Normalize assessment category names."""
        def normalize_category(cat: str) -> str:
            cat = cat.strip()
            return ASSESSMENT_CATEGORIES.get(cat, cat)

        self.df_assessments['Category_normalized'] = self.df_assessments['Category'].apply(normalize_category)
        self.df_assessments['Category'] = self.df_assessments['Category_normalized']
        self.df_assessments = self.df_assessments.drop(columns=['Category_normalized'])

    def _cleanup_columns(self):
        """Remove processed text columns from the final DataFrame."""
        self.final_df = self.final_df.drop(columns=TEXT_COLUMNS_TO_DROP)
        logger.info("Cleaned up processed text columns")

def main():
    # Configuration
    USER_DATA_DIR = r"C:\Users\DO TUAN MINH\AppData\Local\Microsoft\Edge\User Data\Default"
    
    # No need for EDGE_DRIVER_PATH anymore
    scraper = FLMScraper(None, USER_DATA_DIR)  # or update __init__ to not require edge_driver_path
    
    try:
        scraper.setup_driver()
        scraper.login_to_flm()
        scraper.search_curriculum("SE")
        df = scraper.get_first_program_details()
        
        # Process the scraped data
        scraper.process_subject_data()
        
        # Save both the final DataFrame and individual component DataFrames
        scraper.save_to_csv(filename="SE_analyzed_subjects.csv")
        
        # Save component DataFrames if they exist
        if hasattr(scraper, 'df_materials'):
            scraper.df_materials.to_csv("materials.csv", index=False, encoding="utf-8-sig")
        if hasattr(scraper, 'df_los'):
            scraper.df_los.to_csv("learning_outcomes.csv", index=False, encoding="utf-8-sig")
        if hasattr(scraper, 'df_sessions'):
            scraper.df_sessions.to_csv("sessions.csv", index=False, encoding="utf-8-sig")
        if hasattr(scraper, 'df_assessments'):
            scraper.df_assessments.to_csv("assessments.csv", index=False, encoding="utf-8-sig")
        if hasattr(scraper, 'df_questions'):
            scraper.df_questions.to_csv("questions.csv", index=False, encoding="utf-8-sig")
            
        print(df.head())
        
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
    finally:
        scraper.close()

if __name__ == "__main__":
    main() 