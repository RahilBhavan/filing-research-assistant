"""Create a blind human-review sheet from a frozen question set."""
import argparse
import csv
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('questions', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.questions.read_text().splitlines()]
    fields = [
        'id', 'split', 'question', 'expected_answerable', 'source_urls',
        'reviewer_answerable', 'citation_support_0_1_2', 'scope_correct_yes_no',
        'notes', 'reviewer_name', 'reviewed_at',
    ]
    with args.destination.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            urls = sorted({gold.get('source_url', '') for gold in row['gold'] if gold.get('source_url')})
            writer.writerow({
                'id': row['id'], 'split': row['split'], 'question': row['question'],
                'expected_answerable': row['answerable'], 'source_urls': ' '.join(urls),
            })


if __name__ == '__main__':
    main()

