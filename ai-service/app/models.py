from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    asset_tag: str = ""


class RcaRequest(BaseModel):
    asset_tag: str = Field(min_length=2, max_length=100)


class ProcessPathRequest(BaseModel):
    file_path: str
    document_id: str
    original_name: str
