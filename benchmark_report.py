"""
Accuracy Dashboard & Benchmark Report
Generates a terminal report from the SEC Key Terms extraction JSON.
"""
import json
import pathlib
import sys
from collections import Counter

def generate_report(json_path: pathlib.Path):
    if not json_path.exists():
        print(f"Error: Could not find file {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print(f"Error: {json_path.name} is not a valid JSON file.")
            return

    total_filings = len(data)
    if total_filings == 0:
        print("No filings found in the JSON file.")
        return

    # Tracking Counters
    status_counts = Counter()
    method_counts = Counter()
    missing_fields = Counter()
    validation_errors = 0
    total_fields_extracted = 0

    # Crunch the Data
    for filing in data:
        status_counts[filing.get("extraction_status", "unknown")] += 1
        
        # Count extraction methods used
        methods = filing.get("extraction_methods", {})
        for field, method in methods.items():
            method_counts[method] += 1
            total_fields_extracted += 1
            
        # Count missing fields
        for missing in filing.get("missing_fields", []):
            missing_fields[missing] += 1
            
        # Count validation warnings
        if filing.get("validation_warnings"):
            validation_errors += 1

    # Calculate Percentages
    complete_pct = (status_counts["complete"] / total_filings) * 100
    val_error_pct = (validation_errors / total_filings) * 100

    # Print the Dashboard
    print("\n" + "=" * 65)
    print(" 📊 SEC EXTRACTION ENGINE : BENCHMARK DASHBOARD")
    print("=" * 65)
    print(f" File Analyzed  : {json_path.name}")
    print(f" Total Filings  : {total_filings}")
    print("-" * 65)
    
    print(" COMPLETION METRICS ")
    print(f"  ✅ Complete    : {status_counts['complete']} ({complete_pct:.1f}%)")
    print(f"  ⚠️ Partial     : {status_counts['partial']}")
    print(f"  ❌ Failed      : {status_counts['failed']}")
    print("-" * 65)
    
    print(" HYBRID EXTRACTION BREAKDOWN ")
    print(f"  Total Data Points Extracted : {total_fields_extracted}")
    for method, count in method_counts.most_common():
        pct = (count / total_fields_extracted) * 100 if total_fields_extracted else 0
        # Highlight the AI usage
        if "llm" in method:
            print(f"  🤖 {method.ljust(21)} : {count} ({pct:.1f}%)")
        else:
            print(f"  ⚡ {method.ljust(21)} : {count} ({pct:.1f}%)")
    print("-" * 65)
    
    print(" QUALITY & VALIDATION LAYER ")
    print(f"  🚨 Filings w/ Warnings     : {validation_errors} ({val_error_pct:.1f}%)")
    if missing_fields:
        print("  🔍 Top Missing Fields      :")
        for field, count in missing_fields.most_common(3):
            print(f"       - {field.ljust(18)} : {count} times")
    print("=" * 65 + "\n")

if __name__ == "__main__":
    # If a specific file is passed in the terminal, use it.
    if len(sys.argv) > 1:
        target_file = pathlib.Path(sys.argv[1])
    else:
        # Otherwise, automatically find the newest JSON in the output directory
        output_dir = pathlib.Path("output")
        files = list(output_dir.glob("*.json"))
        if not files:
            print("No JSON files found in the output/ directory.")
            sys.exit(1)
        # Sort by modification time to get the most recent batch
        target_file = max(files, key=lambda f: f.stat().st_mtime)
    
    generate_report(target_file)