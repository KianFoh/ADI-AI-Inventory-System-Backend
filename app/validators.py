from typing import Optional

def positive_int_validator(field_name: str = "Value"):
    def validator(v: int) -> int:
        if v <= 0:
            raise ValueError(f'{field_name} must be greater than 0')
        return v
    return validator

def positive_int_optional_validator(field_name: str = "Value"):
    def validator(v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError(f'{field_name} must be greater than 0')
        return v
    return validator

def non_negative_int_validator(field_name: str = "Value"):
    def validator(v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError(f'{field_name} cannot be negative')
        return v
    return validator

def non_empty_string_validator(field_name: str = "Value"):
    def validator(v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError(f'{field_name} cannot be empty')
        return v.strip().upper()
    return validator

def non_empty_string_preserve_case_validator(field_name: str = "Value"):
    def validator(v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError(f'{field_name} cannot be empty')
        return v.strip()
    return validator

def boolean_validator(field_name: str = "Value"):
    def validator(v: bool) -> bool:
        if not isinstance(v, bool):
            raise ValueError(f'{field_name} must be True or False')
        return v
    return validator

def storage_format_validator(prefix: str, field_name: str):
    def validator(v: str) -> str:
        if not v.startswith(prefix) or not v[1:].isdigit():
            raise ValueError(f'{field_name} must be in format {prefix}1, {prefix}2, {prefix}3, etc.')
        return v.upper()
    return validator

def storage_format_optional_validator(prefix: str, field_name: str):
    def validator(v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.startswith(prefix) or not v[1:].isdigit():
                raise ValueError(f'{field_name} must be in format {prefix}1, {prefix}2, {prefix}3, etc.')
            return v.upper()
        return v
    return validator

def bounded_int_validator(min_val: int, max_val: int, field_name: str = "Value"):
    def validator(v: int) -> int:
        if v < min_val:
            raise ValueError(f'{field_name} must be at least {min_val}')
        if v > max_val:
            raise ValueError(f'{field_name} cannot exceed {max_val}')
        return v
    return validator

def bounded_int_optional_validator(min_val: int, max_val: int, field_name: str = "Value"):
    def validator(v: Optional[int]) -> Optional[int]:
        if v is not None:
            if v < min_val:
                raise ValueError(f'{field_name} must be at least {min_val}')
            if v > max_val:
                raise ValueError(f'{field_name} cannot exceed {max_val}')
        return v
    return validator

def string_length_validator(max_length: int, field_name: str = "Value"):
    def validator(v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError(f'{field_name} cannot be empty')
        if len(v) > max_length:
            raise ValueError(f'{field_name} cannot exceed {max_length} characters')
        return v.strip().upper()
    return validator

def positive_float_optional_validator(field_name: str = "Value"):
    def validator(v: Optional[float]) -> Optional[float]:
        if v is not None and v <= 0:
            raise ValueError(f'{field_name} must be positive')
        return v
    return validator