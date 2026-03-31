from dataclasses import dataclass
from dataclasses import field


@dataclass(frozen=True)
class LoginCaseData:
    case_name: str
    username: str
    password: str
    expected_message: str
