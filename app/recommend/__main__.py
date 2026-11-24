"""Package CLI entrypoints for recommendation checks."""

import sys

from app.recommend.engine import main as engine_main
from app.recommend.filter import main as filter_main


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "filter":
        filter_main()
        return
    engine_main()


if __name__ == "__main__":
    main()
