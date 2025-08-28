from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta
from jose import jwt
from app.db import get_db
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models import User   
from fastapi import Request 
from fastapi import WebSocket
from app.models import Account
from app.models import Payment
from app.schemas import PaymentWebhook
from jose import JWTError, jwt
import hashlib
import os
import dotenv


SECRET_K = "supersecretkey"
ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")



def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

async def authenticate_user(db: AsyncSession, full_name: str, password: str):
    result = await db.execute(select(User).where(User.full_name == full_name))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_K, algorithm=ALGORITHM)



async def try_get_user(request: Request | WebSocket, db: AsyncSession = Depends(get_db)):
    try:
        token = request.cookies.get("Authorization")
        if not token:
            return None 
        payload = jwt.decode(token, SECRET_K, algorithms=[ALGORITHM])
        full_name = payload.get("sub")
        if full_name is None:
            return None
    except JWTError:
        return None

    result = await db.execute(select(User).where(User.full_name == full_name))
    return result.scalar_one_or_none()



async def get_or_create_account(user_id: int, account_id: int, db: AsyncSession = Depends(get_db)):
    user = await db.execute(select(User).where(User.id == user_id))
    if not user:
        raise Exception("User not found")
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalars().first()
    if not account:
        account = Account(id=account_id, user_id=user_id)
        db.add(account)
        await db.commit()
        await db.refresh(account)
    return account

async def check_transaction(transaction_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Payment).where(Payment.transaction_id == transaction_id))
    return result.scalars().first() is not None

async def create_payment(data: PaymentWebhook, account: Account, db: AsyncSession = Depends(get_db)):
    payment = Payment(
        transaction_id=data.transaction_id,
        account_id=account.id,
        user_id=data.user_id,
        amount=data.amount
    )
    account.balance += data.amount
    db.add(payment)
    db.add(account)
    await db.commit()

def verify_signature(data: PaymentWebhook):
    s = f"{data.account_id}{data.amount}{data.transaction_id}{data.user_id}{os.getenv('SECRET_KEY')}"
    print("Computed signature:", hashlib.sha256(s.encode()).hexdigest())
    print("Received signature:", data.signature)
    return hashlib.sha256(s.encode()).hexdigest() == data.signature

