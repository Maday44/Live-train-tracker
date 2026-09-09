import argparse
import os

# Set debug before importing app so we get the logging right
os.environ["FLASK_DEBUG"] = "1"

from . import train_tracker  # noqa E402 needs to be after FLASK_DEBUG set


if "FLASK_RUN_HOST" in os.environ:
    train_tracker.run(host=os.environ["FLASK_RUN_HOST"])
else:
    train_tracker.run()
