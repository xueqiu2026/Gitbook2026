
import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin
import aiohttp
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List, Dict, Optional, Set
import json
import os

logger = logging.getLogger(__name__)

@dataclass
class UniversalNode:
    url: str
    title: str
    depth: int
    parent: Optional[str] = None

class UniversalManager:
    """
    Universal Parser for GitBook.
    Strategy:
    1. Sitemap XML (Gold standard, 100% accurate)
    2. Heuristic DOM Scan (Fallback, robust but messy)
    """

    def __init__(self, use_selenium=False):
        self.use_selenium = use_selenium
        self.diagnostics = {
            "method": "unknown",
            "sitemap_found": False,
            "total_links": 0,
            "filtered_links": 0,
            "domains_seen": [],
            "heuristic_scan_details": {}
        }

    async def _get_driver(self):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        # Suppress logging
        options.add_argument("--log-level=3")
        
        try:
            driver = webdriver.Chrome(options=options)
            return driver
        except Exception as e:
            logger.error(f"Failed to create Chrome driver: {e}")
            return None

    async def build_hierarchy(self, base_url: str) -> List[Dict]:
        """
        Main entry point. Returns a list of dicts:
        [{'url': '...', 'title': '...', 'depth': 0, 'parent': None}, ...]
        """
        base_url = base_url.rstrip('/')
        
        # 1. Try Sitemap
        logger.info(f"🔍 [Universal] Phase 1: Checking Sitemap for {base_url}")
        urls = await self._fetch_all_urls_from_sitemap(f"{base_url}/sitemap.xml")
        
        if urls:
            nodes = self._urls_to_nodes(list(urls), base_url)
            logger.info(f"✅ [Universal] Sitemap found {len(nodes)} pages.")
            self.diagnostics["method"] = "sitemap"
            self.diagnostics["total_links"] = len(nodes)
            return [self._node_to_dict(n) for n in nodes]

        # 2. Heuristic DOM Scan
        logger.warning(f"⚠️ [Universal] Sitemap failed. Phase 2: Heuristic DOM Scan.")
        self.diagnostics["method"] = "heuristic_dom"
        nodes = await self._heuristic_scan(base_url)
        
        if nodes:
            logger.info(f"✅ [Universal] Heuristic scan found {len(nodes)} pages.")
            self.diagnostics["total_links"] = len(nodes)
            return [self._node_to_dict(n) for n in nodes]
            
        logger.error("❌ [Universal] All strategies failed.")
        return []

    async def _fetch_all_urls_from_sitemap(self, sitemap_url: str, seen_sitemaps: Set[str] = None) -> Set[str]:
        """
        Recursively fetch all URLs from a sitemap or sitemap index.
        """
        if seen_sitemaps is None:
            seen_sitemaps = set()
        
        if sitemap_url in seen_sitemaps:
            return set()
        
        seen_sitemaps.add(sitemap_url)
        all_urls = set()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(sitemap_url, timeout=15) as resp:
                    if resp.status != 200:
                        return set()
                    content = await resp.text()

            # Remove namespaces
            content = re.sub(r'xmlns="[^"]+"', '', content, count=1)
            try:
                root = ET.fromstring(content)
            except ET.ParseError:
                return set()

            # Case A: Sitemap Index
            if root.tag == 'sitemapindex':
                locs = [loc.text.strip() for loc in root.findall(".//sitemap/loc") if loc.text]
                tasks = [self._fetch_all_urls_from_sitemap(loc, seen_sitemaps) for loc in locs]
                results = await asyncio.gather(*tasks)
                for res in results:
                    all_urls.update(res)
            
            # Case B: Standard Sitemap
            else:
                for loc in root.findall(".//url/loc"):
                    if loc.text:
                        all_urls.add(loc.text.strip())
                        
            return all_urls
                
        except Exception as e:
            logger.error(f"Sitemap error for {sitemap_url}: {e}")
            return set()

    async def _heuristic_scan(self, base_url: str) -> List[UniversalNode]:
        """
        Scan the main page for ALL internal links.
        This uses Selenium if available (to render JS-heavy sidebars), otherwise aiohttp.
        """
        content = ""
        current_url = base_url

        # Use Selenium if available as it renders the sidebar
        if self.use_selenium:
            logger.info("Using Selenium for Heuristic Scan...")
            driver = await self._get_driver()
            if driver:
                try:
                    driver.get(base_url)
                    # Wait a bit for sidebar to populate
                    await asyncio.sleep(5) 
                    
                    # Try to expand all details/summary if they exist (common in docs)
                    try:
                        driver.execute_script("""
                            document.querySelectorAll('details').forEach((el) => el.open = true);
                            document.querySelectorAll('[aria-expanded="false"]').forEach((el) => el.click());
                        """)
                        await asyncio.sleep(2)
                    except:
                        pass
                    
                    content = driver.page_source
                    current_url = driver.current_url # Might have redirected
                except Exception as e:
                    logger.error(f"Selenium scan failed: {e}")
                    # Fallthrough to aiohttp if selenium fails?
                finally:
                    driver.quit()
        
        if not content:
            # Fallback to simple request (likely to miss JS content)
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url) as resp:
                    content = await resp.text()
                    current_url = str(resp.url)

        soup = BeautifulSoup(content, 'html.parser')
        
        # Extract ALL links
        raw_links = set()
        base_domain = urlparse(base_url).netloc
        
        # Broad filter: Find strict domain matches
        all_anchors = soup.find_all('a', href=True)
        self.diagnostics['heuristic_scan_details']['total_anchors'] = len(all_anchors)
        
        for a in all_anchors:
            href = a['href']
            full_url = urljoin(current_url, href)
            parsed = urlparse(full_url)
            
            # Filter logic
            if parsed.netloc != base_domain:
                continue # External link
            
            if any(x in parsed.path.lower() for x in ['/login', '/signup', '/signin', '/register', 'twitter.com', 'discord.gg']):
                continue
                
            # Remove fragments for deduplication, unless it's a single page app where fragments matter? 
            # GitBook typically uses paths. Let's strip fragments to be safe, standard GitBook pages are paths.
            clean_url = full_url.split('#')[0]
            clean_url = clean_url.split('?')[0] # Remove query params
            
            if clean_url.endswith('/'):
                clean_url = clean_url[:-1]
                
            raw_links.add(clean_url)

        self.diagnostics["filtered_links"] = len(raw_links)
        return self._urls_to_nodes(list(raw_links), base_url)

    def _urls_to_nodes(self, urls: List[str], base_url: str) -> List[UniversalNode]:
        """
        Convert flat list of URLs to hierarchical nodes based on path depth.
        """
        # Sort by length implies hierarchy (shorter is usually parent)
        urls = sorted(list(set(urls)))
        
        nodes = []
        base_path_depth = len(urlparse(base_url).path.strip('/').split('/'))
        if urlparse(base_url).path == '/' or not urlparse(base_url).path:
            base_path_depth = 0

        for url in urls:
            path = urlparse(url).path.strip('/')
            parts = path.split('/')
            depth = len(parts) - base_path_depth
            
            # Improved title extraction: 
            # - If slug is empty (root), call it "Home"
            # - Use slug words, clean them
            slug = parts[-1] if parts else ""
            if not slug:
                title = "Introduction"
            else:
                title = slug.replace('-', ' ').replace('_', ' ').title()
                # If slug is just random characters or too short, maybe it's not a good title
                # But for now this is better than "Untitled"
            
            # Try to guess parent
            
            # Try to guess parent
            parent = None
            # Logic: Parent is likely the URL without the last segment
            # This is heuristic and might be wrong for some routing, but ok for GitBook
            potential_parent_parts = parts[:-1]
            if potential_parent_parts:
                # Reconstruct parent URL to check if it exists in our list?
                # For now, just leave parent None and let flat list work. 
                # The viewer can handle flat lists.
                pass

            nodes.append(UniversalNode(
                url=url,
                title=title,
                depth=max(0, depth)
            ))
            
        return nodes

    def _node_to_dict(self, node: UniversalNode) -> Dict:
        return {
            'url': node.url,
            'title': node.title,
            'depth': node.depth,
            'parent': node.parent
        }

    def save_diagnostics(self, path="universal_diagnostics.json"):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.diagnostics, f, indent=2)
            logger.info(f"💾 Diagnostics saved to {path}")
        except Exception as e:
            logger.error(f"Failed to save diagnostics: {e}")
