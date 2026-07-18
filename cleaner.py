import sys

filepath = "Organizador.py"
with open(filepath, "r", encoding="utf-8") as f:
    lines = f.readlines()

start_idx = -1
for i in range(990, len(lines)):
    if lines[i].startswith("    db = DatabaseManager()"):
        start_idx = i
        break

if start_idx == -1:
    print("Could not find start index")
    sys.exit(1)

end_idx = -1
for i in range(start_idx, len(lines)):
    if lines[i].startswith("if __name__ == \"__main__\":"):
        end_idx = i
        break

if end_idx == -1:
    print("Could not find end index")
    sys.exit(1)

new_lines = lines[:start_idx] + lines[end_idx:]

with open(filepath, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print(f"Removed lines from {start_idx + 1} to {end_idx}")
