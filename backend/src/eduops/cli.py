import argparse
import getpass
import sys
from typing import Literal, cast

import uvicorn

from eduops.config import Config, LLMConfig, load_config, save_config


def interactive_setup() -> None:
    """Prompt the user for LLM configuration on first run."""
    print("Welcome to eduops! It looks like this is your first run.")
    print("Let's set up your LLM configuration.\n")

    Provider = Literal["openai", "gemini", "openrouter", "custom"]
    valid_providers = ["openai", "gemini", "openrouter", "custom"]
    provider = ""
    while provider not in valid_providers:
        provider_input = (
            input(
                "Select an LLM provider [openai, gemini, openrouter, custom] (default: gemini): "
            )
            .strip()
            .lower()
        )
        if not provider_input:
            provider = "gemini"
        elif provider_input in valid_providers:
            provider = provider_input
        else:
            print(f"Invalid provider. Please choose from: {', '.join(valid_providers)}")

    api_key = ""
    while not api_key:
        api_key = getpass.getpass(f"Enter your {provider} API key: ").strip()
        if not api_key:
            print("API key is required.")

    default_model = "gemini-2.5-flash" if provider == "gemini" else "gpt-4o-mini"
    model = input(
        f"Enter the default model to use (default: {default_model}): "
    ).strip()
    if not model:
        model = default_model

    base_url = ""
    if provider == "custom":
        while not base_url:
            base_url = input("Enter the custom base URL: ").strip()
            if not base_url:
                print("Base URL is required for custom provider.")

    provider_literal = cast(Provider, provider)
    llm_config = LLMConfig(
        provider=provider_literal, api_key=api_key, model=model, base_url=base_url
    )
    config = Config(llm=llm_config)
    save_config(config)
    print("\nConfiguration saved successfully to ~/.eduops/config.toml!\n")


def main() -> int:
    """Entry point for the eduops CLI."""
    parser = argparse.ArgumentParser(description="eduops CLI")
    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Available commands"
    )

    start_parser = subparsers.add_parser("start", help="Start the eduops server")
    start_parser.add_argument(
        "--port",
        type=int,
        default=7337,
        help="Port to run the server on (default: 7337)",
    )

    args = parser.parse_args()

    if args.command == "start":
        config = load_config()
        if config is None:
            try:
                interactive_setup()
            except (KeyboardInterrupt, EOFError):
                print("\nSetup cancelled. Exiting.")
                return 1

        uvicorn.run("eduops.app:app", host="127.0.0.1", port=args.port)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
