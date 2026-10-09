SCENARIOS = {
    "health": {"method": "GET", "path": "/health"},
    "root": {"method": "GET", "path": "/"},
    "courses": {"method": "GET", "path": "/courses?page=1&page_size=50"},
    "readiness": {"method": "GET", "path": "/health/ready"},
    "notifications": {"method": "GET", "path": "/notifications?page=1&page_size=20"},
    "search": {"method": "GET", "path": "/ai-search?q=database"},
}

# Authenticated scenarios require --token and a safe test account.
# No credentials are stored in this file.
