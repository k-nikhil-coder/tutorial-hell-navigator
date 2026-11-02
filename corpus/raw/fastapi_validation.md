# FastAPI Validation and Error Handling

## Request Validation Errors

FastAPI uses Pydantic models to validate request data. When validation fails, FastAPI automatically returns a 422 Unprocessable Entity response.

The default response body looks like:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "password"],
      "msg": "Field required",
      "input": null
    }
  ]
}
```

### Custom Exception Handler for RequestValidationError

You can override the default behavior by registering a custom exception handler:

```python
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    # Optionally clean ctx that may contain non-serializable objects
    for err in errors:
        if "ctx" in err and err["ctx"]:
            err["ctx"] = {
                k: str(v) if isinstance(v, Exception) else v
                for k, v in err["ctx"].items()
            }
    # The original body is available as exc.body
    body = exc.body
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": errors, "body": body},
    )
```

Note: `await request.body()` can only be called once. Prefer `exc.body` when available.

## Pydantic v2 Field Validators

In Pydantic v2 the `@validator` decorator was replaced by `@field_validator`.

```python
from pydantic import BaseModel, field_validator, ValidationInfo

class ManagerSchema(BaseModel):
    operation_type: str
    background_hex_color: str | None = None

    @field_validator("background_hex_color", mode="before")
    @classmethod
    def validate_background_hex_color(cls, value, info: ValidationInfo):
        operation_type = info.data.get("operation_type")
        if operation_type == "UPDATE_BACKGROUND_COLOR" and not value:
            raise ValueError("background_hex_color is required for UPDATE_BACKGROUND_COLOR")
        return value
```

Important: when a field has a default of `None`, a `mode="before"` validator still receives the value (including the default) only if the field is present in the input data or you use a model-level validator.

## Discriminated Unions

When you have a large Union of schemas, validation errors become extremely verbose because Pydantic tries every member. Use a discriminator:

```python
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field

class SchemaA(BaseModel):
    type: Literal["A"]
    value_a: int

class SchemaB(BaseModel):
    type: Literal["B"]
    value_b: str

MasterRequest = Annotated[
    Union[SchemaA, SchemaB],
    Field(discriminator="type")
]
```

With a discriminator FastAPI returns a short, targeted error instead of enumerating every possible schema.

## Raising Validation Errors from Custom Validators

If a `@field_validator` or `@model_validator` raises `ValueError`, Pydantic converts it into a `ValidationError`. FastAPI turns any `ValidationError` into an HTTP 422 response automatically. You do not need to raise `HTTPException` inside validators for ordinary validation failures.

```python
from pydantic import BaseModel, model_validator, ValidationError

class BookUpdate(BaseModel):
    title: str | None = None
    author: str | None = None

    @model_validator(mode="after")
    def validate_pairs(self):
        errors = []
        if self.title and not self.author:
            errors.append({
                "type": "value_error",
                "loc": ("author",),
                "msg": "author is required when title is provided",
                "input": self.author,
            })
        if errors:
            raise ValidationError.from_exception_data("ModelValidationError", errors)
        return self
```

Using a single `model_validator` lets you collect multiple errors at once instead of short-circuiting after the first field_validator failure.
