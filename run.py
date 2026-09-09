import argparse
import os

# Set debug before importing app so we get the logging right
os.environ["FLASK_DEBUG"] = "1"

from sockets_to_room import app  # noqa E402 needs to be after FLASK_DEBUG set

p = argparse.ArgumentParser(description="Run leavers app in test mode")
p.add_argument("username", help="username to fake", nargs="?", default="Nobody")
args = p.parse_args()
app.config["TEST_CRSID"] = args.username

if "FLASK_RUN_HOST" in os.environ:
    app.run(host=os.environ["FLASK_RUN_HOST"])
else:
    app.run()
