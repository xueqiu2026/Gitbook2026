"""
GitHub Strategy - Clone source repository when available
"""

import asyncio
import aiohttp
import git
import shutil
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from utils.logger import get_logger

class GitHubStrategy:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.logger = get_logger()

    async def extract_pages(self, url, section_path=None):
        """Extract pages by cloning GitHub repository"""
        try:
            # Step 1: Detect GitHub repository
            repo_url = await self._detect_github_repo(url)
            if not repo_url:
                return None

            # Step 2: Clone repository
            repo_dir = Path('temp_repo')
            await self._clone_repo(repo_url, repo_dir)

            # Step 3: Find markdown files
            pages = await self._extract_markdown_files(repo_dir, section_path)

            return pages

        except Exception as e:
            self.logger.debug(f"GitHub strategy error: {e}")
            return None

    async def _detect_github_repo(self, url):
        """Detect GitHub repository from GitBook page"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(30)) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return None

                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Look for GitHub links
                    github_selectors = [
                        'a[href*="github.com"]',
                        'a[aria-label*="Edit"]',
                        'a[title*="GitHub"]'
                    ]

                    for selector in github_selectors:
                        links = soup.select(selector)
                        for link in links:
                            href = link.get('href', '')
                            if 'github.com' in href and '/blob/' in href:
                                # Extract repo URL from blob link
                                parts = href.split('/blob/')
                                if len(parts) >= 2:
                                    repo_url = parts[0] + '.git'
                                    self.logger.debug(f"Found repo: {repo_url}")
                                    return repo_url

                    return None

        except Exception as e:
            self.logger.debug(f"GitHub detection error: {e}")
            return None

    async def _clone_repo(self, repo_url, repo_dir):
        """Clone GitHub repository"""
        if repo_dir.exists():
            shutil.rmtree(repo_dir)

        try:
            git.Repo.clone_from(repo_url, repo_dir, depth=1, branch='main')
        except:
            try:
                git.Repo.clone_from(repo_url, repo_dir, depth=1, branch='master')
            except Exception as e:
                raise Exception(f"Failed to clone {repo_url}: {e}")

    async def _extract_markdown_files(self, repo_dir, section_path=None):
        """Extract markdown files from repository"""
        pages = []

        # Determine search directory
        search_dir = repo_dir
        if section_path:
            search_dir = repo_dir / section_path
            if not search_dir.exists():
                self.logger.warning(f"Section path not found: {section_path}")
                return []

        # Find all markdown files
        md_files = list(search_dir.rglob('*.md'))

        for md_file in md_files:
            try:
                content = md_file.read_text(encoding='utf-8')
                relative_path = md_file.relative_to(repo_dir)

                pages.append({
                    'title': self._extract_title(content) or md_file.stem.replace('-', ' ').replace('_', ' ').title(),
                    'url': str(md_file),
                    'content': content,
                    'source': 'github',
                    'path': str(relative_path)
                })

            except Exception as e:
                self.logger.warning(f"Error reading {md_file}: {e}")

        return pages

    def _extract_title(self, content):
        """Extract title from markdown content"""
        lines = content.split('\n')
        for line in lines[:10]:  # Check first 10 lines
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()
        return None
