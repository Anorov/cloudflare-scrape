from distutils.core import setup

setup(
  name = 'cloudflare-scrape',
  packages = ['cloudflare-scrape'],
  version = '0.2',
  description = 'A simple Python module to bypass Cloudflare\'s anti-bot page',
  author = 'Anorov',
  author_email = 'anorov.vorona@gmail.com',
  url = 'https://github.com/Anorov/cloudflare-scrape',
  download_url = 'https://github.com/Anorov/cloudflare-scrape/tarball/0.2',
  keywords = ['cloudflare', 'scraping'],
  py_modules = 'cfscrape'
)
