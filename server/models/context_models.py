from dataclasses import dataclass

@dataclass
class UserInfo:
    user_id: str
    thread_id: str
    name: str = ""
    email: str = ""
    phone: str = ""
