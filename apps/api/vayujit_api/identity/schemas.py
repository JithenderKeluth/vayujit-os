from pydantic import BaseModel, EmailStr, Field, model_validator


class SetupStatusResponse(BaseModel):
    owner_exists: bool = Field(serialization_alias="ownerExists")


class OwnerSetupRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    password_confirmation: str

    @model_validator(mode="after")
    def match(self) -> "OwnerSetupRequest":
        if self.password != self.password_confirmation:
            raise ValueError("Passwords do not match.")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthenticatedUserResponse(BaseModel):
    id: str
    full_name: str = Field(serialization_alias="fullName")
    email: str
    role: str
