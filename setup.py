from setuptools import setup

setup(
  name = 'cloudflare-scrape',
  packages = ['cfscrape'],
  version = '1.1',
  description = 'A simple Python module to bypass Cloudflare\'s anti-bot page',
  author = 'Anorov',
  author_email = 'anorov.vorona@gmail.com',
  url = 'https://github.com/Anorov/cloudflare-scrape',
  download_url = 'https://github.com/Anorov/cloudflare-scrape/tarball/1.0',
  keywords = ['cloudflare', 'scraping'],
  install_requires = ['PyExecJS >= 1.1.0', 'requests >= 2.0.0']
)
