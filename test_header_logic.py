
import unittest
import re

class ContentConsolidatorHeaders:
    """Mock class containing only the logic we want to test/implement"""
    
    def adjust_headers(self, content, target_level_h2_based=2, page_title=""):
        lines = content.split('\n')
        
        # 1. Analyze content structure
        min_header_level = 99
        first_header_index = -1
        first_header_level = -1
        first_header_text = ""
        
        for i, line in enumerate(lines):
            match = re.match(r'^(#+)\s+(.*)', line)
            if match:
                level = len(match.group(1))
                min_header_level = min(min_header_level, level)
                if first_header_index == -1:
                    first_header_index = i
                    first_header_level = level
                    first_header_text = match.group(2).strip()
        
        if min_header_level == 99:
            return content

        # 2. Check deduplication for the FIRST header only
        is_dupe = False
        if first_header_index != -1:
            clean_text = re.sub(r'[^\w\s]', '', first_header_text.lower())
            clean_title = re.sub(r'[^\w\s]', '', page_title.lower())
            # Expanded fuzzy match
            if clean_text == clean_title or clean_title in clean_text or clean_text in clean_title:
                is_dupe = True

        # 3. Calculate Shift
        # Base rule: Map Top Content Level -> Target Level + 1 (Child)
        # Exception: If Top Content IS the Page Title (Level 1 & Dupe), map it to Target Level (Parent)
        #            So its children (Level 2) map to Target Level + 1 (Child)
        
        desired_base_level = target_level_h2_based + 1
        if min_header_level == 1 and is_dupe:
            desired_base_level = target_level_h2_based

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
                
        return '\n'.join(processed_lines)

class TestHeaderLogic(unittest.TestCase):
    
    def setUp(self):
        self.processor = ContentConsolidatorHeaders()

    def test_basic_demotion(self):
        # Case: Page is inserted as H2 (Level 2).
        # Content has H2. Expect H2 -> H3.
        content = "## Sub Header\nText"
        expected = "### Sub Header\nText"
        result = self.processor.adjust_headers(content, target_level_h2_based=2, page_title="Main Page")
        self.assertEqual(result, expected)

    def test_h1_demotion(self):
        # Case: Page is inserted as H2.
        # Content has H1 (Subtitle). Expect H1 -> H3 (Since H2 is the page title).
        content = "# Page SubTitle\nText"
        expected = "### Page SubTitle\nText"
        result = self.processor.adjust_headers(content, target_level_h2_based=2, page_title="Main Page")
        self.assertEqual(result, expected)
        
    def test_deduplication(self):
        # Case: Page Title is "Mission". Content starts with "# Mission".
        # Expect "# Mission" to be removed.
        content = "# Mission\nOur mission is..."
        expected = "Our mission is..."
        result = self.processor.adjust_headers(content, target_level_h2_based=2, page_title="Mission")
        self.assertEqual(result.strip(), expected.strip())

    def test_deduplication_fuzzy(self):
        content = "# The Mission\nText"
        # Adjusted expectations based on strictness of logic. 
        # If logic is 'contains', 'Mission' in 'The Mission' -> True.
        expected = "Text"
        result = self.processor.adjust_headers(content, target_level_h2_based=2, page_title="Mission")
        self.assertEqual(result.strip(), expected.strip())

    def test_mixed_levels(self):
        # Level 2 page.
        # Content:
        # # Title (Dupe) -> Remove
        # ## Sub1 -> H3
        # ### Sub2 -> H4
        content = "# Mixed\n## Sub1\n### Sub2"
        expected = "### Sub1\n#### Sub2"
        result = self.processor.adjust_headers(content, target_level_h2_based=2, page_title="Mixed")
        self.assertEqual(result.strip(), expected.strip())

if __name__ == '__main__':
    unittest.main()
