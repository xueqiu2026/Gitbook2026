import sys

filename = sys.argv[1]
targets = ["Onboarding Tutorial", "Bridging USDT0 to Ink", "FAQs", "Get Started", "Place Order", "Developer Resources"]

print(f"Scanning {filename} for section order...")
try:
    with open(filename, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            clean = line.strip()
            for t in targets:
                if t in clean and clean.startswith('#'):
                    print(f"Line {i+1}: {clean}")
except Exception as e:
    print(f"Error: {e}")
