from fastapi import FastAPI
from fastapi.security import HTTPBasic
from app.models import User
from app.models import Account
from app.models import Payment
from app.db import engine, Base
from app.db import get_db
from app.router import router as base_router
from passlib.context import CryptContext
from fastapi.responses import RedirectResponse
from app.utils import try_get_user
import asyncio
from fastapi import Request
import asyncpg


app = FastAPI()
security = HTTPBasic()

app.include_router(base_router)

async def wait_for_postgres():
    while True:
        try:
            conn = await asyncpg.connect(
                user="user",
                password="password",
                host="db",
                database="mydb"
            )
            await conn.close()
            print("Postgres is ready!")
            break
        except Exception:
            print("Waiting for Postgres...")
            await asyncio.sleep(1)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@app.on_event("startup")
async def startup():
    await wait_for_postgres()  

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async for session in get_db():
        user1 = User(email="user1@example.com", hashed_password=pwd_context.hash('123456'), full_name="Dark")
        admin = User(email="admin@example.com", hashed_password=pwd_context.hash('123456'), full_name="admin", is_admin=True)

        account1 = Account(balance=100.0, user=user1)
        account2 = Account(balance=250.5, user=user1)

        payment1 = Payment(account=account1, user_id=1, amount=25.0, transaction_id="5eae174f-7cd0-472c-bd36-35660f00132b")
        payment2 = Payment(account=account2, user_id=1, amount=50.0, transaction_id="7eae174f-7cd0-472c-bd36-35660f00132b")

        session.add_all([user1, account1, account2, payment1, payment2, admin])
        await session.commit()
        break

@app.middleware("http")
async def check_auth(request: Request, call_next):
    path = ["/login", "/favicon.ico"]

    if request.url.path in path:
        return await call_next(request)
    
    async for db in get_db():
        user = await try_get_user(request, db)
        if not user:
            return RedirectResponse('/login')
        break

    response = await call_next(request)
    return response


