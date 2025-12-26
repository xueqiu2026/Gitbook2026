from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from urllib.parse import urljoin, urlparse
from utils.logger import get_logger
import time

class HierarchyManager:
    def __init__(self, use_selenium=True, verbose=False):
        self.use_selenium = use_selenium
        self.verbose = verbose
        self.logger = get_logger()
        self.hierarchy_map = {}  # url -> {'level': int, 'order': int, 'parent': str}

    def build_hierarchy(self, start_url):
        """Build hierarchy map from the starting URL using Selenium"""
        if not self.use_selenium:
            self.logger.warning("Selenium needed for hierarchy but disabled")
            return {}

        self.logger.info("🌳 Building hierarchy tree using Selenium...")
        
        driver = None
        try:
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            # Suppress logs
            options.add_argument('--log-level=3')
            options.add_argument('--window-size=1920,1080')

            driver = webdriver.Chrome(options=options)
            driver.get(start_url)
            
            # Allow dynamic content to load
            time.sleep(3)
            
            # Find the best sidebar candidate
            # Simple selectors might catch breadcrumbs or top-nav
            candidates = driver.find_elements(By.CSS_SELECTOR, "nav, aside, div[class*='sidebar'], [data-testid='sidebar']")
            self.logger.debug(f"Found {len(candidates)} sidebar candidates")
            
            sidebar = None
            max_links = 0
            
            for i, cand in enumerate(candidates):
                try:
                    # Quick heuristic: Identify the "real" sidebar by link density
                    links = cand.find_elements(By.TAG_NAME, 'a')
                    count = len(links)
                    self.logger.debug(f"Candidate {i}: {count} links")
                    # Check if it looks like a sidebar (vertical list usually, but hard to tell)
                    # Just picking the one with MOST links is usually correct for documentation sites
                    if count > max_links and count > 3:
                        max_links = count
                        sidebar = cand
                except:
                    continue
            
            if sidebar:
                self.logger.info(f"Selected sidebar with {max_links} links")
            
            if not sidebar:
                self.logger.warning("Could not find sidebar for hierarchy analysis")
                return {}

            # Expand the sidebar to reveal all lazy-loaded items
            self._expand_sidebar(driver, sidebar)

            # Parse the tree
            self._parse_dom_tree(sidebar, start_url)
            
            self.logger.info(f"🌳 Hierarchy built: {len(self.hierarchy_map)} pages mapped")
            return self.hierarchy_map

        except Exception as e:
            self.logger.error(f"Error building hierarchy: {e}")
            if self.verbose:
                import traceback
                self.logger.debug(traceback.format_exc())
            return {}
        finally:
            if driver:
                driver.quit()

    def _expand_sidebar(self, driver, sidebar):
        """Recursively expand all collapsed items in the sidebar using 'rotate-0' heuristic"""
        self.logger.info("  🔓 Expanding sidebar items...")
        
        # Max iterations to prevent infinite loops (deep nesting usually < 10 levels)
        max_iterations = 20
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Find SVGs with 'rotate-0' which indicates a collapsed state in this GitBook theme
            # Note: We must re-query every time because clicking changes the DOM
            try:
                # Target SVGs that have 'rotate-0' class.
                # Use a specific selector to avoid non-sidebar arrows if any
                collapsed_icons = sidebar.find_elements(By.CSS_SELECTOR, "svg.rotate-0")
                
                if not collapsed_icons:
                    self.logger.debug("  No more collapsed items found.")
                    break
                
                clicked_in_this_pass = 0
                
                for icon in collapsed_icons:
                    try:
                        # SVGs might report as not displayed in Selenium, so skip check
                        # or check parent.
                        
                        # Scroll to element to ensure it's in viewport
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", icon)
                        time.sleep(0.1)
                        
                        # Try standard click first
                        try:
                            icon.click()
                        except:
                            # Fallback to JS click on parent if SVG click fails
                            driver.execute_script("arguments[0].parentNode.click();", icon)
                            
                        clicked_in_this_pass += 1
                        time.sleep(0.1) # Small delay for animation
                    except Exception as e:
                        # Stale element or intercepted
                        pass
                
                if clicked_in_this_pass == 0:
                    # If we found items but couldn't click any, break to avoid infinite loop
                     self.logger.debug("  Found collapsed items but could not click any.")
                     break
                     
                self.logger.info(f"  [Pass {iteration}] Expanded {clicked_in_this_pass} items")
                
                # Wait for content to load/animate
                time.sleep(0.5)
                
            except Exception as e:
                self.logger.warning(f"  Expansion error: {e}")
                break

    def _parse_dom_tree(self, root_element, base_url):
        """
        Parses the DOM tree using Strict Recursion based on user specification.
        Root: div[data-testid="toc-scroll-container"] > first ul
        Nodes: li -> Type A (Leaf) or Type B (Group)
        Recursion: Find nested ul in li subtree
        """
        from bs4 import BeautifulSoup
        html = root_element.get_attribute('outerHTML')
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1. Locate Root Container
        # Strict Selector: div[data-testid="toc-scroll-container"]
        container = soup.find('div', {'data-testid': 'toc-scroll-container'})
        
        if not container:
            self.logger.warning("Strict Parsing: 'toc-scroll-container' not found! Falling back to root soup.")
            container = soup
            
        # 2. Find First Top-Level UL
        root_ul = container.find('ul')
        if not root_ul:
             self.logger.warning("Strict Parsing: No root UL found in container.")
             return

        # 3. Recursive Parsing Function
        order_counter = 0

        def clean_url(u):
            if not u: return ""
            u = urljoin(base_url, u)
            u = u.split('#')[0]
            return u

        def parse_recursive(ul_node, level=0, current_section=None):
            nonlocal order_counter
            
            # Iterate all LI children (Strict Hierarchy)
            # Usage of recursive=False ensures we process this list's items only
            list_items = ul_node.find_all('li', recursive=False)
            
            for li in list_items:
                # Determine Node Type
                
                # Search for direct link (Type A)
                node_type = None
                title = None
                url = None
                
                # Direct Link check (Type A)
                # Look for 'a' that is a direct child OR inside a wrapper div but "conceptually" direct
                # User strict mode: li > a (Leaf)
                direct_a = li.find('a', recursive=False)
                
                # If not direct child, sometimes it's wrapped in div. 
                # e.g. li > div > a. But we must be careful not to mistake a nested list link.
                if not direct_a:
                     direct_wrapper = li.find('div', recursive=False)
                     if direct_wrapper:
                         direct_a = direct_wrapper.find('a', recursive=False)

                if direct_a:
                    node_type = 'A'
                    title = direct_a.get_text(strip=True)
                    url = direct_a.get('href')
                else:
                    # Group Header check (Type B)
                    # li > div (Text)
                    # Find first div direct child that has text
                    # (And verify it's not just a wrapper for ul?)
                    for child in li.find_all('div', recursive=False):
                         # If this div has text and NO 'a', treat as title
                         if not child.find('a'):
                             text = child.get_text(strip=True)
                             if text:
                                  node_type = 'B'
                                  title = text
                                  break
                
                # Process Node Data
                cleaned_url = None
                if node_type == 'A' and url:
                    cleaned_url = clean_url(url)
                    if cleaned_url and cleaned_url not in self.hierarchy_map:
                         self.hierarchy_map[cleaned_url] = {
                            'title': title,           # CRITICAL FIX: Save the title!
                            'level': level,
                            'order': order_counter,
                            'section': current_section
                        }
                         order_counter += 1
                
                # Determine Nested Section Context
                next_section = current_section
                if node_type == 'B':
                    next_section = title
                    self.logger.debug(f"  [Group] Found Section: {title}")
                
                # Recursion Logic
                # Check for nested UL anywhere in subtree
                # Use find() to get the *first* nested UL.
                nested_ul = li.find('ul') 
                if nested_ul:
                     parse_recursive(nested_ul, level + 1, next_section)

        # Start Recursion
        self.logger.info("Starting Strict Recursive Parsing...")
        parse_recursive(root_ul, level=1, current_section=None)

        
    def get_info(self, url):
        """Get hierarchy info for a URL"""
        # normalize url
        # remove anchor, query
        u = url.split('#')[0].split('?')[0]
        return self.hierarchy_map.get(u)
