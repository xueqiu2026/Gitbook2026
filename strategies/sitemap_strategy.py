"""
Sitemap Strategy - Download pages listed in sitemap.xml
"""

import asyncio
import aiohttp
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from utils.logger import get_logger

class SitemapStrategy:
    def __init__(self, max_concurrent=15, delay=0.1, timeout=30, verbose=False):
        self.max_concurrent = max_concurrent
        self.delay = delay
        self.timeout = timeout
        self.verbose = verbose
        self.logger = get_logger()

    async def extract_pages(self, url, section_path=None):
        """Extract pages from sitemap.xml"""
        try:
            # Find sitemap URLs
            sitemap_urls = await self._find_sitemaps(url)
            if not sitemap_urls:
                return None

            # Extract page URLs from sitemaps
            page_urls = []
            for sitemap_url in sitemap_urls:
                urls = await self._parse_sitemap(sitemap_url)
                page_urls.extend(urls)

            if not page_urls:
                return None

            # Filter by section if specified
            if section_path:
                page_urls = [u for u in page_urls if section_path in u]

            # Download pages
            pages = await self._download_pages(page_urls)

            return pages

        except Exception as e:
            self.logger.debug(f"Sitemap strategy error: {e}")
            return None

    async def _find_sitemaps(self, base_url):
        """Find sitemap.xml URLs"""
        sitemap_paths = [
            '/sitemap.xml',
            '/sitemap-pages.xml', 
            '/sitemap_index.xml'
        ]

        sitemaps = []
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(self.timeout)) as session:
            for path in sitemap_paths:
                sitemap_url = urljoin(base_url, path)
                try:
                    async with session.get(sitemap_url) as response:
                        if response.status == 200:
                            content = await response.text()
                            if '<urlset' in content or '<sitemapindex' in content:
                                sitemaps.append(sitemap_url)
                                self.logger.debug(f"Found sitemap: {sitemap_url}")
                except:
                    continue

        return sitemaps

    async def _parse_sitemap(self, sitemap_url):
        """Parse sitemap XML and extract page URLs"""
        urls = []

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(self.timeout)) as session:
                async with session.get(sitemap_url) as response:
                    if response.status != 200:
                        return []

                    content = await response.text()
                    soup = BeautifulSoup(content, 'xml')

                    # Handle sitemap index
                    sitemap_tags = soup.find_all('sitemap')
                    if sitemap_tags:
                        # This is a sitemap index, recurse
                        for sitemap_tag in sitemap_tags:
                            loc = sitemap_tag.find('loc')
                            if loc:
                                child_urls = await self._parse_sitemap(loc.text)
                                urls.extend(child_urls)
                    else:
                        # Regular sitemap with URLs
                        url_tags = soup.find_all('url')
                        for url_tag in url_tags:
                            loc = url_tag.find('loc')
                            if loc:
                                urls.append(loc.text)

        except Exception as e:
            self.logger.debug(f"Error parsing sitemap {sitemap_url}: {e}")

        return urls

    async def _download_pages(self, urls):
        """Download content from page URLs"""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        pages = []

        async def download_page(url):
            async with semaphore:
                await asyncio.sleep(self.delay)

                try:
                    # Construct .md URL instead of HTML
                    md_url = url.rstrip('/') + '.md'
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(self.timeout)) as session:
                        async with session.get(md_url) as response:
                            if response.status == 200:
                                md = await response.text()
                                title = self._extract_title(md)
                                if not title:
                                    # Try to guess from URL if content title missing
                                    path = urlparse(url).path.strip('/')
                                    title = path.split('/')[-1].replace('-', ' ').title() if path else "Introduction"
                                
                                pages.append({
                                    'title': title,
                                    'url': md_url,
                                    'content': md,
                                    'source': 'sitemap-md'
                                })
                                return
                        # Fallback to HTML if Markdown not available
                        async with session.get(url) as response:
                            if response.status == 200:
                                html = await response.text()
                                content = self._extract_content(html)
                                if content:
                                    title = self._extract_title(html)
                                    if not title:
                                        path = urlparse(url).path.strip('/')
                                        title = path.split('/')[-1].replace('-', ' ').title() if path else "Introduction"
                                    
                                    pages.append({
                                        'title': title,
                                        'url': url,
                                        'content': content,
                                        'source': 'sitemap-html'
                                    })
                except Exception as e:
                    self.logger.debug(f"Error downloading {url}: {e}")

        # Download all pages concurrently
        tasks = [download_page(url) for url in urls]
        await asyncio.gather(*tasks, return_exceptions=True)

        return pages

    def _extract_content(self, html):
        """Extract main content from HTML"""
        soup = BeautifulSoup(html, 'html.parser')

        # Remove unwanted elements
        for element in soup.select('nav, header, footer, .sidebar, .navigation'):
            element.decompose()

        # Find main content
        content_selectors = [
            '[data-testid="page-content"]',
            'main',
            '.content',
            'article',
            '.page-content'
        ]

        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                return content_elem.get_text().strip()

        # Fallback - get body text
        body = soup.find('body')
        return body.get_text().strip() if body else html

    def _extract_title(self, html):
        """Extract page title from HTML or Markdown"""
        if not html:
            return "Untitled Page"
            
        # Try finding # Title in Markdown
        md_match = re.search(r'^#\s+(.*)', html, re.MULTILINE)
        if md_match:
            return md_match.group(1).strip()
            
        soup = BeautifulSoup(html, 'html.parser')

        # Try various title sources
        title_selectors = [
            'h1',
            '[data-testid="page-title"]',
            'title',
            '.page-title',
            '.post-title'
        ]

        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text().strip()
                if title and len(title) < 200:
                    # Clean common suffixes
                    if ' | ' in title: title = title.split(' | ')[0]
                    elif ' - ' in title: title = title.split(' - ')[0]
                    return title.strip()

        return None # Return None so caller can try fallback via URL
