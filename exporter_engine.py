import os
import re
import zipfile
import urllib.parse
import xml.etree.ElementTree as ET
import logging
from bs4 import BeautifulSoup, Comment
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FramerExporter")

class FramerExporter:
    def __init__(self, target_url, options=None, log_callback=None):
        """
        target_url: URL of the Framer website (e.g. https://centipic.framer.website)
        options: dict of export options
            - strip_telemetry: bool (default True)
            - hide_badge: bool (default True)
            - rewrite_links: bool (default True)
            - max_pages: int (default 100)
        """
        self.raw_url = target_url.strip()
        if not self.raw_url.startswith(("http://", "https://")):
            self.raw_url = "https://" + self.raw_url
            
        parsed = urllib.parse.urlparse(self.raw_url)
        self.scheme = parsed.scheme
        self.netloc = parsed.netloc
        self.base_url = f"{self.scheme}://{self.netloc}"
        
        self.options = options or {}
        self.strip_telemetry = self.options.get("strip_telemetry", True)
        self.hide_badge = self.options.get("hide_badge", True)
        self.rewrite_links = self.options.get("rewrite_links", True)
        self.max_pages = self.options.get("max_pages", 100)
        
        self.log_callback = log_callback or (lambda msg, level="info": logger.info(msg))
        
        self.discovered_routes = set()
        self.route_file_map = {}
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def log(self, message, level="info"):
        self.log_callback(message, level)

    def normalize_route(self, path):
        """
        Normalizes a path into a clean canonical route string starting with /
        e.g. '/about/' -> '/about'
             '/.', '', '/' -> '/'
             '/./projects/seenwize/' -> '/projects/seenwize'
        """
        if not path:
            return "/"
        path = urllib.parse.urlparse(path).path
        parts = [p for p in path.split("/") if p and p != "."]
        if not parts:
            return "/"
        return "/" + "/".join(parts)

    def route_to_filepath(self, route):
        """
        Maps a route path like '/' or '/about' to relative output filepath
        '/' -> 'index.html'
        '/about' -> 'about/index.html'
        '/projects/seenwize' -> 'projects/seenwize/index.html'
        """
        route = self.normalize_route(route)
        if route == "/":
            return "index.html"
        
        clean_path = route.lstrip("/")
        return f"{clean_path}/index.html"


    def discover_routes(self):
        """
        Discovers all routes via sitemap.xml and home page link scanning.
        """
        self.log(f"Starting route discovery for {self.base_url}...")
        self.discovered_routes.add("/")
        
        # 1. Check sitemap.xml
        sitemap_urls = [
            f"{self.base_url}/sitemap.xml",
            f"{self.base_url}/sitemap_index.xml",
        ]
        
        for sm_url in sitemap_urls:
            try:
                resp = self.session.get(sm_url, timeout=10)
                if resp.status_code == 200 and "xml" in resp.headers.get("Content-Type", "").lower():
                    self.log(f"Found sitemap at {sm_url}")
                    root = ET.fromstring(resp.content)
                    # Handle XML namespaces
                    for elem in root.iter():
                        if elem.tag.endswith("loc") and elem.text:
                            url = elem.text.strip()
                            parsed = urllib.parse.urlparse(url)
                            if parsed.netloc == self.netloc:
                                route = self.normalize_route(parsed.path)
                                if route not in self.discovered_routes:
                                    self.discovered_routes.add(route)
                                    self.log(f"Discovered route from sitemap: {route}")
            except Exception as e:
                self.log(f"Sitemap check error for {sm_url}: {e}", level="warning")

        # 2. Fetch Home Page HTML to scan internal links
        try:
            home_resp = self.session.get(self.base_url, timeout=15)
            if home_resp.status_code == 200:
                soup = BeautifulSoup(home_resp.text, "html.parser")
                self._extract_links_from_soup(soup)
        except Exception as e:
            self.log(f"Error crawling root page: {e}", level="error")

        # Build route file map
        for route in self.discovered_routes:
            self.route_file_map[route] = self.route_to_filepath(route)

        self.log(f"Total discovered routes ({len(self.discovered_routes)}): {sorted(list(self.discovered_routes))}")
        return sorted(list(self.discovered_routes))

    def _extract_links_from_soup(self, soup):
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
                continue
            
            parsed = urllib.parse.urlparse(href)
            # Check if internal domain or relative path
            if not parsed.netloc or parsed.netloc == self.netloc:
                route = self.normalize_route(parsed.path)
                # Ignore static files like .png, .jpg, .css, .js, .pdf
                if not re.search(r"\.(png|jpe?g|gif|svg|webp|css|js|pdf|ico|json)$", route, re.I):
                    if route not in self.discovered_routes and len(self.discovered_routes) < self.max_pages:
                        self.discovered_routes.add(route)
                        self.log(f"Discovered route from page crawl: {route}")

    def fetch_page_html(self, route):
        """
        Fetches HTML for a specific route with retry.
        """
        url = f"{self.base_url}{route}" if route != "/" else self.base_url
        self.log(f"Fetching page HTML for route: {route} ({url})")
        
        for attempt in range(1, 3):
            try:
                resp = self.session.get(url, timeout=30)
                if resp.status_code == 200:
                    return resp.text
                else:
                    self.log(f"Failed to fetch {url} - Status Code: {resp.status_code}", level="error")
                    return None
            except Exception as e:
                if attempt == 1:
                    self.log(f"Fetch timeout/error on {route}, retrying once... ({e})", level="warning")
                else:
                    self.log(f"Exception fetching {url}: {e}", level="error")
                    return None

    def process_and_clean_html(self, html_content, current_route):
        """
        Parses and cleans the HTML:
        - Rewrites internal page links to export paths (/about -> /about/index.html)
        - Removes telemetry scripts (events.framer.com, init.mjs, etc.)
        - Hides/removes Framer badge if enabled
        - Leaves framerusercontent image & video links untouched
        """
        soup = BeautifulSoup(html_content, "html.parser")
        
        # 1. Rewrite Internal Page Links
        if self.rewrite_links:
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                if not href or href.startswith(("javascript:", "mailto:", "tel:", "data:")):
                    continue
                
                # Check for fragment
                parsed = urllib.parse.urlparse(href)
                fragment = f"#{parsed.fragment}" if parsed.fragment else ""
                
                if not parsed.netloc or parsed.netloc == self.netloc:
                    route = self.normalize_route(parsed.path)
                    if route in self.route_file_map or not re.search(r"\.[a-z0-9]+$", route, re.I):
                        target_filepath = self.route_file_map.get(route, self.route_to_filepath(route))
                        # Format as root-relative path e.g. /about/index.html
                        new_href = f"/{target_filepath}{fragment}"
                        a_tag["href"] = new_href

        # 2. Strip Telemetry & Editor Scripts if requested
        if self.strip_telemetry:
            # Remove scripts pointing to events.framer.com or framer.com/edit
            for script in soup.find_all("script"):
                src = script.get("src", "")
                content = script.string or ""
                if "events.framer.com" in src or "framer.com/edit" in src or "events.framer.com" in content or "__framer_force_showing_editorbar_since" in content:
                    script.decompose()
            
            # Remove editorbar style tags if present
            for style in soup.find_all("style"):
                if style.string and "#__framer-editorbar" in style.string:
                    # Clean out editorbar CSS rules
                    cleaned_css = re.sub(r"#__framer-editorbar[^{]*\{[^}]*\}", "", style.string)
                    style.string = cleaned_css

        # 3. Hide & Remove Framer Badge / Watermark if requested
        if self.hide_badge:
            # Selector-based decomposition
            badge_selectors = [
                "#framer-badge-container",
                "#__framer-badge-container",
                "#__framer-editorbar-container",
                "#__framer-editorbar",
                "[id*='framer-badge']",
                "[class*='framer-badge']",
                "[data-framer-badge]",
                ".framer-badge",
            ]
            for selector in badge_selectors:
                for elem in soup.select(selector):
                    elem.decompose()

            # Text-based decomposition for "Made in Framer" elements
            for tag in soup.find_all(True):
                if tag.string and "made in framer" in tag.string.lower():
                    target = tag.find_parent("a") or tag.find_parent("div") or tag
                    target.decompose()

            # Link-based decomposition for Framer referral/watermark links
            for a_tag in soup.find_all("a", href=True):
                href_lower = a_tag["href"].lower()
                if "framer.com" in href_lower and ("utm_" in href_lower or "badge" in href_lower or "made-in-framer" in href_lower):
                    parent = a_tag.parent
                    if parent and parent.name in ["div", "span", "section"]:
                        parent.decompose()
                    else:
                        a_tag.decompose()

            # Comment-based decomposition for HTML comments containing "Made in Framer"
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                if "made in framer" in comment.lower():
                    comment.extract()

            # Inject aggressive CSS override rule to ensure no badge or editorbar can ever render

            if soup.head:
                badge_hide_style = soup.new_tag("style")
                badge_hide_style.string = (
                    "#framer-badge-container, #__framer-badge-container, [id*='framer-badge'], "
                    "[class*='framer-badge'], [data-framer-badge], .framer-badge, "
                    "#__framer-editorbar-container, #__framer-editorbar, "
                    "a[href*='framer.com?utm'], a[href*='framer.com/?utm'] "
                    "{ display: none !important; opacity: 0 !important; visibility: hidden !important; "
                    "pointer-events: none !important; width: 0 !important; height: 0 !important; }"
                )
                soup.head.append(badge_hide_style)


        return str(soup)

    def export_site(self, output_dir):
        """
        Main execution flow:
        1. Discover all routes
        2. Fetch HTML for each route
        3. Clean and rewrite HTML
        4. Write files into output_dir
        5. Create a ZIP package
        """
        os.makedirs(output_dir, exist_ok=True)
        routes = self.discover_routes()
        
        exported_files = []
        
        for idx, route in enumerate(routes, 1):
            self.log(f"Processing route [{idx}/{len(routes)}]: {route}")
            html = self.fetch_page_html(route)
            if not html:
                self.log(f"Skipping route {route} due to fetch failure.", level="warning")
                continue
                
            processed_html = self.process_and_clean_html(html, route)
            rel_filepath = self.route_file_map[route]
            full_filepath = os.path.join(output_dir, rel_filepath)
            
            os.makedirs(os.path.dirname(full_filepath), exist_ok=True)
            with open(full_filepath, "w", encoding="utf-8") as f:
                f.write(processed_html)
                
            exported_files.append(rel_filepath)
            self.log(f"Saved: {rel_filepath}")

        # Create ZIP file
        zip_filename = "website_export.zip"
        zip_filepath = os.path.join(output_dir, zip_filename)
        self.log(f"Creating ZIP archive: {zip_filename}...")
        
        with zipfile.ZipFile(zip_filepath, "w", zipfile.ZIP_DEFLATED) as zipf:
            for rel_file in exported_files:
                abs_file = os.path.join(output_dir, rel_file)
                zipf.write(abs_file, arcname=rel_file)

        self.log(f"Export completed successfully! Total pages exported: {len(exported_files)}")
        return {
            "output_dir": output_dir,
            "zip_filepath": zip_filepath,
            "exported_files": exported_files,
            "total_pages": len(exported_files),
        }
