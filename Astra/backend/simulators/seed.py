"""Seed the onboard Hub with the fictional demo crew."""

from hub.app import app
from .crew import seed_hub_store


def main():
    count = seed_hub_store(app.state.store)
    print(f"Seeded {count} fictional crew profiles.")


if __name__ == "__main__":
    main()
