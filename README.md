# Tour Kiosk Project

A comprehensive tour booking kiosk system for Airlie Beach, featuring automated web scraping, review aggregation, and a user-friendly interface for browsing and booking tours.

## Features

- **Automated Tour Scraping**: Scrapes tour information from multiple tour operator websites
- **Google Reviews Integration**: Collects ratings and testimonials from Google Reviews
- **Multi-Company Support**: Handles tours from various operators including:
  - Cruise Whitsundays
  - True Blue Sailing
  - Red Cat Adventures
  - ZigZag Whitsundays
  - ProSail, OzSail
  - Explore Group
  - Iconic Whitsunday
  - And more!

- **Media Management**: Downloads and processes tour images
- **Review System**: Aggregates reviews from multiple sources
- **Flask Web Application**: Clean, modern interface for browsing tours

## Installation

1. Clone this repository:
```bash
git clone <your-repo-url>
cd tour-kiosk-project
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables (create a `.env` file):
```env
# Add any API keys or configuration here
OPENAI_API_KEY=your_key_here  # if using AI features
SENDGRID_API_KEY=your_key_here  # if using email features
```

## Usage

### Running the Web Application
```bash
python app.py
```

### Scraping Tours
```bash
python scrape_tours.py
```

### Scraping Google Reviews
```bash
python scrape_google_reviews_complete.py
```

## Project Structure

- `app.py` - Main Flask web application
- `scrape_tours.py` - Tour data scraper
- `scrape_google_reviews_complete.py` - Google Reviews scraper
- `download_tour_media.py` - Media downloader
- `static/` - Static assets (CSS, images)
- `templates/` - HTML templates
- `tour_reviews/` - Scraped review data (JSON)
- `tours_*.csv` - Scraped tour data

## Requirements

- Python 3.7+
- Chrome/Chromium browser (for Selenium)
- See `requirements.txt` for Python packages

## Notes

- This scraper uses `undetected-chromedriver` to avoid detection
- Be respectful of rate limits when scraping
- Review data is stored in JSON format for easy integration
- The application is designed for kiosk deployment in tourist areas

## License

[Add your license here]

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

