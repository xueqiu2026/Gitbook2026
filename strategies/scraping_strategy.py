"""
Enhanced Scraping Strategy - Web scraping with navigation discovery
"""

import asyncio
import aiohttp
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from utils.logger import get_logger

# Import selenium dependencies lazily or checkIfAvailable
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except ImportError:
    webdriver = None

class ScrapingStrategy:
    def __init__(self, max_concurrent=15, delay=0.1, timeout=30, 
                 use_selenium=False, verbose=False):
        self.max_concurrent = max_concurrent
        self.delay = delay
        self.timeout = timeout
        self.use_selenium = use_selenium
        self.verbose = verbose
        self.logger = get_logger()

        # Navigation selectors for different GitBook layouts
        self.nav_selectors = [
            # Modern GitBook
            '[data-testid="sidebar"] a[href]',
            '[data-testid="navigation"] a[href]',
            '.sidebar a[href]',
            '.navigation a[href]',

            # Legacy GitBook
            '.book-summary a[href]',
            '.summary a[href]',

            # Generic
            'nav a[href]',
            '.nav a[href]',
            '.toc a[href]',
            'aside a[href]',
        ]

    async def extract_pages(self, url, section_path=None):
        """Extract pages using web scraping"""
        try:
            # Step 1: Discover navigation links
            nav_links = await self._discover_navigation(url)

            if not nav_links:
                # Fallback - at least get the main page
                nav_links = [{'url': url, 'title': 'Main Page'}]

            # Step 2: Filter by section if specified
            if section_path:
                nav_links = [link for link in nav_links 
                           if section_path.lower() in link['url'].lower()]

            # Step 3: Download all pages
            pages = await self._download_pages(nav_links)

            return pages

        except Exception as e:
            self.logger.debug(f"Scraping strategy error: {e}")
            return None

    async def _discover_navigation(self, url):
        """Discover navigation links from the main page"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(self.timeout)) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return []

                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    links = []
                    base_domain = urlparse(url).netloc

                    # Try each navigation selector
                    for selector in self.nav_selectors:
                        nav_links = soup.select(selector)

                        for link in nav_links:
                            href = link.get('href', '')
                            text = link.get_text().strip()

                            if not href or not text:
                                continue

                            # Convert to absolute URL
                            abs_url = urljoin(url, href)

                            # Validate URL
                            if self._is_valid_page_url(abs_url, base_domain):
                                links.append({
                                    'url': abs_url,
                                    'title': text[:100]  # Limit title length
                                })

                        # If we found good links with this selector, use them
                        if len(links) > 5:
                            break

                    # Remove duplicates
                    unique_links = []
                    seen_urls = set()

                    for link in links:
                        if link['url'] not in seen_urls:
                            unique_links.append(link)
                            seen_urls.add(link['url'])

                    self.logger.info(f"Discovered {len(unique_links)} navigation links")
                    return unique_links

        except Exception as e:
            self.logger.debug(f"Navigation discovery error: {e}")
            return []

    def _is_valid_page_url(self, url, base_domain):
        """Check if URL is a valid page to scrape"""
        if not url or url.startswith('#'):
            return False

        parsed = urlparse(url)

        # Must be same domain
        if parsed.netloc != base_domain:
            return False

        # Skip non-content URLs
        skip_patterns = [
            r'/search', r'/login', r'/logout', r'/edit',
            r'/admin', r'/api/', r'/assets/', r'/static/',
            r'\.(css|js|json|xml|rss|txt)$',
            r'\.(jpg|png|gif|svg|ico|pdf)$',
            r'mailto:', r'tel:', r'javascript:'
        ]

        url_lower = url.lower()
        for pattern in skip_patterns:
            if re.search(pattern, url_lower):
                return False

        return True

    async def _download_pages(self, nav_links):
        """Download content from all navigation links"""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        pages = []

        async def download_page(link):
            async with semaphore:
                await asyncio.sleep(self.delay)

                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(self.timeout)) as session:
                        async with session.get(link['url']) as response:
                            if response.status == 200:
                                html = await response.text()
                                content, parsed_title = self._extract_main_content(html)

                                if content and (len(content.strip()) > 50 or parsed_title):  # Minimum content length or has title
                                    pages.append({
                                        'title': parsed_title or link.get('title', 'Untitled Page'),
                                        'url': link['url'],
                                        'content': content,
                                        'source': 'scraping'
                                    })

                except Exception as e:
                    self.logger.debug(f"Error downloading {link['url']}: {e}")

        # Download all pages concurrently
        tasks = [download_page(link) for link in nav_links]
        await asyncio.gather(*tasks, return_exceptions=True)

        return pages

    def _extract_main_content(self, html):
        """Extract main content from HTML page"""
        soup = BeautifulSoup(html, 'html.parser')

        # Remove unwanted elements
        unwanted_selectors = [
            'nav', 'header', 'footer', 'aside', 
            '.sidebar', '.navigation', '.nav', '.header', '.footer',
            '.breadcrumb', '.breadcrumbs', '.page-edit-link',
            'script', 'style', 'noscript',
            '.search', '.share', '.comments'
        ]

        for selector in unwanted_selectors:
            for element in soup.select(selector):
                element.decompose()

        # Fix Math / KaTeX
        # KaTeX often has an annotation tag with the source
        # Structure: <span class="katex"><span class="katex-mathml"><math><semantics><annotation encoding="application/x-tex">SOURCE</annotation>...
        katex_elements = soup.select('.katex')
        for k in katex_elements:
            annotation = k.select_one('annotation[encoding="application/x-tex"]')
            if annotation:
                latex_source = annotation.get_text()
                # Determine if block or inline? 
                # Usually hard to tell, but we can default to inline for safety or double dollar for distinct blocks.
                # If the parent is a paragraph or div by itself, maybe block.
                # Let's try to detect current style. 
                # GitBook often sets class 'katex-display' for block math.
                is_display = 'katex-display' in k.get('class', []) or k.select_one('.katex-display')
                
                if is_display:
                     k.replace_with(f"\n$$\n{latex_source}\n$$\n")
                else:
                     k.replace_with(f"${latex_source}$")
            else:
                # If no annotation, we might want to just unwrap or keep text?
                # But typically the '.katex-html' part is what makes the garbage text.
                # If we can't find source, proceed with care.
                # Often removing .katex-html helps if there is a mathml fallback
                pass

        # Also explicit removal of katex-html if we missed the replacement above 
        # (e.g. if annotation was missing but katex structure exists)
        for junk in soup.select('.katex-html'):
             junk.decompose()

        # Find main content area
        content_selectors = [
            '[data-testid="page-content"]',
            '.page-content',
            '.content',
            'main',
            'article',
            '.post-content',
            '.entry-content'
        ]

        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                # TRY TO FIND TITLE HERE FIRST
                h1 = content_elem.find('h1')
                title = h1.get_text().strip() if h1 else None
                
                # Convert to markdown-like text
                content = self._html_to_text(content_elem)
                return content, title

        # Fallback - use body content
        body = soup.find('body')
        if body:
            return self._html_to_text(body), None

        return soup.get_text(), None

    def _html_to_text(self, element):
        """Convert HTML element to clean text with basic markdown formatting"""
        # This is a simple HTML to text converter
        # For production, you might want to use a proper HTML-to-markdown library

        text_lines = []

        def process_element(elem):
            if elem.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                level = int(elem.name[1])
                heading = '#' * level + ' ' + elem.get_text().strip()
                text_lines.append(heading)
                text_lines.append('')
            elif elem.name == 'p':
                text_lines.append(elem.get_text().strip())
                text_lines.append('')
            elif elem.name in ['ul', 'ol']:
                for li in elem.find_all('li', recursive=False):
                    text_lines.append('- ' + li.get_text().strip())
                text_lines.append('')
            elif elem.name == 'code':
                text_lines.append('`' + elem.get_text().strip() + '`')
            elif elem.name == 'pre':
                code_text = elem.get_text().strip()
                text_lines.append('```')
                text_lines.append(code_text)
                text_lines.append('```')
                text_lines.append('')
            elif elem.name == 'img':
                src = elem.get('src', '')
                alt = elem.get('alt', 'image')
                if src:
                    text_lines.append(f"![{alt}]({src})")
                    text_lines.append('')
            elif elem.name in ['span', 'a', 'strong', 'em', 'b', 'i', 'sub', 'sup', 'small', 'math']:
                # Handle inline elements by merging with previous text
                text = elem.get_text(separator=' ').strip()
                if text:
                    if text_lines and not text_lines[-1].endswith('\n') and not text_lines[-1].strip() == '':
                        text_lines[-1] += " " + text
                    else:
                        text_lines.append(text)
            
            elif elem.name == 'table' or elem.get('role') in ['table', 'grid']:
                text_lines.append('\n')
                # Find rows: standard <tr> or elements with role="row"
                rows = elem.find_all(lambda t: t.name == 'tr' or t.get('role') == 'row', recursive=True)
                
                table_data = []
                max_cols = 0
                for row in rows:
                    # Cells: <td>, <th> or role="cell", "columnheader"
                    cells = row.find_all(lambda t: t.name in ['td', 'th'] or t.get('role') in ['cell', 'columnheader', 'gridcell'], recursive=False)
                    if not cells: # Try one level deeper for complex structures
                         cells = row.find_all(lambda t: t.name in ['td', 'th'] or t.get('role') in ['cell', 'columnheader', 'gridcell'], recursive=True)
                    
                    if cells:
                        row_cells = [c.get_text(separator=' ').strip() for c in cells]
                        table_data.append(row_cells)
                        max_cols = max(max_cols, len(row_cells))
                
                for i, row_cells in enumerate(table_data):
                    # Pad cells
                    padded = row_cells + [""] * (max_cols - len(row_cells))
                    text_lines.append("| " + " | ".join(padded) + " |")
                    # Simplified header detection: first row if it has 'th' or just first row overall
                    if i == 0:
                        text_lines.append("| " + " | ".join(["---"] * max_cols) + " |")
                text_lines.append('')

            else:
                # For other elements (div, section, or unknown), recurse
                for child in elem.children:
                    if hasattr(child, 'name') and child.name:
                        process_element(child)
                    else:
                        # Text node
                        text = str(child).strip()
                        if text:
                             # Check if we should merge with previous line?
                             # In a block container, text nodes often imply inline content too.
                             if text_lines and not text_lines[-1].endswith('\n') and elem.name in ['div', 'li', 'td', 'th', 'p']:
                                 text_lines[-1] += " " + text
                             else:
                                 text_lines.append(text)

        process_element(element)

        # Join and clean up
        result = '\n'.join(text_lines)

        # Remove excessive blank lines
        result = re.sub(r'\n{3,}', '\n\n', result)

        return result.strip()


    async def download_with_selenium(self, urls, progress_callback=None):
        """Download content using Selenium (for SPAs)"""
        if not webdriver:
            self.logger.error("Selenium not installed")
            return []

        self.logger.info(f"🕷️ Starting Selenium scraper for {len(urls)} pages...")
        pages = []
        
        # Setup driver
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        
        driver = webdriver.Chrome(options=options)
        
        try:
            for i, url in enumerate(urls):
                try:
                    if self.verbose:
                        self.logger.info(f"📄 Scraping [{i+1}/{len(urls)}] {url}")
                    
                    driver.get(url)
                    
                    if progress_callback:
                        progress_callback(i + 1, len(urls), f"Scraping {i+1}/{len(urls)}")
                    
                    # Wait for content to load
                    try:
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "main, article, .content"))
                        )
                    except:
                        # Continue even if timeout, might be loaded already
                        pass

                    
                    # Small sleep for JS to finish
                    await asyncio.sleep(2.0)
                    
                    html = driver.page_source
                    content, parsed_title = self._extract_main_content(html)
                    
                    if content:
                        pages.append({
                            'title': parsed_title if parsed_title else driver.title,
                            'url': url,
                            'content': content,
                            'source': 'selenium-spa',
                            'html': html
                        })
                    else:
                        self.logger.warning(f"⚠️ Empty content for {url}")

                except Exception as e:
                    self.logger.error(f"Error scraping {url}: {e}")
                    
        finally:
            driver.quit()
            
        return pages
