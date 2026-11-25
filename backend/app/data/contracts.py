from pydantic import BaseModel, ConfigDict, Field


class DatasetImport(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=120)
    rows: list[dict] = Field(min_length=1, max_length=5000)
