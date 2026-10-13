import argparse
import sys
from pathlib import Path

from pydantic import AliasChoices, AnyHttpUrl, Field, PositiveInt, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    CliApp,
    CliSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

STDIO = "-"


class CliSettings(BaseSettings):
    """Create payloads on the caching service and read them back."""

    model_config = SettingsConfigDict(cli_hide_none_type=True)

    host: AnyHttpUrl = Field(
        "http://localhost:8000",
        validation_alias=AliasChoices("host", "h"),
        description="service base URL",
    )
    repeat: PositiveInt = Field(
        1, validation_alias=AliasChoices("repeat", "r"), description="number of iterations"
    )
    input: str | None = Field(
        None,
        validation_alias=AliasChoices("input", "i"),
        description=f'file with the JSON payload, "{STDIO}" for stdin',
    )
    json_input: str | None = Field(
        None, validation_alias=AliasChoices("json", "j"), description="JSON payload as a string"
    )
    output: str = Field(
        STDIO,
        validation_alias=AliasChoices("output", "o"),
        description=f'file for the results, "{STDIO}" for stdout',
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Only command line arguments count: an unrelated HOST or INPUT variable in the
        # environment must not change what the tool sends.
        return (init_settings,)

    @field_validator("input")
    @classmethod
    def input_file_exists(cls, value: str | None) -> str | None:
        if value is not None and value != STDIO and not Path(value).is_file():
            raise ValueError(f"file not found: {value}")
        return value

    @model_validator(mode="after")
    def single_payload_source(self) -> "CliSettings":
        if (self.input is None) == (self.json_input is None):
            raise ValueError("pass exactly one of --input or --json")
        return self


def parse_args(args: list[str] | None = None) -> CliSettings:
    # The spec gives -h to --host, so help is only available as --help.
    parser = argparse.ArgumentParser(
        prog="cache-cli", description=CliSettings.__doc__, add_help=False
    )
    parser.add_argument("--help", action="help", help="show this help message and exit")
    source = CliSettingsSource(CliSettings, root_parser=parser)
    return CliApp.run(
        CliSettings,
        cli_args=sys.argv[1:] if args is None else args,
        cli_settings_source=source,
    )
