from pathlib import Path

for path in Path("tests").glob("test_*.py"):
    lines = path.read_text(encoding="utf-8").splitlines()
    fixed = []
    changed = False
    for line in lines:
        if line.startswith('                "veg_type":') and not line.startswith(
            '        "veg_type":'
        ):
            # normalize to 8-space indent inside typical dicts; keep relative if deeper
            stripped = line.lstrip()
            # if previous fixed line used 8 spaces for keys, match that
            indent = "        "
            if fixed and fixed[-1].startswith("                "):
                indent = "                "
            elif fixed and fixed[-1].startswith("            "):
                indent = "            "
            elif fixed and fixed[-1].startswith("        "):
                indent = "        "
            newline = indent + stripped
            if newline != line:
                changed = True
            fixed.append(newline)
        else:
            fixed.append(line)
    if changed:
        path.write_text("\n".join(fixed) + "\n", encoding="utf-8")
        print("fixed", path)
