"""
Asset Downloader - Downloads and manages images and other assets
"""

import asyncio
import aiohttp
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from utils.logger import get_logger

class AssetDownloader:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.logger = get_logger()

        self.asset_extensions = {
            '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico',
            '.pdf', '.zip', '.tar', '.gz'
        }

    async def download_assets(self, pages, assets_dir):
        """Download assets referenced in pages"""
        assets_dir = Path(assets_dir)
        assets_dir.mkdir(parents=True, exist_ok=True)

        # Find all asset URLs
        asset_urls = set()

        for page in pages:
            content = page.get('content', '') + page.get('html', '')
            urls = self._extract_asset_urls(content, page.get('url', ''))
            asset_urls.update(urls)

        if not asset_urls:
            return 0

        self.logger.info(f"Found {len(asset_urls)} assets to download")

        # Download assets
        downloaded_count = 0
        semaphore = asyncio.Semaphore(10)  # Limit concurrent downloads

        async def download_asset(url):
            nonlocal downloaded_count

            async with semaphore:
                try:
                    await asyncio.sleep(0.1)  # Rate limiting

                    # Determine filename
                    parsed = urlparse(url)
                    filename = Path(parsed.path).name
                    if not filename or '.' not in filename:
                        filename = f"asset_{hash(url) % 10000}"

                    asset_path = assets_dir / filename

                    # Skip if already exists
                    if asset_path.exists():
                        return

                    # Download
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(30)) as session:
                        async with session.get(url) as response:
                            if response.status == 200:
                                content = await response.read()

                                # Write file
                                with open(asset_path, 'wb') as f:
                                    f.write(content)

                                downloaded_count += 1

                                if self.verbose:
                                    self.logger.debug(f"Downloaded: {filename}")

                except Exception as e:
                    self.logger.debug(f"Failed to download {url}: {e}")

        # Download all assets
        tasks = [download_asset(url) for url in asset_urls]
        await asyncio.gather(*tasks, return_exceptions=True)

        return downloaded_count

    def _extract_asset_urls(self, content, base_url):
        """Extract asset URLs from content"""
        urls = set()

        # Image patterns
        img_patterns = [
            r'!\[([^\]]*)\]\(([^)]+)\)',  # Markdown images
            r'<img[^>]*src=["\']([^"\']+)["\'][^>]*>',  # HTML images
            r'src\s*=\s*["\']([^"\']+)["\']',  # Generic src attributes
        ]

        # Link patterns for downloadable assets
        link_patterns = [
            r'\[([^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*)\]\(([^)]+)\)',  # Markdown links
            r'href\s*=\s*(?:["\']([^"\']*)["\']|([^\s>]+))',  # HTML links
        ]

        all_patterns = img_patterns + link_patterns

        for pattern in all_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                url = match.strip()

                # Skip empty, anchor, or data URLs
                if not url or url.startswith(('#', 'data:', 'javascript:')):
                    continue

                # Convert relative URLs to absolute
                if base_url and not url.startswith(('http://', 'https://')):
                    url = urljoin(base_url, url)

                # Check if it's an asset we want to download
                parsed = urlparse(url)
                path_lower = parsed.path.lower()

                if any(path_lower.endswith(ext) for ext in self.asset_extensions):
                    urls.add(url)

        return urls

    def update_asset_references(self, content, assets_dir):
        """Update asset references in content to point to local files"""
        # This is a basic implementation
        # In a full version, you'd want more sophisticated path replacement

        # Replace image references
        def replace_image(match):
            original_url = match.group(1)
            parsed = urlparse(original_url)
            filename = Path(parsed.path).name

            if filename and any(filename.lower().endswith(ext) for ext in self.asset_extensions):
                return f"![{match.group(0).split(']')[0][2:]}]({assets_dir}/{filename})"

            return match.group(0)

        # Replace markdown images
        content = re.sub(r'!\[(.*?)\]\((.*?)\)', replace_image, content)

        return content
