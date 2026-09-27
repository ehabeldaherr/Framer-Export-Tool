import argparse
import sys
import os
from exporter_engine import FramerExporter

# Fix stdout encoding for Windows terminal
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Export Framer website to clean, static HTML files.")
    parser.add_argument("url", help="URL of the Framer website (e.g. https://centipic.framer.website)")
    parser.add_argument("-o", "--output", default="./exported_website", help="Output directory path (default: ./exported_website)")
    parser.add_argument("--keep-telemetry", action="store_true", help="Keep Framer telemetry scripts")
    parser.add_argument("--keep-badge", action="store_true", help="Keep Framer watermark badge")
    parser.add_argument("--no-link-rewrite", action="store_true", help="Do not rewrite internal page links")
    parser.add_argument("--max-pages", type=int, default=100, help="Maximum number of pages to export")

    args = parser.parse_args()

    options = {
        "strip_telemetry": not args.keep_telemetry,
        "hide_badge": not args.keep_badge,
        "rewrite_links": not args.no_link_rewrite,
        "max_pages": args.max_pages,
    }

    print(f"🚀 Starting Framer Export for: {args.url}")
    print(f"📁 Output Directory: {os.path.abspath(args.output)}")
    print(f"⚙️ Options: {options}\n")

    def cli_logger(msg, level="info"):
        prefix = {
            "info": "[INFO]",
            "warning": "⚠️ [WARN]",
            "error": "❌ [ERR]",
        }.get(level, "[LOG]")
        print(f"{prefix} {msg}")

    exporter = FramerExporter(args.url, options=options, log_callback=cli_logger)
    result = exporter.export_site(args.output)

    print("\n🎉 Export Complete!")
    print(f"📄 Total Pages: {result['total_pages']}")
    print(f"📦 ZIP Archive Created: {result['zip_filepath']}")
    print("Exported files list:")
    for f in result["exported_files"]:
        print(f" - {f}")

if __name__ == "__main__":
    main()
