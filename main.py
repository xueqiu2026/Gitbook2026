#!/usr/bin/env python3
"""
GitBook Multi-Strategy Downloader v4.0 - Universal GitBook downloader
Author: xueqiu2026
Version: 4.0.0
Description: Uses multiple strategies to download any GitBook - GitHub cloning, sitemap parsing, or enhanced web scraping
"""

import asyncio
import argparse
import sys
from pathlib import Path
from gitbook_multi_downloader import GitBookMultiDownloader
from utils.logger import setup_logger

def main():
    parser = argparse.ArgumentParser(
        description="Universal GitBook downloader with multiple fallback strategies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Strategies (tried in order):
  1. GitHub Repository Cloning (fastest - seconds)
  2. Sitemap-based Download (fast - under a minute) 
  3. Enhanced Web Scraping (slower but works on any GitBook - few minutes)

Examples:
  %(prog)s https://sallam.gitbook.io/sec-88/
  %(prog)s https://appsecexplained.gitbook.io/appsecexplained -o appsec.md
  %(prog)s https://docs.example.com --strategy scraping --max-concurrent 20
  %(prog)s https://site.gitbook.io/docs/ --section-path specific-section
        """
    )

    parser.add_argument('url', help='GitBook URL to download')
    parser.add_argument('-o', '--output', default='gitbook_download.md', help='Output file')
    parser.add_argument('--strategy', choices=['auto', 'github', 'sitemap', 'scraping', 'universal', 'fusion'], 
                       default='auto', help='Download strategy (default: auto - tries all)')
    parser.add_argument('--section-path', help='Only process specific section/directory (Include)')
    parser.add_argument('--exclude', help='Exclude paths pattern')
    parser.add_argument('--max-concurrent', type=int, default=15, help='Max concurrent requests')
    parser.add_argument('--delay', type=float, default=0.1, help='Delay between requests')
    parser.add_argument('--timeout', type=int, default=30, help='Request timeout')
    parser.add_argument('--include-assets', action='store_true', help='Download images/assets')
    parser.add_argument('--keep-temp', action='store_true', help='Keep temporary files')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    parser.add_argument('--use-selenium', action='store_true', help='Force Selenium for JS rendering')

    args = parser.parse_args()

    logger = setup_logger(verbose=args.verbose)

    if not args.url.startswith(('http://', 'https://')):
        logger.error("URL must start with http:// or https://")
        sys.exit(1)

    # Create output directory
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    downloader = GitBookMultiDownloader(
        url=args.url,
        output_file=args.output,
        strategy=args.strategy,
        section_path=args.section_path,
        exclude_path=args.exclude,
        max_concurrent=args.max_concurrent,
        delay=args.delay,
        timeout=args.timeout,
        include_assets=args.include_assets,
        keep_temp=args.keep_temp,
        use_selenium=args.use_selenium,
        verbose=args.verbose
    )

    try:
        logger.info(f"🚀 Starting GitBook download: {args.url}")
        logger.info(f"📁 Output: {args.output}")
        logger.info(f"🎯 Strategy: {args.strategy}")

        result = asyncio.run(downloader.download())

        logger.info(f"✅ Success! Downloaded to {args.output}")
        logger.info(f"📊 Strategy used: {result['strategy_used']}")
        logger.info(f"📚 Pages: {result['pages_downloaded']}")
        logger.info(f"⏱️  Time: {result['duration']:.2f}s")
        logger.info(f"🚀 Speed: {result['pages_per_second']:.1f} pages/sec")

        if result.get('assets_downloaded', 0) > 0:
            logger.info(f"🖼️  Assets: {result['assets_downloaded']}")

    except KeyboardInterrupt:
        logger.info("🛑 Cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Failed: {e}")
        if args.verbose:
            import traceback
            logger.debug(traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
    main()
