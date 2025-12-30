from bs4 import BeautifulSoup
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

filename = "sidebar_debug.html"
print(f"Analyzing {filename}...")

with open(filename, 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f, 'html.parser')

# 1. Find Onboarding
onboarding = soup.select_one('a[href="/onboarding-tutorial"]')
if not onboarding:
    print("❌ Onboarding link NOT FOUND (href match failed)")
    # Try text match
    onboarding = soup.find(lambda t: t.name == 'a' and 'Onboarding Tutorial' in t.text)
    if not onboarding:
        print("❌ Onboarding link NOT FOUND (text match failed)")
        sys.exit(1)
    else:
        print(f"✅ Onboarding found via text match. Tag: {onboarding.name}, Classes: {onboarding.get('class')}")
else:
    print(f"✅ Onboarding found via href. Tag: {onboarding.name}, Classes: {onboarding.get('class')}")

# 2. Check Next Sibling
print("\n--- Onboarding Siblings ---")
curr = onboarding.next_sibling
count = 0
found_div = False
while curr and count < 5:
    print(f"Sibling {count+1}: Type={type(curr)}, Name={curr.name}, Text (repr)={repr(curr.text)[:50] if curr.name else repr(curr)[:50]}")
    if curr.name == 'div':
        found_div = True
        print("  --> THIS IS THE DIV WE WANT!")
        # Check children of div
        children = curr.select('a[class*="toclink"]')
        print(f"  --> Found {len(children)} toclinks inside.")
        for c in children:
            print(f"      - {c.get_text(strip=True)}")
    curr = curr.next_sibling
    count += 1

# 3. Find Bridging
print("\n--- Bridging Check ---")
bridging = soup.find(lambda t: t.name == 'a' and 'Bridging USDT0 to Ink' in t.text)
if bridging:
    print(f"✅ Bridging found. Classes: {bridging.get('class')}")
    # 4. Check Parents
    parent = bridging.parent
    grandparent = parent.parent
    greatgrand = grandparent.parent if grandparent else None
    
    print(f"Parent: {parent.name} (Class: {parent.get('class')})")
    print(f"Grandparent: {grandparent.name} (Class: {grandparent.get('class')})")
    if greatgrand:
        print(f"GreatGrandParent: {greatgrand.name} (Class: {greatgrand.get('class')})")
        
        # Check prev sibling of GreatGrandParent (assuming it's the group div)
        # Wait, if Bridging -> li -> ul -> div (Group)
        # Then GreatGrandParent is the DIV.
        # Let's check ITS prev sibling.
        prev = greatgrand.previous_sibling
        print(f"GreatGrandParent Prev Sibling: {type(prev)}, Name={prev.name if prev else 'None'}")
        
        # Check find_previous_sibling('a')
        prev_a = greatgrand.find_previous_sibling('a')
        print(f"GreatGrandParent find_previous_sibling('a'): {prev_a}")
        if prev_a:
             print(f"  --> Identified as: {prev_a.get_text(strip=True)}")
else:
    print("❌ Bridging link NOT FOUND")
