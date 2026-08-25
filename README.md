# Web Mirror Detector

Web Mirror Detector is a desktop application written in Python for detecting
potential mirror, redirect and impersonation websites.

The application uses network information, HTTP redirects and visual
similarity to compare candidate websites with a reference website.

## Features

### Domain detection

- Generates domain permutations
- Supports multiple TLDs
- Supports numeric prefixes and suffixes
- Allows configurable numeric ranges

### Network analysis

- Checks domain availability
- Follows HTTP/HTTPS redirects
- Displays the final target URL
- Detects hostname
- Detects IP addresses
- Displays HTTP status code

### Visual comparison

- Captures screenshots of websites
- Compares screenshots using perceptual hashing
- Calculates visual similarity in percent
- Displays screenshots directly in the application

### Results

The application displays:

- Domain
- Type
- Final target URL
- Hostname
- IP addresses
- HTTP status code
- Similarity percentage
- Screenshot preview

### Export

- Exports results to Excel
- Includes domain, type, URL, hostname, IP addresses, HTTP status
  and similarity percentage

## Technologies

- Python
- PyQt5
- aiohttp
- Pyppeteer
- Pillow
- imagehash
- pandas
- openpyxl

## Project structure

The application is currently being refactored into separate modules.

```text
web-mirror-detector/
│
├── main.py
├── network.py
├── README.md
├── requirements.txt
├── WebMirrorDetector.spec
└── .gitignore