"""
Content Consolidator - Combines pages into a single markdown document
"""

import re
from datetime import datetime
from pathlib import Path
from utils.logger import get_logger

class ContentConsolidator:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.logger = get_logger()

    async def consolidate_pages(self, pages, base_url, section_path=None, hierarchy_map=None):
        """Consolidate multiple page dicts into a single markdown file"""
        if not pages:
            return None

        # Sort pages
        self.hierarchy_map = hierarchy_map or {}
        sorted_pages = self._sort_pages(pages)

        # Generate document
        content_parts = []

        # Add Header
        header = self._generate_header(base_url, section_path, len(sorted_pages))
        content_parts.append(header)
        last_section = None
        seen_content_hashes = set()
        
        import hashlib
        
        for i, page in enumerate(sorted_pages, 1):
            content = page.get('content', '').strip()
            if not content:
                continue
                
            # Deduplication: check content hash
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
            if content_hash in seen_content_hashes:
                self.logger.debug(f"Skipping duplicate content for page: {page.get('title')}")
                continue
            seen_content_hashes.add(content_hash)

            # Check for generic section break
            url = page.get('url', '')
            section_title = None
            if self.hierarchy_map:
                info = self.hierarchy_map.get(url)
                if not info and url.endswith('.md'):
                    info = self.hierarchy_map.get(url[:-3])
                
                if info and info.get('section'):
                    section_title = info['section']
            
            # Inject section header if changed
            if section_title and section_title != last_section:
                content_parts.append(f"\n## {section_title}\n")
                last_section = section_title
            
            page_content = self._process_page_content(page, i)
            if page_content:
                content_parts.append(page_content)
                content_parts.append("\n---\n")

        # Combine and clean up
        final_content = "\n".join(content_parts)
        final_content = self._post_process_content(final_content)

        return final_content

    def _generate_header(self, base_url, section_path, page_count):
        """Generate document header"""
        from urllib.parse import urlparse

        domain = urlparse(base_url).netloc
        title = domain.replace('.gitbook.io', '').replace('.com', '').title()

        if section_path:
            title += f" - {section_path.replace('/', ' / ').title()}"

        header = f"""# {title}

*Downloaded with GitBook Multi-Strategy Downloader v4.0*

**Source:** {base_url}  
**Pages:** {page_count}  
**Downloaded:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}  
"""

        if section_path:
            header += f"**Section:** {section_path}  \n"

        header += "\n---\n"

        return header

    def _sort_pages(self, pages):
        """Sort pages in logical reading order based on hierarchy or heuristics"""
        
        def sort_key(page):
            url = page.get('url', '')
            title = page['title'].lower()
            
            # Check hierarchy first
            if self.hierarchy_map:
                # Need to match URL loosely (ignore protocol/www) to be robust
                # But hierarchy_map keys are cleaned absolute URLs
                # Let's try exact match first
                info = self.hierarchy_map.get(url) 
                
                # If content URL might be .md but hierarchy has clean URL
                if not info and url.endswith('.md'):
                     clean_u = url[:-3] # remove .md
                     info = self.hierarchy_map.get(clean_u)
                     
                if info:
                    # Primary sort: Order index from sidebar
                    return (info['order'], 0)
                else:
                    # Put unmapped pages at the end
                    return (999999, 0)
            
            # Fallback to heuristic sort
            score = 0
            if any(word in title for word in ['readme', 'introduction', 'intro', 'start', 'index']):
                score += 1000
            if any(word in title for word in ['getting started', 'quick start', 'overview']):
                score += 900
            
            import re
            numeric_match = re.search(r'(\d+)', title)
            if numeric_match:
                score += 800 - int(numeric_match.group(1))

            score += max(0, 100 - len(title.split()))
            score += max(0, 50 - len(url.split('/')))

            return (0, -score)

        return sorted(pages, key=sort_key)

    def _process_page_content(self, page, page_num):
        """Process individual page content with smart header adjustment"""
        title = page['title']
        # Clean title suffix (e.g. " | Nado Docs")
        if '|' in title:
            title = title.split('|')[0].strip()
            
        content = page.get('content', '')
        url = page.get('url', '')
        
        if not content or not content.strip():
            self.logger.warning(f"Empty content for page: {title}")
            return None

        # Determine target hierarchical level
        # Default behavior:
        # Document Title = H1
        # Root pages (Introduction) = H2  (Level 1 in our logic)
        # Sub pages = H3
        
        target_h2_level = 2 # Default to H2 
        
        if self.hierarchy_map:
            info = self.hierarchy_map.get(url)
            # Try removing extension if not found
            if not info and url.endswith('.md'):
                 info = self.hierarchy_map.get(url[:-3])
            
            if info:
                # Calculate level relative to document root. 
                # Sidebar root items are usually level 1 (inside first UL).
                # We want them to be H2.
                # So: Level 1 -> H2. Offset +1.
                target_h2_level = info['level'] + 1

        # 1. Clean and Adjust Headers
        # We need to demote the headers inside the content so they fit UNDER the new page title.
        # But we also want to remove best-effort duplicate titles (e.g. if content already starts with H1 Title)
        
        processed_content = self._adjust_headers(content, target_level_h2_based=target_h2_level, page_title=title)
        
        # 2. Add the authoritative Section Header
        # We ALWAYS add this to ensure navigation structure is preserved,
        # unless we detect we just essentially "demoted" the exact same title title just below.
        # But to be safe and consistent, we force our structure.
        
        header_prefix = '#' * target_h2_level
        
        # Look at the first few lines of processed content to see if it looks like we already have a suitable header.
        # But _adjust_headers logic might have shifted everything to level+1.
        # We will simply PREPEND our authoritative header.
        
        final_content = f"{header_prefix} {title}\n\n{processed_content}"
        return final_content

    def _adjust_headers(self, content, target_level_h2_based=2, page_title=""):
        """
        Adjust headers in content to fit into the target hierarchy using smart demotion & deduplication.
        Ported from test_header_logic.py
        """
        lines = content.split('\n')
        
        # 1. Analyze content structure
        min_header_level = 99
        first_header_index = -1
        first_header_text = ""
        
        import re
        for i, line in enumerate(lines):
            match = re.match(r'^(#+)\s+(.*)', line)
            if match:
                level = len(match.group(1))
                min_header_level = min(min_header_level, level)
                if first_header_index == -1:
                    first_header_index = i
                    first_header_text = match.group(2).strip()
        
        if min_header_level == 99:
            # No headers, just return text
            return content

        # 2. Check deduplication for the FIRST header only
        # If the first header found matches the page_title we are about to insert, mark it for removal
        is_dupe = False
        if first_header_index != -1 and page_title:
            clean_text = re.sub(r'[^\w\s]', '', first_header_text.lower())
            clean_title = re.sub(r'[^\w\s]', '', page_title.lower())
            # Expanded fuzzy match
            if clean_text == clean_title or clean_title in clean_text or clean_text in clean_title:
                is_dupe = True

        # 3. Calculate Shift
        # General Rule: We want the top-level content of this page to sit UNDER the new Page Title.
        # New Page Title Level = target_level_h2_based
        # So Logical Content Start Level = target_level_h2_based + 1
        
        # BUT, if the content's top header WAS the title (Level 1) and we recognized it as a dupe, 
        # it logically represented the Page Title itself. 
        # If we remove it, the REMAINING headers (which were Level 2) should now map to (Target Level + 1).
        # Existing Level 2 -> Target Level + 1
        # Shift = (Target Level + 1) - 2
        
        # Let's generalize. 
        # We map `min_header_level` in the file to `desired_base_level`.
        
        desired_base_level = target_level_h2_based + 1
        
        # Special Logic: If the file started with H1, and it was a duplicate we are removing,
        # then the "logical" content actually started at H2 (the subsections). 
        # Those H2 subsections should map to children of our new H2 title -> H3.
        # So H2 -> H3. Shift = 3 - 2 = 1.
        # H1 -> H2. Shift = 2 - 1 = 1.
        # It seems the shift is constant regardless of removal?
        
        # Let's trace:
        # Page Title: "Mission" (Level 2)
        # Content: 
        #   # Mission (H1) -> Remove
        #   ## Goal (H2) -> Should become ### Goal (Level 3)
        # Shift calculation:
        #   Desired for old H2 is Level 3.
        #   Shift = 3 - 2 = 1.
        
        # Case 2: No Dupe
        # Page Title: "Overview" (Level 2)
        # Content:
        #   # Introduction (H1) -> Keep. Should become ### Introduction (Level 3) ?? 
        #   Actually if it's H1, maybe it should be H3 (Child of Overview).
        #   Desired for H1 is Level 3.
        #   Shift = 3 - 1 = 2.
        
        # Wait, if content has H1 that is NOT a dupe, it's a major section. 
        # But we are forcing a parent H2. So yes, it becomes H3.
        # So Desired Base Level for `min_header_level` is always `target_level_h2_based + 1`
        
        shift = desired_base_level - min_header_level
        
        # 4. Process lines
        processed_lines = []
        header_count = 0
        for i, line in enumerate(lines):
            match = re.match(r'^(#+)\s+(.*)', line)
            if match:
                level = len(match.group(1))
                text = match.group(2).strip()
                header_count += 1
                
                # Deduplication removal (only remove the very first header if it matches)
                if header_count == 1 and is_dupe:
                    continue
                
                new_level = max(1, level + shift)
                processed_lines.append(f"{'#' * new_level} {text}")
            else:
                processed_lines.append(line)
        
        result_text = '\n'.join(processed_lines)
        return self._clean_whitespace(result_text)

    def _clean_whitespace(self, content):
        content = re.sub(r'\n{4,}', '\n\n\n', content)
        return content.strip()

    def _post_process_content(self, content):
        """Final post-processing of the complete document"""
        content = re.sub(r'\n{4,}', '\n\n\n', content)
        content = content.rstrip() + '\n'
        return content

