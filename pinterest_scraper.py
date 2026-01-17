"""
Pinterest Ultra-Fast Scraper - 50k Pins Edition
===============================================
Ye script maximum speed ke liye design ki gayi hai. 
URL collection aur detail extraction (Title + Saves) parallel me chalti hain.

Key Features:
- Overlapping Parallelism: URL milte hi detail extraction shuru ho jati hai.
- High Concurrency: 40-50 parallel tasks.
- Resource Optimization: Unnecessary images/CSS block kiye gaye hain.
"""

import asyncio
import csv
import re
from playwright.async_api import async_playwright
from datetime import datetime
import os
import sys

# --- CONFIGURATION ---
PROFILE_URL = "https://www.pinterest.com/bnjweigel/pins/"
OUTPUT_DIR = "output"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "pinterest_final_data.csv")

# BATCH SETTINGS
TARGET_COUNT = 50000      # 50k Target
CONCURRENT_TASKS = 40    # High concurrency for speed

# PERFORMANCE SETTINGS
HEADLESS = True
MAX_RETRIES = 2
SCROLL_DELAY = 1.5       # Faster scrolling
MAX_SCROLL_ATTEMPTS = 10000
NO_NEW_PINS_WAIT = 10    # Wait longer for 50k pins
# ---------------------

# Global state
results = []
seen_urls = set()
queue = asyncio.Queue()
processed_count = 0
extraction_done = asyncio.Event()
results_lock = asyncio.Lock()

async def get_pin_details_worker(browser, semaphore):
    """
    Worker that pulls URLs from the queue and extracts details immediately.
    """
    global processed_count
    while True:
        # Get a URL from the queue
        url = await queue.get()
        
        async with semaphore:
            retry_count = 0
            success = False
            while retry_count <= MAX_RETRIES and not success:
                context = None
                try:
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                    page = await context.new_page()
                    
                    # Speed optimization: Block images, CSS, and fonts
                    await page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda route: route.abort())
                    
                    await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    
                    # Extract Title and Saves
                    content = await page.content()
                    
                    # Title Extraction
                    title_match = re.search(r'<h1[^>]*>(.*?)</h1>', content, re.IGNORECASE | re.DOTALL)
                    title = title_match.group(1).strip() if title_match else "N/A"
                    
                    # Saves Extraction
                    patterns = [
                        r'"saves"[:\s]+(\d+)',
                        r'"aggregated_pin_data"[^}]*"saves"[:\s]+(\d+)',
                        r'"save_count"[:\s]+(\d+)',
                        r'saves["\s:]+(\d+)',
                        r'(\d+)\s+saves',
                        r'"repinCount"[:\s]+(\d+)',
                    ]
                    saves_count = "N/A"
                    for pattern in patterns:
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        if matches:
                            saves_count = max([int(m) for m in matches])
                            break
                    
                    async with results_lock:
                        results.append({
                            'url': url,
                            'title': title[:100], # Limit title length
                            'saves': saves_count,
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                        processed_count += 1
                        if processed_count % 10 == 0:
                            print(f"   ⚡ Processed {processed_count} pins...", end='\r')
                    
                    success = True
                except Exception:
                    retry_count += 1
                    if retry_count > MAX_RETRIES:
                        async with results_lock:
                            results.append({'url': url, 'title': "Error", 'saves': "Error", 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
                            processed_count += 1
                    else:
                        await asyncio.sleep(1)
                finally:
                    if context: await context.close()
        
        queue.task_done()
        if queue.empty() and extraction_done.is_set():
            break

async def url_collector(profile_url):
    """
    Collects URLs from the profile and feeds them into the queue.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        page = await browser.new_page()
        await page.goto(profile_url, wait_until="domcontentloaded")
        
        scrolls = 0
        no_new_pins_count = 0
        previous_total = 0
        
        print(f"🚀 Starting URL Collection & Parallel Extraction...")
        
        while scrolls < MAX_SCROLL_ATTEMPTS and len(seen_urls) < TARGET_COUNT:
            links = await page.query_selector_all('a[href*="/pin/"]')
            new_found = 0
            for link in links:
                href = await link.get_attribute('href')
                if href:
                    url = f"https://www.pinterest.com{href.split('?')[0]}" if href.startswith('/') else href.split('?')[0]
                    if url not in seen_urls:
                        seen_urls.add(url)
                        await queue.put(url)
                        new_found += 1
            
            if len(seen_urls) >= TARGET_COUNT:
                break
                
            if len(seen_urls) == previous_total:
                no_new_pins_count += 1
                if no_new_pins_count >= NO_NEW_PINS_WAIT:
                    print(f"\n⚠️ No more pins found after {no_new_pins_count} attempts.")
                    break
            else:
                no_new_pins_count = 0
            
            previous_total = len(seen_urls)
            print(f"   🔍 Found {len(seen_urls)} pins... (Queue size: {queue.qsize()})", end='\r')
            
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(SCROLL_DELAY)
            scrolls += 1
            
        await browser.close()
        extraction_done.set()
        print(f"\n✅ URL Collection Finished. Total: {len(seen_urls)}")

async def main():
    start_time = datetime.now()
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        semaphore = asyncio.Semaphore(CONCURRENT_TASKS)
        
        # Start workers
        workers = [asyncio.create_task(get_pin_details_worker(browser, semaphore)) for _ in range(CONCURRENT_TASKS)]
        
        # Start collector
        await url_collector(PROFILE_URL)
        
        # Wait for all tasks in queue to be processed
        await queue.join()
        
        # Stop workers
        for w in workers:
            w.cancel()
        
        await browser.close()

    # Save Results
    if results:
        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['url', 'title', 'saves', 'timestamp'])
            writer.writeheader()
            writer.writerows(results)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n\n{'='*70}")
        print(f"✅ ULTRA-FAST SCRAPING COMPLETE!")
        print(f"📊 Total Pins: {len(results)}")
        print(f"⏱️  Total Time: {elapsed/60:.1f} minutes")
        print(f"🚀 Speed: {len(results)/(elapsed/3600):.0f} pins per hour")
        print(f"📁 Output File: {OUTPUT_FILE}")
        print(f"{'='*70}\n")

if __name__ == "__main__":
    asyncio.run(main())
