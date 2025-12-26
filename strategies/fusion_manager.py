
import asyncio
import logging
from typing import List, Dict, Optional, Set
from urllib.parse import urlparse

from strategies.hierarchy_manager import HierarchyManager
from strategies.universal_manager import UniversalManager

logger = logging.getLogger(__name__)

class FusionManager:
    """
    Fusion Strategy / Hybrid Mode
    Merges all discovery sources into a single consistent hierarchy.
    1. Sitemap (All URLs)
    2. Sidebar (Accurate Titles & Order)
    3. Heuristic (Deep link fallback)
    """

    def __init__(self, use_selenium: bool = True):
        self.use_selenium = use_selenium
        self.hierarchy_manager = HierarchyManager(use_selenium=use_selenium)
        self.universal_manager = UniversalManager(use_selenium=use_selenium)
        self.diagnostics = {
            "sources": {},
            "merged_count": 0,
            "fusion_method": "hybrid"
        }

    async def build_hierarchy(self, base_url: str) -> List[Dict]:
        """
        Parallelizes discovery and merges results.
        """
        logger.info(f"🚀 [Fusion] Starting Ultimate Fusion discovery for {base_url}")
        
        # Start parallel discovery
        tasks = [
            self._get_sitemap_urls(base_url),
            self._get_sidebar_map(base_url),
            self._get_heuristic_nodes(base_url)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        sitemap_urls = results[0] if not isinstance(results[0], Exception) else set()
        sidebar_map = results[1] if not isinstance(results[1], Exception) else {}
        heuristic_nodes = results[2] if not isinstance(results[2], Exception) else []

        logger.info(f"📊 [Fusion] Discovery results: Sitemap={len(sitemap_urls)}, Sidebar={len(sidebar_map)}, Heuristic={len(heuristic_nodes)}")

        # MERGE LOGIC
        # We use URL as the key.
        merged_map = {}

        # 1. Process Sidebar results (Highest priority for titles and order)
        for url, info in sidebar_map.items():
            merged_map[self._canonical_url(url)] = {
                'url': url,
                'title': info.get('title', 'Untitled'),
                'depth': info.get('level', 0),
                'order': info.get('order', 0),
                'source': 'sidebar'
            }

        # 2. Process Sitemap URLs (Fill missing pages)
        for url in sitemap_urls:
            c_url = self._canonical_url(url)
            if c_url not in merged_map:
                # Estimate depth from path
                depth = self._estimate_depth(url, base_url)
                merged_map[c_url] = {
                    'url': url,
                    'title': self._title_from_url(url),
                    'depth': depth,
                    'order': 9999 + depth, # Put at end but preserve relative depth order
                    'source': 'sitemap'
                }

        # 3. Process Heuristic nodes (Discovery backup)
        for node in heuristic_nodes:
            c_url = self._canonical_url(node['url'])
            if c_url not in merged_map:
                merged_map[c_url] = {
                    'url': node['url'],
                    'title': node['title'],
                    'depth': node['depth'],
                    'order': 20000 + node['depth'],
                    'source': 'heuristic'
                }

        # Convert back to sorted list
        final_nodes = sorted(merged_map.values(), key=lambda x: (x['order'], x['url']))
        
        logger.info(f"✅ [Fusion] Successfully merged {len(final_nodes)} unique pages.")
        return final_nodes

    async def _get_sitemap_urls(self, base_url: str) -> Set[str]:
        return await self.universal_manager._fetch_all_urls_from_sitemap(f"{base_url}/sitemap.xml")

    async def _get_sidebar_map(self, base_url: str) -> Dict:
        return self.hierarchy_manager.build_hierarchy(base_url)

    async def _get_heuristic_nodes(self, base_url: str) -> List[Dict]:
        # UniversalManager.build_hierarchy(base_url) actually does sitemap + heuristic
        # We only want its heuristic discovery if sitemap fails or we just want its scanner.
        # Let's call its internal _heuristic_scan directly.
        nodes = await self.universal_manager._heuristic_scan(base_url)
        return [self.universal_manager._node_to_dict(n) for n in nodes]

    def _canonical_url(self, url: str) -> str:
        """Strip protocol and trailing slashes for key matching"""
        url = url.split('#')[0].split('?')[0].rstrip('/')
        if '://' in url:
            url = url.split('://', 1)[1]
        if url.startswith('www.'):
            url = url[4:]
        return url.lower()

    def _estimate_depth(self, url: str, base_url: str) -> int:
        base_path = urlparse(base_url).path.strip('/')
        url_path = urlparse(url).path.strip('/')
        
        if not url_path or url_path == base_path:
            return 0
            
        # Remove common prefix
        if url_path.startswith(base_path):
            url_path = url_path[len(base_path):].strip('/')
            
        return len(url_path.split('/'))

    def _title_from_url(self, url: str) -> str:
        path = urlparse(url).path.strip('/')
        if not path:
            return "Introduction"
        slug = path.split('/')[-1]
        return slug.replace('-', ' ').replace('_', ' ').title()
