"""
Pinterest Turbo Scraper - High Performance Parallel Edition
============================================================
Ye script 5,000-10,000 pins ko fast parallel processing ke saath 
extract karti hai. Agar profile me kam pins hain to jo bhi available 
hain wo sab fetch kar leti hai aur kuch seconds wait karne ke baad 
complete kar deti hai.

Requirements:
    pip install playwright
    python -m playwright install chromium

Usage:
    python pinterest_scraper.py
"""

import asyncio
import csv
import re
from playwright.async_api import async_playwright
from datetime import datetime
import json
import os
import sys

# --- CONFIGURATION ---
PROFILE_URL = "https://www.pinterest.com/purba43w/_created/"
OUTPUT_DIR = "output"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "pinterest_turbo_data.csv")

# BATCH SETTINGS
SKIP_COUNT = 0           # Kitne pins skip karne hain
TARGET_COUNT = 5000      # Kitne naye pins extract karne hain (5k ya 10k set kar sakte hain)

# PERFORMANCE SETTINGS (TURBO MODE)
CONCURRENT_TASKS = 30    # Aik saath 30 pins process karein
HEADLESS = True
MAX_RETRIES = 2
PAGE_LOAD_WAIT = 2.0     # Reduced wait for speed
SCROLL_DELAY = 2.0
MAX_SCROLL_ATTEMPTS = 2000
NO_NEW_PINS_WAIT = 5     # Agar naye pins nahi mile to kitne seconds wait karein
# ---------------------

# Global results
results = []
results_lock = asyncio.Lock()
processed_count = 0

async def get_pin_details_turbo(browser, url, semaphore, task_id):
    """
    High-speed parallel extraction for pin details
    """
    global processed_count
    async with semaphore:
        retry_count = 0
        while retry_count <= MAX_RETRIES:
            context = None
            try:
                # Har task ke liye optimized context
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    java_script_enabled=True
                )
                page = await context.new_page()
                
                # Speed optimization: Block images and CSS if only metadata is needed
                # (Optional: uncomment if you want even more speed)
                # await page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda route: route.abort())
                
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                
                # Title & Date extraction using fast JS evaluation
                data = await page.evaluate("""() => {
                    let title = "N/A";
                    let date = "N/A";
                    
                    // Title extraction
                    const h1 = document.querySelector('h1');
                    if (h1 && h1.innerText && !h1.innerText.startsWith('Pin on')) {
                        title = h1.innerText.trim();
                    } else {
                        const ogTitle = document.querySelector('meta[property="og:title"]');
                        if (ogTitle) title = ogTitle.content.replace(' - Pinterest', '').trim();
                    }
                    
                    // Date extraction from JSON-LD or meta
                    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                    for (let s of scripts) {
                        try {
                            const json = JSON.parse(s.text);
                            if (json.datePublished) { date = json.datePublished; break; }
                            if (json.uploadDate) { date = json.uploadDate; break; }
                        } catch(e) {}
                    }
                    
                    if (date === "N/A") {
                        const createdAt = document.body.innerHTML.match(/"created_at":\s*"([^"]+)"/);
                        if (createdAt) date = createdAt[1];
                    }
                    
                    return { title, date };
                }""")
                
                async with results_lock:
                    results.append({
                        'url': url,
                        'title': data['title'],
                        'upload_date': data['date']
                    })
                    processed_count += 1
                    if processed_count % 10 == 0:
                        print(f"   ⚡ Processed {processed_count} pins...", end='\r')
                
                return
                
            except Exception as e:
                retry_count += 1
                if retry_count > MAX_RETRIES:
                    async with results_lock:
                        results.append({'url': url, 'title': "Error", 'upload_date': "N/A"})
                        processed_count += 1
                else:
                    await asyncio.sleep(1)
            finally:
                if context: await context.close()

async def extract_urls_turbo(profile_url, skip, target):
    """
    Fast URL extraction from profile - agar target se kam pins hain to jo bhi available hain wo sab fetch karta hai
    """
    new_urls = []
    async with async_playwright() as p:
        print(f"\\n{'='*70}")
        print(f"🚀 PINTEREST TURBO SCRAPER - HIGH PERFORMANCE")
        print(f"{'='*70}")
        print(f"📊 Profile: {profile_url}")
        print(f"⏭️  Skip: {skip} | 🎯 Target: {target} | ⚡ Concurrency: {CONCURRENT_TASKS}")
        print(f"⏳ Step 1: Collecting URLs (Please wait)...\\n")
        
        browser = await p.chromium.launch(headless=HEADLESS)
        page = await browser.new_page()
        await page.goto(profile_url, wait_until="domcontentloaded")
        
        seen = set()
        all_urls = []
        scrolls = 0
        no_new_pins_count = 0
        previous_count = 0
        
        # Jab tak target achieve na ho ya phir pins khatam na ho jaye
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
                            if len(new_urls) >= target: 
                                break
            
            # Agar target achieve ho gaya to break
            if len(new_urls) >= target: 
                break
            
            # Check karo ke naye pins mil rahe hain ya nahi
            if len(new_urls) == previous_count:
                no_new_pins_count += 1
                print(f"   ⏸️  No new pins found (attempt {no_new_pins_count}/{NO_NEW_PINS_WAIT})...", end='\r')
                
                # Agar NO_NEW_PINS_WAIT attempts tak naye pins nahi mile to stop kar do
                if no_new_pins_count >= NO_NEW_PINS_WAIT:
                    print(f"\\n   ⚠️  No new pins after {NO_NEW_PINS_WAIT} attempts. Stopping with {len(new_urls)} pins.")
                    break
            else:
                no_new_pins_count = 0  # Reset counter agar naye pins mil gaye
            
            previous_count = len(new_urls)
            print(f"   🔍 Found {len(all_urls)} total pins... ({len(new_urls)} new)", end='\r')
            
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(SCROLL_DELAY)
            scrolls += 1
            
        await browser.close()
        
        # Final message
        if len(new_urls) < target:
            print(f"\\n\\n⚠️  Target was {target} pins, but only {len(new_urls)} pins available.")
            print(f"✅ Proceeding with {len(new_urls)} pins for processing.")
        else:
            print(f"\\n\\n✅ URL Collection Complete: {len(new_urls)} pins ready for processing.")
    
    return new_urls

async def main():
    start_time = datetime.now()
    
    # Ensure output directory exists
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"📁 Created directory: {OUTPUT_DIR}")

    # Step 1: Get URLs
    urls_to_process = await extract_urls_turbo(PROFILE_URL, SKIP_COUNT, TARGET_COUNT)
    
    if not urls_to_process:
        print("❌ No pins found!")
        return

    # Step 2: Parallel Processing
    print(f"\\n⏳ Step 2: Extracting Details (Parallel Mode: {CONCURRENT_TASKS} tasks)...\\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        semaphore = asyncio.Semaphore(CONCURRENT_TASKS)
        
        tasks = [get_pin_details_turbo(browser, url, semaphore, i) for i, url in enumerate(urls_to_process)]
        await asyncio.gather(*tasks)
        await browser.close()

    # Step 3: Save Results
    if results:
        file_exists = os.path.isfile(OUTPUT_FILE)
        with open(OUTPUT_FILE, 'a' if file_exists else 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['url', 'title', 'upload_date'])
            if not file_exists: writer.writeheader()
            writer.writerows(results)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\\n\\n{'='*70}")
        print(f"✅ TURBO SCRAPING COMPLETE!")
        print(f"📊 Total Pins Extracted: {len(results)}")
        print(f"⏱️  Total Time: {elapsed:.1f} seconds")
        print(f"🚀 Average Speed: {elapsed/len(results):.2f}s per pin")
        print(f"📁 Output File: {OUTPUT_FILE}")
        print(f"{'='*70}\\n")

if __name__ == "__main__":
    asyncio.run(main())
