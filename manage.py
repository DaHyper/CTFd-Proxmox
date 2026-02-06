from dotenv import load_dotenv
from flask.cli import FlaskGroup

load_dotenv()

from CTFd import create_app

app = create_app()

cli = FlaskGroup(app)


if __name__ == "__main__":
    cli()
