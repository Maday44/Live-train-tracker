import argparse
import os

# Set debug before importing app so logging initializes correctly
os.environ["FLASK_DEBUG"] = "1"

from train_tracker import app  # noqa E402


if "FLASK_RUN_HOST" in os.environ:
    app.run(host=os.environ["FLASK_RUN_HOST"], port=5000)
else:
    app.run(port=5000)