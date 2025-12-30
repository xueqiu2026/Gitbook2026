import sys

filename = sys.argv[1]
print(f"Scanning {filename} for ALL headers...")
try:
    with open(filename, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            clean = line.strip()
            if clean.startswith('#'):
                print(f"Line {i+1}: {clean}")
except Exception as e:
    print(f"Error: {e}")
