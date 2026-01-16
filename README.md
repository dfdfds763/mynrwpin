# Pinterest Turbo Scraper 🚀

High-performance Pinterest pin scraper jo 5,000-10,000 pins ko parallel processing ke saath extract karta hai.

## ✨ Features

- ⚡ **Fast Parallel Processing**: 30 concurrent tasks ke saath high-speed extraction
- 🎯 **Flexible Target**: 5k ya 10k pins set kar sakte hain
- 🛡️ **Smart Handling**: Agar profile me kam pins hain to jo bhi available hain wo sab fetch kar leta hai
- 📊 **CSV Export**: Results automatically CSV file me save hote hain
- 🔄 **Skip/Resume**: Pehle se scraped pins ko skip kar sakte hain
- 🤖 **GitHub Actions**: Apne PC ke bina automatically GitHub par run kar sakte hain

## 📋 Requirements

```bash
pip install playwright
python -m playwright install chromium
```

## 🚀 Local Usage

1. **Script ko configure karein**:
   ```python
   PROFILE_URL = "https://www.pinterest.com/your_profile/board_name/"
   TARGET_COUNT = 5000  # 5k ya 10k set kar sakte hain
   SKIP_COUNT = 0       # Kitne pins skip karne hain
   ```

2. **Script run karein**:
   ```bash
   python pinterest_scraper.py
   ```

3. **Results**:
   - Output file: `pinterest_turbo_data.csv`
   - Format: URL, Title, Upload Date

## 🤖 GitHub Actions Setup

### Step 1: Repository Setup
1. GitHub par naya repository banayein
2. Ye files upload karein:
   - `pinterest_scraper.py`
   - `.github/workflows/pinterest_scraper.yml`

### Step 2: Manual Run
1. GitHub repository me jayein
2. **Actions** tab par click karein
3. **Pinterest Scraper Automation** workflow select karein
4. **Run workflow** button par click karein
5. Workflow complete hone par **Artifacts** se CSV file download karein

### Step 3: Automatic Schedule (Optional)
Workflow file me schedule already set hai:
```yaml
schedule:
  - cron: '0 12 * * *'  # Har din 12:00 UTC
```

Agar schedule nahi chahiye to ye lines comment kar dein.

## ⚙️ Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `TARGET_COUNT` | 5000 | Kitne pins extract karne hain |
| `SKIP_COUNT` | 0 | Kitne pins skip karne hain |
| `CONCURRENT_TASKS` | 30 | Parallel processing tasks |
| `SCROLL_DELAY` | 2.0 | Scroll ke beech delay (seconds) |
| `NO_NEW_PINS_WAIT` | 5 | Naye pins na milne par kitne attempts |

## 📊 Output Format

CSV file me ye columns honge:
- **url**: Pin ka complete URL
- **title**: Pin ki title
- **upload_date**: Pin ka upload date

## 🔍 Smart Features

### 1. Incomplete Pin Handling
Agar profile me target se kam pins hain:
- Script automatically available pins fetch kar lega
- 5 attempts tak wait karega naye pins ke liye
- Jo bhi pins mile wo sab save ho jayenge

### 2. Error Handling
- Har pin ke liye 2 retries
- Error wale pins bhi CSV me save hote hain (title: "Error")
- Script kabhi crash nahi hoti

### 3. Progress Tracking
Real-time progress display:
```
⚡ Processed 450/5000 pins...
```

## 🛠️ Troubleshooting

### GitHub Actions me error aa rahi hai?
1. Repository settings me **Actions** enable hona chahiye
2. Workflow file `.github/workflows/` folder me honi chahiye
3. Python version 3.11 use ho rahi hai

### Local run me error?
1. Playwright install check karein: `python -m playwright install chromium`
2. Internet connection stable hona chahiye
3. Profile URL correct hona chahiye

## 📝 Notes

- **Headless Mode**: Default me browser visible nahi hota (HEADLESS=True)
- **Rate Limiting**: Script automatically delays use karti hai
- **Data Privacy**: Sirf public pins extract hote hain

## 🤝 Support

Issues ya questions ke liye GitHub Issues use karein.

---

**Happy Scraping! 🎉**
