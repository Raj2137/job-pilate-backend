"""Backend application entry point."""

import uvicorn

from app.main import app


def main() -> None:
    """Run the backend application."""
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
