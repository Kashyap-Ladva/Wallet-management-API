from decimal import Decimal
from typing import Annotated
from pydantic import PlainSerializer


def format_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


DecimalStr = Annotated[
    Decimal,
    PlainSerializer(format_decimal, return_type=str, when_used="json-unless-none"),
]
