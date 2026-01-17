"""
Pinterest Integrated Scraper - URL, Title & Saves
=================================================
Ye script profile se pins collect karti hai aur phir har pin ke 
Title aur Saves count extract karke aik single CSV file me save karti hai.

Requirements:
    pip install playwright
    python -m playwright install chromium
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
SKIP_COUNT = 0           # Kitne pins skip karne hain
TARGET_COUNT = 30000      # Kitne pins extract karne hain

# PERFORMANCE SETTINGS
CONCURRENT_TASKS = 20    # Parallel tasks for details extraction
HEADLESS = True
MAX_RETRIES = 2
SCROLL_DELAY = 2.0
MAX_SCROLL_ATTEMPTS = 2000
NO_NEW_PINS_WAIT = 5
# ---------------------

# Global results
results = []
results_lock = asyncio.Lock()
processed_count = 0

async def get_pin_details_integrated(browser, url, semaphore, task_id):
    """
    Extract Title and Saves count for a specific Pin URL
    """
    global processed_count
    async with semaphore:
        retry_count = 0
        while retry_count <= MAX_RETRIES:
            context = None
            try:
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = await context.new_page()
                
                # Speed optimization: Block unnecessary resources
                # await page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda route: route.abort())
                
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(1) # Small wait for dynamic content
                
                # 1. Extract Title and Date using JS
                data = await page.evaluate("""() => {
                    let title = "N/A";
                    let date = "N/A";
                    const h1 = document.querySelector('h1');
                    if (h1 && h1.innerText && !h1.innerText.startsWith('Pin on')) {
                        title = h1.innerText.trim();
                    } else {
                        const ogTitle = document.querySelector('meta[property="og:title"]');
                        if (ogTitle) title = ogTitle.content.replace(' - Pinterest', '').trim();
                    }
                    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                    for (let s of scripts) {
                        try {
                            const json = JSON.parse(s.text);
                            if (json.datePublished) { date = json.datePublished; break; }
                            if (json.uploadDate) { date = json.uploadDate; break; }
                        } catch(e) {}
                    }
                    return { title, date };
                }""")

                # 2. Extract Saves Count using Regex on page content
                content = await page.content()
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
                        'title': data['title'],
                        'saves': saves_count,
                        'upload_date': data['date'],
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    processed_count += 1
                    status = f"✓ {saves_count}" if isinstance(saves_count, int) else f"⚠ {saves_count}"
                    print(f"   [{processed_count}] {status} | {data['title'][:30]}... | {url}")
                
                return
                
            except Exception as e:
                retry_count += 1
                if retry_count > MAX_RETRIES:
                    async with results_lock:
                        results.append({
                            'url': url, 'title': "Error", 'saves': "Error", 
                            'upload_date': "N/A", 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                        processed_count += 1
                else:
                    await asyncio.sleep(2)
            finally:
                if context: await context.close()

async def extract_urls_turbo(profile_url, skip, target):
    """
    Collect Pin URLs from the profile page
    """
    new_urls = []
    async with async_playwright() as p:
        print(f"\\n{'='*70}")
        print(f"🚀 PINTEREST INTEGRATED SCRAPER")
        print(f"{'='*70}")
        print(f"📊 Profile: {profile_url}")
        print(f"⏳ Step 1: Collecting URLs...\\n")
        
        browser = await p.chromium.launch(headless=HEADLESS)
        page = await browser.new_page()
        await page.goto(profile_url, wait_until="domcontentloaded")
        
        seen = set()
        all_urls = []
        scrolls = 0
        no_new_pins_count = 0
        previous_count = 0
        
        while scrolls < MAX_SCROLL_ATTEMPTS:
            links = await page.query_selector_all('a[href*="/pin/"]')
            for link in links:
                href = await link.get_attribute('href')
                if href:
                    url = f"https://www.pinterest.com{href.split('?')[0]}" if href.startswith('/') else href.split('?')[0]
                    if url not in seen:
                        seen.add(url)
                        all_urls.append(url)
                        if len(all_urls) > skip:
                            new_urls.append(url)
                            if len(new_urls) >= target: break
            
            if len(new_urls) >= target: break
            
            if len(new_urls) == previous_count:
                no_new_pins_count += 1
                if no_new_pins_count >= NO_NEW_PINS_WAIT: break
            else:
                no_new_pins_count = 0
            
            previous_count = len(new_urls)
            print(f"   🔍 Found {len(all_urls)} total pins... ({len(new_urls)} new)", end='\\r')
            
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(SCROLL_DELAY)
            scrolls += 1
            
        await browser.close()
        print(f"\\n\\n✅ URL Collection Complete: {len(new_urls)} pins ready.")
    
    return new_urls

async def main():
    start_time = datetime.now()
    
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # Step 1: Get URLs
    urls_to_process = await extract_urls_turbo(PROFILE_URL, SKIP_COUNT, TARGET_COUNT)
    
    if not urls_to_process:
        print("❌ No pins found!")
        return

    # Step 2: Extract Details (Title + Saves)
    print(f"\\n⏳ Step 2: Extracting Details (Parallel Mode: {CONCURRENT_TASKS} tasks)...\\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        semaphore = asyncio.Semaphore(CONCURRENT_TASKS)
        
        tasks = [get_pin_details_integrated(browser, url, semaphore, i) for i, url in enumerate(urls_to_process)]
        await asyncio.gather(*tasks)
        await browser.close()

    # Step 3: Save Results
    if results:
        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['url', 'title', 'saves', 'upload_date', 'timestamp'])
            writer.writeheader()
            writer.writerows(results)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\\n\\n{'='*70}")
        print(f"✅ SCRAPING COMPLETE!")
        print(f"📊 Total Pins: {len(results)}")
        print(f"⏱️  Total Time: {elapsed:.1f} seconds")
        print(f"📁 Output File: {OUTPUT_FILE}")
        print(f"{'='*70}\\n")

if __name__ == "__main__":
    asyncio.run(main())
