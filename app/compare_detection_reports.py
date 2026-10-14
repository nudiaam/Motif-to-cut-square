"""Compare two saved JSON reports or diagnostic ZIP packages locally."""
import argparse
import json
from pathlib import Path
import zipfile
from app.imaging.run_diagnostics import compare_reports


def read_report(path):
    path = Path(path)
    if path.suffix.lower() == '.zip':
        with zipfile.ZipFile(path) as archive:
            return json.loads(archive.read('report.json'))
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('first', type=Path)
    parser.add_argument('second', type=Path)
    args = parser.parse_args()
    print(json.dumps(compare_reports(read_report(args.first), read_report(args.second)), indent=2))


if __name__ == '__main__':
    main()
