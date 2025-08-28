from fastapi import APIRouter
from fastapi.templating import Jinja2Templates
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi import Depends, HTTPException, status
from datetime import timedelta
from app.db import get_db
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models import User, Account, Payment
from sqlalchemy.orm import selectinload
from app import schemas
from app.utils import get_or_create_account, check_transaction, create_payment
from app.utils import verify_signature
from app.utils import authenticate_user, create_access_token
from app.utils import try_get_user
from fastapi import Form

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("Authorization")
    return response


@router.post("/login")
async def login(
    username: str = Form(...), 
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    user = await authenticate_user(db, username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) 
    
    access_token = create_access_token(
        data={"sub": username},
        expires_delta=timedelta(minutes=30)
    )
    
    response = RedirectResponse(url="/me", status_code=303)
    response.set_cookie(
        key="Authorization",
        value=access_token,
        httponly=True
    )
    return response


@router.get("/", response_class=HTMLResponse)
async def root(request: Request, db: AsyncSession = Depends(get_db)):
    user = await try_get_user(request, db)
    if user:
        return RedirectResponse(url="/me", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@router.get("/me", response_class=HTMLResponse)
async def read_me(request: Request, db: AsyncSession = Depends(get_db)):
    user = await try_get_user(request, db)
    if user.is_admin:
        return RedirectResponse(url="/admin/users", status_code=302)
    payments = await db.execute(select(Payment).where(Payment.user_id == user.id))
    accounts = await db.execute(select(Account).where(Account.user_id == user.id))
    return templates.TemplateResponse("me.html", {"request": request, "user": user, "payments": payments.scalars().all(), "accounts": accounts.scalars().all()})



@router.get('/admin/users', response_class=HTMLResponse)
async def admin_list_users(request: Request, db: AsyncSession = Depends(get_db)):
    users = await db.execute(select(User))
    admin = await try_get_user(request, db)
    return templates.TemplateResponse("admin_users.html", {"request": request, "users": users.scalars().all(), "admin": admin})


@router.get('/admin/user/{user_id}', response_class=HTMLResponse)
async def admin_show_user(user_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.accounts).selectinload(Account.payments)
        )
        .where(User.id == user_id)
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")


    return templates.TemplateResponse(
        "show_user.html",
        {
            "request": request,
            "user": user,
            "accounts": user.accounts
        }
    )


@router.get('/admin/users/create', response_class=HTMLResponse)
async def admin_create_user_page(request: Request):
    return templates.TemplateResponse("create_user.html", {"request": request})


@router.post('/admin/create/user')
async def admin_create_user(email : str = Form(...), full_name: str = Form(...), password: str = Form(...), is_admin: bool = Form(False),
                            db: AsyncSession = Depends(get_db)):
    hashed_password = pwd_context.hash(password)
    db_user = User(
        email=email,
        full_name=full_name,
        hashed_password=hashed_password,
        is_admin=is_admin
    )
    account = Account(balance=0.0, user=db_user)
    db.add(db_user)
    db.add(account)
    await db.commit()
    await db.refresh(db_user)
    return RedirectResponse(url="/admin/users", status_code=302)


@router.post('/admin/delete/user/{user_id}')
async def admin_delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await db.execute(select(User).where(User.id == user_id))
    account = await db.execute(select(Account).where(Account.user_id == user_id))
    payments = await db.execute(select(Payment).where(Payment.user_id == user_id))
    user = user.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    for acc in account.scalars().all():
        await db.delete(acc)
    for pay in payments.scalars().all():
        await db.delete(pay)
    await db.delete(user)
    await db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)


@router.get('/admin/users/{user_id}/edit', response_class=HTMLResponse)
async def admin_edit_user_page(user_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    user = await db.execute(select(User).where(User.id == user_id))
    user = user.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return templates.TemplateResponse("edit_user.html", {"request": request, "user": user})

@router.post('/admin/edit/user/{user_id}')
async def admin_edit_user(user_id: int, email : str = Form(...), full_name: str = Form(...), is_admin: bool = Form(False),
                            db: AsyncSession = Depends(get_db)):
    user = await db.execute(select(User).where(User.id == user_id))
    user = user.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.email = email
    user.full_name = full_name
    user.is_admin = is_admin
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return RedirectResponse(url="/admin/users", status_code=302)


@router.get('/admin/account/{account_id}/edit', response_class=HTMLResponse)
async def admin_edit_account_page(account_id: int, request: Request, db: AsyncSession = Depends(get_db)):
    account = await db.execute(select(Account).where(Account.id == account_id))
    account = account.scalars().first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return templates.TemplateResponse("edit_account.html", {"request": request, "account": account})


@router.post('/admin/edit/account/{account_id}')
async def admin_edit_account(account_id: int, balance : float = Form(...),
                            db: AsyncSession = Depends(get_db)):
    account = await db.execute(select(Account).where(Account.id == account_id))
    account = account.scalars().first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    account.balance = balance
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return RedirectResponse(url=f"/admin/user/{account.user_id}", status_code=302)



@router.post("/webhook/payment")
async def payment_webhook(data: schemas.PaymentWebhook, db: AsyncSession = Depends(get_db)):
    if not verify_signature(data):
        raise HTTPException(status_code=400, detail="Invalid signature")

    if await check_transaction(data.transaction_id, db):
        return {"status": "already_processed"}

    account = await get_or_create_account(data.user_id, data.account_id, db)
    await create_payment(data, account, db)
    return {"status": "success"}
