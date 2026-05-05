import anthropic
import requests
from bs4 import BeautifulSoup
import json
import os


def validate_url(url):
    try:
        r = requests.get(url, timeout=10)
        return r.status_code == 200
    except:
        return False


def search_new_jobs():
    # Load joblist and SKILL.md
    # Check known URLs for status changes
    # Run web search for new roles
    # Filter against SKILL.md criteria
    # Return validated new roles
    pass


if __name__ == "__main__":
    search_new_jobs()
