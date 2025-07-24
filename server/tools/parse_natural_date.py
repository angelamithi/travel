from datetime import datetime
import dateparser
from agents import Agent, Runner,function_tool

@function_tool
def parse_natural_date(text: str) -> str:
    """
    Parses natural language date expressions and returns YYYY-MM-DD format.
    If the date is ambiguous and has passed this year, it assumes next year.
    """

    now = datetime.now()
    parsed_date = dateparser.parse(text, settings={"PREFER_DATES_FROM": "future"})

    if not parsed_date:
        raise ValueError(f"Could not parse the date from '{text}'.")

    # Round to date only
    parsed_date = parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)

    # If it's in the past and looks like it's meant to be future, push to next year
    if parsed_date.date() < now.date():
        # Re-parse with an assumption of next year if not explicit
        parsed_date = dateparser.parse(
            f"{text} {now.year + 1}",
            settings={"PREFER_DATES_FROM": "future"}
        )
        if not parsed_date or parsed_date.date() < now.date():
            raise ValueError(f"The date '{text}' is in the past.")

    return parsed_date.strftime('%Y-%m-%d')
