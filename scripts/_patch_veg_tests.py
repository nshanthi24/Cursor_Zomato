from pathlib import Path
import re

for path in Path("tests").glob("test_*.py"):
    text = path.read_text(encoding="utf-8")
    text2 = re.sub(
        r'("budget_band":\s*[^\n]+,)',
        r'\1\n                "veg_type": "veg_and_non_veg",',
        text,
    )
    text2 = text2.replace(
        '"veg_type": "veg_and_non_veg",\n                "veg_type": "veg_and_non_veg",',
        '"veg_type": "veg_and_non_veg",',
    )
    # ValidatedRecommendation missing veg_type after budget_band=
    text2 = re.sub(
        r"(budget_band=\"[^\"]+\",\n)(\s*)(location=)",
        r'\1\2veg_type="veg_and_non_veg",\n\2\3',
        text2,
    )
    text2 = re.sub(
        r"(budget_band=\"[^\"]+\",\n)(\s*)(veg_type=\"veg_and_non_veg\",\n)(\s*)(veg_type=\"veg_and_non_veg\",\n)",
        r"\1\2\3",
        text2,
    )
    if text2 != text:
        path.write_text(text2, encoding="utf-8")
        print("updated", path)
    else:
        print("unchanged", path)
