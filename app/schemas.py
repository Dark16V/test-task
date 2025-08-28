from pydantic import BaseModel
from pydantic import BaseModel

class PaymentWebhook(BaseModel):
    transaction_id: str
    account_id: int
    user_id: int
    amount: float
    signature: str

