
import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class SmartProbe:
    """
    Smart Native Probe Engine
    Attempts to download original Markdown sources directly, bypassing HTML parsing.
    """
    
    def __init__(self, max_concurrent: int = 20, delay: float = 0.1):
        self.max_concurrent = max_concurrent
        self.delay = delay
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.session = None

    async def probe_and_download(self, urls: List[str], progress_callback=None) -> Dict[str, str]:
        """
        Probes a list of URLs for their .md counterparts.
        Returns a dictionary of {url: markdown_content} for successful hits.
        """
        logger.info(f"🕵️ [SmartProbe] Probing {len(urls)} pages for native Markdown...")
        if progress_callback:
            progress_callback(0, len(urls), "Starting Smart Probe...")
        
        results = {}
        timeout = aiohttp.ClientTimeout(total=10) # Fast timeout for probing
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            self.session = session
            
            tasks = []
            completed_count = 0
            
            async def wrapped_probe(u):
                nonlocal completed_count
                res = await self._probe_single(u)
                completed_count += 1
                if progress_callback:
                    # Report periodically to avoid flooding
                    if completed_count % 5 == 0 or completed_count == len(urls):
                        progress_callback(completed_count, len(urls), f"Smart Probing: {completed_count}/{len(urls)}")
                return res

            for url in urls:
                tasks.append(wrapped_probe(url))
                
            # Run in batches/concurrently
            probed_results = await asyncio.gather(*tasks)
            
            for url, content in probed_results:
                if content:
                    results[url] = content
                    
        hit_rate = (len(results) / len(urls)) * 100 if urls else 0
        logger.info(f"🎯 [SmartProbe] Success: {len(results)}/{len(urls)} ({hit_rate:.1f}%) native files found.")
        return results

    async def _probe_single(self, url: str) ->(str, Optional[str]):
        """
        Try to fetch the .md version of a single URL.
        Returns (original_url, content_or_None).
        """
        async with self.semaphore:
            # Construct candidate URLs
            # 1. Direct append .md (common in some static hosts)
            # 2. GitBook often serves content via API, but raw .md might be accessible if statically exported.
            # The competitor simply appended .md. Let's try that first.
            
            # Clean URL first
            parsed = urlparse(url)
            clean_url = url.split('#')[0].split('?')[0]
            
            # Heuristic: If it already ends in /, maybe add README.md? 
            # Or just .md?
            # Competitor did: f"{link}.md"
            
            candidates = [
                f"{clean_url}.md",
                f"{clean_url}/README.md" if not clean_url.endswith('.md') else None
            ]
            candidates = [c for c in candidates if c]

            for candidate in candidates:
                try:
                    await asyncio.sleep(self.delay)
                    async with self.session.get(candidate) as response:
                        if response.status == 200:
                            # Verify if it looks like markdown
                            content = await response.text()
                            # Basic validation: Shouldn't start with <!DOCTYPE html>
                            if content.strip().lower().startswith('<!doctype html'):
                                continue
                                
                            return url, content
                        
                        elif response.status == 429:
                            # Simple backoff handled by retry (omitted here for speed, just fail this probe)
                            pass
                            
                except Exception as e:
                    pass
            
            return url, None
