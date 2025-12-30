
from selenium.webdriver.common.by import By
from utils.logger import get_logger
from utils.doc_tree import DocNode
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
from utils.driver_manager import DriverManager

class DirectoryTreeService:
    """
    Dedicated service for building, verifying, and healing the Document Tree.
    Isolates volatile DOM interaction logic from the main application.
    """
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.logger = get_logger()

    async def build(self, base_url):
        """
        Builds the semantic DocNode tree.
        Orchestrates Expansion -> Parsing -> Validation -> Healing.
        """
        driver = DriverManager().get_driver()
        
        # 1. Navigation & Force-Expansion
        self.logger.info(f"🌳 [TreeService] constructing tree for {base_url}")
        driver.get(base_url)
        time.sleep(2) # Hydration wait
        
        sidebar = self._get_sidebar(driver)
        if not sidebar:
            self.logger.error("  ❌ [TreeService] Sidebar not found!")
            return DocNode("Root")
            
        # Force Expand (CSS)
        sidebar = self._expand_sidebar(driver)
        
        # 2. Parse Tree (Visual)
        tree_root = self._parse_to_tree(sidebar, base_url)
        
        return tree_root

    def _get_sidebar(self, driver):
        """Find the main sidebar element using heuristics"""
        try:
            candidates = driver.find_elements(By.CSS_SELECTOR, "nav, aside, div[class*='sidebar'], [data-testid='sidebar']")
            sidebar = None
            max_links = 0
            
            for i, cand in enumerate(candidates):
                try:
                    links = cand.find_elements(By.TAG_NAME, 'a')
                    count = len(links)
                    if count > max_links and count > 3:
                        max_links = count
                        sidebar = cand
                except:
                    continue
            return sidebar
        except Exception as e:
            self.logger.debug(f"Error finding sidebar: {e}")
            return None

    def _expand_sidebar(self, driver):
        """
        Multi-Phase Force-Reveal:
        1. CSS injection for standard GitBook
        2. Click-based expansion for Nado-style chevron toggles
        """
        self.logger.info("  🔓 [TreeService] Executing Multi-Phase Force-Reveal...")
        
        # === PHASE 1: CSS Force-Reveal ===
        force_reveal_script = """
        (function forceExpandTree() {
            const selectors = [
                'div[data-state="closed"]',  // Radix UI / GitBook
                'div[style*="height: 0"]',   // Inline style collapse
                'ul.hidden',                 // Tailwind hidden
                'nav div.overflow-hidden',    // Common wrapper
                '[aria-hidden="true"]'       // Aria hidden
            ];

            const allCollapsed = document.querySelectorAll(selectors.join(','));
            let count = 0;
            allCollapsed.forEach(el => {
                el.style.display = 'block';
                el.style.height = 'auto';
                el.style.maxHeight = 'none';
                el.style.visibility = 'visible';
                el.style.opacity = '1';
                el.style.overflow = 'visible';
                el.setAttribute('data-force-expanded', 'true');
                el.setAttribute('data-state', 'open');
                el.setAttribute('aria-expanded', 'true');
                el.setAttribute('aria-hidden', 'false');
                count++;
            });
            return count;
        })();
        """
        try:
            count = driver.execute_script(force_reveal_script)
            self.logger.info(f"  ⚡ Phase 1 (CSS): Force-revealed {count} elements.")
            time.sleep(0.5)
        except Exception as e:
            self.logger.warning(f"  Phase 1 error: {e}")

        # === PHASE 2: Click-Based Expansion for Nado ===
        # Nado uses <a class="toclink"> with sibling <div> for expandable sections
        click_expand_script = """
        (function clickExpandAll() {
            let clickCount = 0;
            
            // Strategy 1: Click toclink elements that have sibling divs (Nado-specific)
            const toclinks = document.querySelectorAll('a.toclink');
            toclinks.forEach(link => {
                const nextSib = link.nextElementSibling;
                if (nextSib && nextSib.tagName === 'DIV') {
                    // Check if the sibling div is hidden/collapsed
                    const style = window.getComputedStyle(nextSib);
                    if (style.display === 'none' || style.height === '0px' || style.visibility === 'hidden') {
                        try {
                            link.click();
                            clickCount++;
                        } catch(e) {}
                    }
                }
            });
            
            // Strategy 2: Generic aria-expanded toggle
            const toggles = document.querySelectorAll('[aria-expanded="false"], [data-state="closed"]');
            toggles.forEach(el => {
                try {
                    el.click();
                    clickCount++;
                } catch(e) {}
            });
            
            // Strategy 3: SVG chevron icons as fallback
            const chevrons = document.querySelectorAll('svg[class*="icon"]');
            chevrons.forEach(svg => {
                let clickTarget = svg.closest('span') || svg.closest('button') || svg.parentElement;
                if (clickTarget && clickTarget.click) {
                    try {
                        clickTarget.click();
                        clickCount++;
                    } catch(e) {}
                }
            });
            
            return clickCount;
        })();
        """
        
        # Run multiple expansion passes to handle deep nesting
        for pass_num in range(3):
            try:
                click_count = driver.execute_script(click_expand_script)
                if click_count > 0:
                    self.logger.info(f"  🖱️ Phase 2 Pass {pass_num + 1}: Clicked {click_count} expansion toggles.")
                    time.sleep(0.5)
                else:
                    break  # No more elements to expand
            except Exception as e:
                self.logger.debug(f"  Phase 2 Pass {pass_num + 1} error: {e}")
                break
        
        # Final CSS pass to catch any newly revealed elements
        try:
            final_count = driver.execute_script(force_reveal_script)
            if final_count > 0:
                self.logger.info(f"  ⚡ Phase 3 (Final CSS): Revealed {final_count} additional elements.")
        except:
            pass
        
        time.sleep(1.0)

        # Return fresh sidebar from DOM
        return self._get_sidebar(driver)

    def _parse_to_tree(self, root_element, base_url):
        """Parses the sidebar DOM into DocNode tree - Dual Mode Support"""
        html = root_element.get_attribute('outerHTML')
        soup = BeautifulSoup(html, 'html.parser')
        
        
        doc_root = DocNode("Documentation Root", level=0)
        print("!!! I AM RUNNING _parse_to_tree !!!", flush=True)
        # === STRUCTURE DETECTION ===
        # Robust Nado Detection with Fallback
        toclinks = soup.select('a[class*="toclink"]')
        
        if not toclinks or len(toclinks) <= 3:
            # Fallback: Manual class inspection
            all_a = soup.find_all('a')
            manual_toclinks = []
            for a in all_a:
                classes = a.get('class', [])
                # Handle list of strings or single string
                if isinstance(classes, list):
                    if any('toclink' in c for c in classes) or any('group/toclink' in c for c in classes):
                        manual_toclinks.append(a)
                elif isinstance(classes, str):
                    if 'toclink' in classes:
                        manual_toclinks.append(a)
            
            if len(manual_toclinks) > 3:
                self.logger.info(f"  🔍 Detected Nado-style flat structure (Manual Fallback: {len(manual_toclinks)} links). Using Flat Parser.")
                toclinks = manual_toclinks # Use these for consistency if needed, though _parse_flat_structure re-selects
                return self._parse_flat_structure(soup, base_url, doc_root)

        if toclinks and len(toclinks) > 3:
            self.logger.info("  🔍 Detected Nado-style flat structure (toclink). Using Flat Parser.")
            return self._parse_flat_structure(soup, base_url, doc_root)
        
        # Standard: Nested li > ul structure
        self.logger.info("  🔍 Detected standard nested structure. Using Nested Parser.")
        root_ul = soup.find('ul')
        if not root_ul:
            container = soup.find('div', {'data-testid': 'toc-scroll-container'})
            if container: root_ul = container.find('ul')
            
        if not root_ul: return doc_root
        
        def parse_recursive(ul_node, parent_node, current_level):
            list_items = ul_node.find_all('li', recursive=False)
            
            # Context for flat lists: If we find a Type B header, it captures subsequent Type A siblings
            current_section_node = None
            
            for li in list_items:
                title = "Unknown"
                url = None
                
                # Check Direct Link (Type A)
                direct_a = li.find('a', recursive=False)
                if not direct_a:
                     wrapper = li.find('div', recursive=False)
                     if wrapper: direct_a = wrapper.find('a', recursive=False)
                
                node_type = 'B'
                if direct_a:
                    node_type = 'A'
                    title = direct_a.get_text(strip=True)
                    href = direct_a.get('href')
                    if href:
                        url = urljoin(base_url, href).split('#')[0]
                else:
                    # Group Header (Type B)
                    for child in li.find_all('div', recursive=False):
                        if not child.find('a'):
                            title = child.get_text(strip=True)
                            break
                
                # Determine Parent
                # Default: Add to current logical parent
                target_parent = parent_node
                
                if node_type == 'A' and current_section_node:
                    # If we are in a "Section" (Flat List Mode), add to the section node
                    target_parent = current_section_node
                    
                new_node = DocNode(title, level=current_level, url=url)
                target_parent.add_child(new_node)
                
                # Handling Nesting
                nested_ul = li.find('ul')
                
                if node_type == 'B':
                    if nested_ul:
                         # Standard GitBook: Header contains UL. Reset section context because nesting is strict.
                         current_section_node = None 
                    else:
                         # Flat GitBook: Header has NO UL. It acts as a folder for subsequent siblings.
                         current_section_node = new_node
                
                # Recurse
                if nested_ul:
                    # If recursing, children inside UL belong to new_node (Standard)
                    parse_recursive(nested_ul, new_node, current_level + 1)
                    
        parse_recursive(root_ul, doc_root, current_level=1)
        return doc_root

    def _parse_flat_structure(self, soup, base_url, doc_root):
        """
        Parses Nado-style sidebar using nested List traversal.
        Instead of depth calc (brittle), we follow LI -> UL -> LI structure.
        """
        # 1. capture all top-level TOClinks (Roots)
        # Roots are toclinks that do NOT have a parent LI that contains another toclink?
        # Simpler: Roots are toclinks in the "Main" UL?
        # Or: Use the depths just to find Roots (min_depth), but structure for Children.
        
        all_links = soup.select('a[class*="toclink"]')
        if not all_links:
             # Try fallback again just in case
             all_a = soup.find_all('a')
             for a in all_a:
                classes = a.get('class', [])
                if isinstance(classes, list):
                    if any('toclink' in c for c in classes): all_links.append(a)
                elif isinstance(classes, str) and 'toclink' in classes: all_links.append(a)

        if not all_links:
            self.logger.warning("  ⚠️ Flat Parser found no links.")
            return doc_root

        processed_urls = set()
        
        def get_url(link):
            href = link.get('href')
            if href:
               return urljoin(base_url, href).split('#')[0]
            return None

        # Helper to find depth for Root detection only
        link_depths = {l: len(l.find_parents('li')) for l in all_links}
        min_depth = min(link_depths.values()) if link_depths else 0
        
        self.logger.info(f"  🔍 Flat Parser: Found {len(all_links)} links. Root depth: {min_depth}")

        def process_node_from_link(link, parent_node, current_level):
            title = link.get_text(strip=True)
            url = get_url(link)
            
            # De-dupe
            if url and url in processed_urls: return
            if url: processed_urls.add(url)
            
            new_node = DocNode(title, level=current_level, url=url)
            parent_node.add_child(new_node)
            
            # Find Children via DOM
            # Scope: The LI containing this link
            li = link.find_parent('li')
            if li:
                # Look for a nested container inside this LI
                # Nado uses DIV. GitBook uses UL. We check ALL children containers.
                # We specifically look for containers that hold `toclink`s.
                
                # Strategy: Find any descendant container that holds links
                # Caution: Use recursive=False or specific search to avoid finding siblings' children?
                # No, we are in 'li'. Everything in 'li' (except the header link) belongs to this item.
                
                # Robust: Find ALL descendant 'a' tags with toclink class in this LI.
                # Filter out the current 'link' itself.
                # Filter out 'grandchildren'? 
                # Grandchildren are inside nested LIs.
                # If we iterate ALL descendants, we flatten the hierarchy relative to 'link'.
                # But 'process_node_from_link' adds them as DIRECT children.
                # So we MUST find the IMMEDIATE child container.
                
                # Check direct children of LI (skip the 'a' header)
                # Usually: LI -> [A, DIV/UL]
                # So verify direct children.
                direct_children = li.find_all(recursive=False)
                for child in direct_children:
                    if child.name == 'a': continue # Skip the header itself
                    
                    # If this child is a container (div/ul), process its links
                    # But we need its "items".
                    # If it's a UL, items are LIs.
                    # If it's a DIV (Nado Flat), items are A tags + DIV pairs? Or DIV -> UL?
                    # `analyze_sidebar` said "Div -> Found X toclinks inside".
                    # It implies the DIV directly contains the A tags? Or DIV -> UL -> LI?
                    # Let's search for 'a.toclink' inside this container, BUT exclude any that are deeper?
                    
                    # Safe Strategy: 
                    # If we find a UL, iterate LIs.
                    # If we find a DIV, check if it contains UL.
                    container_ul = child.find('ul') if child.name == 'div' else (child if child.name == 'ul' else None)
                    
                    if container_ul:
                        # Standard list iter
                        c_lis = container_ul.find_all('li', recursive=False)
                        for c_li in c_lis:
                            candidates = c_li.find_all('a')
                            for c in candidates:
                                if any('toclink' in x for x in c.get('class', [])):
                                    process_node_from_link(c, new_node, current_level + 1)
                                    break # One link per LI
                    else:
                        # Maybe direct links inside DIV (weird flat structure)?
                        # Or DIV -> DIV -> ...
                        # Let's try finding all 'toclink's inside this container that are NOT nested in another UL/LI
                        # Actually, if we just recurse on `toclinks` found here, relying on `process` to establish hierarchy...
                        # If we treat them as direct children, it might be OK properly.
                        
                        # Let's try explicit:
                        sub_links = child.select('a[class*="toclink"]')
                        # Only process if they don't have a parent LI that is inside 'child'?
                        # i.e. are they "top level" relative to 'child'?
                        for sl in sub_links:
                             # Check if sl's parent LI is 'li' (our current LI) or 'child' itself logic?
                             # This is getting complex.
                             
                             # Simple Fallback: Just process them.
                             # If they are duplicates (grandchildren), 'processed_urls' prevents re-adding.
                             # BUT we want correct parent.
                             process_node_from_link(sl, new_node, current_level + 1)

            return

        # Process Roots (items at min_depth)
        for link in all_links:
            if link_depths[link] == min_depth:
                process_node_from_link(link, doc_root, level=1)
        
        self.logger.info(f"  📊 Flat Parser extracted {len(doc_root.children)} top-level nodes.")
        return doc_root

    async def verify_and_heal(self, tree_root, sitemap_urls):
        """
        Cross-Verification Logic:
        Visual Tree vs Sitemap URLs.
        """
        if not sitemap_urls: return tree_root
        
        tree_urls = set()
        def collect_urls(node):
            if node.url:
                u = node.url.split('#')[0].rstrip('/')
                tree_urls.add(u)
            for child in node.children:
                collect_urls(child)
        collect_urls(tree_root)
        
        missing = [u for u in sitemap_urls if u.split('#')[0].rstrip('/') not in tree_urls]
        
        if not missing:
            self.logger.info("  ✅ [TreeService] Verification Passed.")
            return tree_root
            
        self.logger.warning(f"  ⚠️ [TreeService] Found {len(missing)} missing pages. Healing...")
        
        driver = DriverManager().get_driver()
        for url in missing:
            try:
                tree_root = await self._heal_with_breadcrumbs(driver, tree_root, url)
            except Exception as e:
                self.logger.warning(f"  ❌ Failed to heal {url}: {e}")
                
        return tree_root
        
    async def _heal_with_breadcrumbs(self, driver, root, url):
        driver.get(url)
        time.sleep(1.5)
        
        crumbs = []
        try:
            container = driver.find_elements(By.CSS_SELECTOR, "nav[aria-label='Breadcrumb'] li, .gitbook-breadcrumbs a")
            if container:
                for el in container:
                    t = el.text.strip()
                    if t and t != '/': crumbs.append(t)
        except: pass
        
        if not crumbs:
            new_node = DocNode(title=driver.title, url=url, level=1)
            root.children.append(new_node)
            return root
            
        current_node = root
        if crumbs and (crumbs[0].lower() in ['home', 'docs', root.title.lower()]):
            crumbs.pop(0)
            
        self_title = crumbs.pop(-1) if crumbs else "Untitled"
        
        for segment in crumbs:
            found = None
            for child in current_node.children:
                if child.title.lower() == segment.lower():
                    found = child
                    break
            
            if found:
                current_node = found
            else:
                self.logger.info(f"    [Healing] New virtual dir: {segment}")
                new_dir = DocNode(title=segment, level=current_node.level + 1)
                current_node.children.append(new_dir)
                current_node = new_dir
                
        self.logger.info(f"    [Healing] Restored '{self_title}'")
        new_page = DocNode(title=self_title, url=url, level=current_node.level + 1)
        current_node.children.append(new_page)
        return root
