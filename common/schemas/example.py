from pydantic import BaseModel, ConfigDict, Field


class Person(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    age: int = Field(ge=0)
