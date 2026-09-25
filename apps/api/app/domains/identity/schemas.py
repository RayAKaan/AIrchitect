from pydantic import BaseModel, Field, field_validator

class RegisterRequest(BaseModel):
    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if value.count("@") != 1 or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("A valid email address is required")
        return value

    email: str
    name: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=12, max_length=128)
    organization_name: str = Field(min_length=1, max_length=160)

class LoginRequest(BaseModel):
    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if value.count("@") != 1 or "." not in value.rsplit("@", 1)[-1]:
            raise ValueError("A valid email address is required")
        return value

    email: str
    password: str

class UserOut(BaseModel):
    id: str
    email: str
    name: str

class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400
    user: UserOut
