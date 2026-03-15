import argparse
import getpass
import sys
from typing import Literal, cast

import uvicorn

from eduops.config import Config, LLMConfig, load_config, save_config, get_config_path


def get_default_model(provider: str) -> str:
    """Return the default model string based on the provider."""
    if provider == "gemini":
        return "gemini-3-flash-preview"
    elif provider == "openrouter":
        return "openai/gpt-4o-mini"
    elif provider == "openai":
        return "gpt-4o-mini"
    return "gpt-4o-mini"


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

    default_model = get_default_model(provider)
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
    try:
        save_config(config)
    except OSError as e:
        print(f"\nError saving configuration to {get_config_path()}: {e}")
        print("Please check your file system permissions and try again.")
        sys.exit(1)
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
        config_path = get_config_path()
        if not config_path.exists():
            try:
                interactive_setup()
            except (KeyboardInterrupt, EOFError):
                print("\nSetup cancelled. Exiting.")
                return 1
        elif load_config() is None:
            print(
                "Existing config is invalid. Please fix ~/.eduops/config.toml and retry."
            )
            return 1

        uvicorn.run("eduops.app:app", host="127.0.0.1", port=args.port)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
