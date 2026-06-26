import json
from pathlib import Path

INPUT_DIR = Path(r"C:\Projects\NER_DRUG\data\annotated")
OUTPUT_DIR = INPUT_DIR / "done"
OUTPUT_FILE = OUTPUT_DIR / "drug.jsonl"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

jsonl_files = sorted(INPUT_DIR.glob("*.jsonl"))

print("INPUT_DIR:", INPUT_DIR)
print("OUTPUT_FILE:", OUTPUT_FILE)
print("Số file jsonl sẽ gộp:", len(jsonl_files))

if not jsonl_files:
    raise FileNotFoundError("Không tìm thấy file .jsonl nào để gộp.")

total_lines = 0
bad_lines = []

with open(OUTPUT_FILE, "w", encoding="utf-8", newline="\n") as fout:
    for file in jsonl_files:
        file_line_count = 0

        with open(file, "r", encoding="utf-8") as fin:
            for line_no, line in enumerate(fin, start=1):
                line = line.strip()

                if not line:
                    continue

                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    bad_lines.append({
                        "file": file.name,
                        "line": line_no,
                        "error": str(e),
                    })
                    continue

                fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
                total_lines += 1
                file_line_count += 1

        print(f"[OK] {file.name}: {file_line_count} dòng")

print("\nHoàn tất.")
print("Đã xuất:", OUTPUT_FILE)
print("Tổng dòng đã gộp:", total_lines)

if bad_lines:
    print("\nCó dòng lỗi JSON, đã bỏ qua:")
    for item in bad_lines:
        print(f"- {item['file']} dòng {item['line']}: {item['error']}")