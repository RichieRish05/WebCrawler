import multiprocessing
# Set multiprocessing start method to 'fork' for compatibility with spacetime on macOS
# This must be done before any imports that use multiprocessing
try:
    multiprocessing.set_start_method('fork')
except (RuntimeError, ValueError):
    # Start method already set or 'fork' not available, ignore
    pass

from configparser import ConfigParser
from argparse import ArgumentParser

from utils.server_registration import get_cache_server
from utils.config import Config
from crawler import Crawler
from scraper import generate_report


def main(config_file, restart):
    cparser = ConfigParser()
    cparser.read(config_file)
    config = Config(cparser)
    config.cache_server = get_cache_server(config, restart)
    crawler = Crawler(config, restart)
    crawler.start()
    generate_report()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--restart", action="store_true", default=False)
    parser.add_argument("--config_file", type=str, default="config.ini")
    args = parser.parse_args()
    main(args.config_file, args.restart)
