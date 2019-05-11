import os
import re
from setuptools import setup

base_path = os.path.dirname(__file__)


def get_long_description():
    readme_md = os.path.join(base_path, "README.md")
    with open(readme_md) as f:
        return f.read()


with open(os.path.join(base_path, "cfscrape", "__init__.py")) as f:
    VERSION = re.compile(r'.*__version__ = "(.*?)"', re.S).match(f.read()).group(1)

setup(
    name="cfscrape",
    packages=["cfscrape"],
    version=VERSION,
    description='A simple Python module to bypass Cloudflare\'s anti-bot page. See https://github.com/Anorov/cloudflare-scrape for more information.',
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    author="Anorov",
    author_email="anorov.vorona@gmail.com",
    url="https://github.com/Anorov/cloudflare-scrape",
    keywords=["cloudflare", "scraping"],
    include_package_data=True,
    install_requires=["requests >= 2.0.0"],
)
