"""First delivery milestone: authenticated site, progress, and todo API."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response, UploadFile, File, Header
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine, event, select, func, or_
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
engine = create_engine(os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'app.db'}"), connect_args={"check_same_thread": False})

@event.listens_for(engine, "connect")
def sqlite_setup(connection, _):
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()

SessionLocal = sessionmaker(engine, expire_on_commit=False)
def now(): return datetime.now(timezone.utc).replace(tzinfo=None)
def uid(): return str(uuid4())

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default="user")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
class LoginSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
class Site(Base):
    __tablename__ = "sites"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String, index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String, default="未开始")
    region: Mapped[str] = mapped_column(String, default="")
    country: Mapped[str] = mapped_column(String, default="")
    city: Mapped[str] = mapped_column(String, default="")
    operator: Mapped[str] = mapped_column(String, default="")
    remark: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
class Progress(Base):
    __tablename__ = "progress"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    issue: Mapped[str] = mapped_column(Text, default="")
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    void: Mapped[bool] = mapped_column(Boolean, default=False)
class Todo(Base):
    __tablename__ = "todos"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    progress_id: Mapped[str | None] = mapped_column(ForeignKey("progress.id"), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    due_date: Mapped[str | None] = mapped_column(String, nullable=True)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
class Attachment(Base):
    __tablename__ = "attachments"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    size: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
class Star(Base):
    __tablename__ = "stars"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), primary_key=True)
class FieldDefinition(Base):
    __tablename__ = "field_definitions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String, unique=True)
    kind: Mapped[str] = mapped_column(String, default="text")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
class FieldValue(Base):
    __tablename__ = "field_values"
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), primary_key=True)
    field_id: Mapped[str] = mapped_column(ForeignKey("field_definitions.id"), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
class Contact(Base):
    __tablename__ = "contacts"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    name: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default="")
    employee_no: Mapped[str] = mapped_column(String, default="")
    remark: Mapped[str] = mapped_column(Text, default="")
class ChatGroup(Base):
    __tablename__ = "chat_groups"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    group_id: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    remark: Mapped[str] = mapped_column(Text, default="")
class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String, unique=True)
    color: Mapped[str] = mapped_column(String, default="#6354b8")
class SiteTag(Base):
    __tablename__ = "site_tags"
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), primary_key=True)
    tag_id: Mapped[str] = mapped_column(ForeignKey("tags.id"), primary_key=True)
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String)
    site_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
class ApiToken(Base):
    __tablename__ = "api_tokens"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String)
    token_hash: Mapped[str] = mapped_column(String, unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
class TrashedAttachment(Base):
    __tablename__ = "trashed_attachments"
    attachment_id: Mapped[str] = mapped_column(ForeignKey("attachments.id"), primary_key=True)
    deleted_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    deleted_at: Mapped[datetime] = mapped_column(DateTime, default=now)
class SiteStatus(Base):
    __tablename__ = "site_statuses"
    name: Mapped[str] = mapped_column(String, primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

def audit(session, user, action, site_id=None):
    session.add(AuditLog(actor_id=user.id, action=action, site_id=site_id))

def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600000).hex()
    return f"{salt}${digest}"
def verify_password(password, value):
    salt, expected = value.split("$", 1)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600000).hex()
    return hmac.compare_digest(actual, expected)
def db():
    with SessionLocal() as session: yield session
def current_user(session: Session = Depends(db), session_token: str | None = Cookie(default=None), authorization: str | None = Header(default=None)):
    if authorization:
        if not authorization.startswith("Bearer "): raise HTTPException(401, "认证方式无效")
        digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
        api_token = session.scalar(select(ApiToken).where(ApiToken.token_hash == digest, ApiToken.active == True))
        user = session.get(User, api_token.user_id) if api_token else None
        if not user or not user.active: raise HTTPException(401, "令牌无效")
        return user
    token = hashlib.sha256((session_token or "").encode()).hexdigest()
    login = session.get(LoginSession, token)
    user = session.get(User, login.user_id) if login else None
    if not user or not user.active or login.created_at < now() - timedelta(days=1): raise HTTPException(401, "请先登录")
    return user
def get_site(session, site_id, user, write=False):
    site = session.get(Site, site_id)
    if not site: raise HTTPException(404, "局点不存在")
    if write and user.role != "admin" and site.owner_id != user.id: raise HTTPException(403, "只有负责人或管理员可以修改")
    return site
def valid_owner(session, owner_id):
    user = session.get(User, owner_id)
    if not user or not user.active: raise HTTPException(422, "负责人不存在或已停用")
def serialize_site(session, site):
    latest = session.scalar(select(Progress).where(Progress.site_id == site.id, Progress.void == False).order_by(Progress.occurred_at.desc(), Progress.created_at.desc(), Progress.id.desc()).limit(1))
    tags = session.scalars(select(Tag).join(SiteTag, Tag.id == SiteTag.tag_id).where(SiteTag.site_id == site.id)).all()
    return {"id": site.id, "name": site.name, "owner_id": site.owner_id, "status": site.status, "region": site.region, "country": site.country, "city": site.city, "operator": site.operator, "remark": site.remark, "version": site.version, "archived": site.archived, "tags": [{"id": t.id, "name": t.name, "color": t.color} for t in tags], "latest_progress": {"id": latest.id, "content": latest.content, "occurred_at": latest.occurred_at} if latest else None}

class Credentials(BaseModel):
    username: str
    password: str
class UserInput(Credentials):
    name: str
    role: str = "user"
class SiteInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    owner_id: str
    status: str = "未开始"
    region: str = ""
    country: str = ""
    city: str = ""
    operator: str = ""
    remark: str = ""
class SiteUpdate(SiteInput):
    version: int
class TodoInput(BaseModel):
    content: str = Field(min_length=1)
    due_date: str | None = None
class ProgressInput(BaseModel):
    content: str = Field(min_length=1)
    issue: str = ""
    occurred_at: datetime
    todos: list[TodoInput] = []

app = FastAPI(title="局点交付管理 API")
@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    username, password = os.getenv("ADMIN_USERNAME"), os.getenv("ADMIN_PASSWORD")
    with SessionLocal() as session:
        if not session.scalar(select(SiteStatus.name)):
            session.add_all([SiteStatus(name=n, sort_order=i) for i,n in enumerate(["未开始","进行中","等待外部","存在风险","待验收","已完成","暂停"])])
            for name in session.scalars(select(Site.status).distinct()):
                if name not in {"未开始","进行中","等待外部","存在风险","待验收","已完成","暂停"}: session.add(SiteStatus(name=name))
        if not session.scalar(select(User).where(User.role == "admin")) and username and password:
            session.add(User(username=username, name="管理员", password_hash=hash_password(password), role="admin"))
        session.commit()

@app.post("/api/v1/auth/login")
def login(body: Credentials, response: Response, session: Session = Depends(db)):
    user = session.scalar(select(User).where(User.username == body.username))
    if not user or not user.active or not verify_password(body.password, user.password_hash): raise HTTPException(401, "账号或密码错误")
    token = secrets.token_urlsafe(32)
    session.add(LoginSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id)); audit(session,user,"用户登录"); session.commit()
    response.set_cookie("session_token", token, httponly=True, samesite="strict", max_age=86400)
    return {"id": user.id, "name": user.name, "role": user.role}
@app.post("/api/v1/auth/logout")
def logout(response: Response, session_token: str | None = Cookie(default=None), session: Session = Depends(db)):
    login_session = session.get(LoginSession, hashlib.sha256((session_token or "").encode()).hexdigest())
    if login_session: session.delete(login_session); session.commit()
    response.delete_cookie("session_token"); return {"ok": True}
@app.get("/api/v1/auth/me")
def me(user: User = Depends(current_user)): return {"id": user.id, "name": user.name, "role": user.role}
@app.get("/api/v1/users")
def users(user: User = Depends(current_user), session: Session = Depends(db)):
    return [{"id": u.id, "name": u.name, "username": u.username, "role": u.role} for u in session.scalars(select(User).where(User.active == True))]
@app.post("/api/v1/users", status_code=201)
def create_user(body: UserInput, user: User = Depends(current_user), session: Session = Depends(db)):
    if user.role != "admin": raise HTTPException(403, "需要管理员权限")
    if body.role != "user": raise HTTPException(422, "只能创建普通用户")
    if session.scalar(select(User).where(User.username == body.username)): raise HTTPException(409, "账号已存在")
    new = User(username=body.username, name=body.name, password_hash=hash_password(body.password), role=body.role)
    session.add(new); audit(session,user,"创建用户"); session.commit(); return {"id": new.id, "name": new.name}
@app.get("/api/v1/sites")
def list_sites(q: str = "", page: int = 1, page_size: int = 20, owner_id: str = "", region: str = "", country: str = "", operator: str = "", status: str = "", tag_id: str = "", user: User = Depends(current_user), session: Session = Depends(db)):
    page, page_size = max(1, page), min(100, max(1, page_size))
    query = select(Site).where(Site.archived == False)
    if q:
        query = query.where(or_(Site.name.contains(q), Site.country.contains(q), Site.city.contains(q), Site.operator.contains(q), Site.region.contains(q), Site.id.in_(select(Progress.site_id).where(Progress.content.contains(q), Progress.void == False)), Site.id.in_(select(Contact.site_id).where(Contact.name.contains(q))), Site.id.in_(select(ChatGroup.site_id).where(ChatGroup.name.contains(q))), Site.id.in_(select(Attachment.site_id).where(Attachment.name.contains(q))), Site.id.in_(select(FieldValue.site_id).where(FieldValue.value.contains(q)))))
    for col,value in [(Site.owner_id,owner_id),(Site.region,region),(Site.country,country),(Site.operator,operator),(Site.status,status)]:
        if value: query = query.where(col == value)
    if tag_id: query = query.where(Site.id.in_(select(SiteTag.site_id).where(SiteTag.tag_id == tag_id)))
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    records = session.scalars(query.order_by(Site.name,Site.id).offset((page-1)*page_size).limit(page_size)).all()
    return {"total": total, "page":page, "page_size":page_size, "items": [serialize_site(session, s) for s in records]}
@app.post("/api/v1/sites", status_code=201)
def create_site(body: SiteInput, user: User = Depends(current_user), session: Session = Depends(db)):
    valid_owner(session, body.owner_id)
    if not session.get(SiteStatus, body.status): raise HTTPException(422,"状态不存在")
    site = Site(**body.model_dump()); session.add(site); session.flush(); audit(session, user, "创建局点", site.id); session.commit(); return serialize_site(session, site)
@app.get("/api/v1/sites/{site_id}")
def read_site(site_id: str, user: User = Depends(current_user), session: Session = Depends(db)):
    return serialize_site(session, get_site(session, site_id, user))
@app.put("/api/v1/sites/{site_id}")
def update_site(site_id: str, body: SiteUpdate, user: User = Depends(current_user), session: Session = Depends(db)):
    from sqlalchemy import update
    get_site(session, site_id, user, True); valid_owner(session, body.owner_id)
    if not session.get(SiteStatus, body.status): raise HTTPException(422,"状态不存在")
    values = body.model_dump(exclude={"version"}); values.update(version=body.version+1, updated_at=now())
    result = session.execute(update(Site).where(Site.id == site_id, Site.version == body.version).values(**values))
    if result.rowcount != 1: session.rollback(); raise HTTPException(409, "局点已被修改，请刷新后重试")
    audit(session, user, "修改局点", site_id); session.commit(); session.expire_all(); return serialize_site(session, session.get(Site, site_id))
@app.post("/api/v1/sites/{site_id}/progress", status_code=201)
def add_progress(site_id: str, body: ProgressInput, user: User = Depends(current_user), session: Session = Depends(db)):
    site = get_site(session, site_id, user, True)
    occurred = body.occurred_at
    if occurred.tzinfo: occurred = occurred.astimezone(timezone.utc).replace(tzinfo=None)
    p = Progress(site_id=site_id, content=body.content, issue=body.issue, occurred_at=occurred, created_by=user.id)
    session.add(p); session.flush()
    for todo in body.todos: session.add(Todo(site_id=site_id, progress_id=p.id, **todo.model_dump()))
    site.updated_at = now(); audit(session, user, "新增进展", site_id); session.commit(); return {"id": p.id, "site": serialize_site(session, site)}
@app.get("/api/v1/sites/{site_id}/progress")
def progress_list(site_id: str, user: User = Depends(current_user), session: Session = Depends(db)):
    get_site(session, site_id, user)
    return [{"id": p.id, "content": p.content, "occurred_at": p.occurred_at, "created_by": p.created_by} for p in session.scalars(select(Progress).where(Progress.site_id == site_id, Progress.void == False).order_by(Progress.occurred_at.desc(), Progress.created_at.desc(), Progress.id.desc()))]
@app.get("/api/v1/sites/{site_id}/todos")
def todo_list(site_id: str, user: User = Depends(current_user), session: Session = Depends(db)):
    get_site(session, site_id, user)
    return [{"id": t.id, "content": t.content, "due_date": t.due_date, "done": t.done} for t in session.scalars(select(Todo).where(Todo.site_id == site_id))]
@app.post("/api/v1/sites/{site_id}/todos", status_code=201)
def add_todo(site_id: str, body: TodoInput, user: User = Depends(current_user), session: Session = Depends(db)):
    get_site(session, site_id, user, True); todo = Todo(site_id=site_id, **body.model_dump()); session.add(todo); audit(session,user,"创建待办",site_id); session.commit(); return {"id": todo.id}

@app.post("/api/v1/progress/{progress_id}/void")
def void_progress(progress_id: str, user: User = Depends(current_user), session: Session = Depends(db)):
    progress = session.get(Progress, progress_id)
    if not progress: raise HTTPException(404, "进展不存在")
    get_site(session, progress.site_id, user, True); progress.void = True; audit(session, user, "作废进展", progress.site_id); session.commit(); return {"ok": True}

@app.put("/api/v1/progress/{progress_id}")
def edit_progress(progress_id: str, body: ProgressInput, user: User = Depends(current_user), session: Session = Depends(db)):
    progress = session.get(Progress, progress_id)
    if not progress or progress.void: raise HTTPException(404, "进展不存在")
    get_site(session, progress.site_id, user, True)
    occurred = body.occurred_at
    if occurred.tzinfo: occurred = occurred.astimezone(timezone.utc).replace(tzinfo=None)
    progress.content = body.content; progress.issue = body.issue; progress.occurred_at = occurred
    audit(session, user, "修改进展", progress.site_id); session.commit(); return {"ok": True}
@app.post("/api/v1/todos/{todo_id}/complete")
def complete_todo(todo_id: str, user: User = Depends(current_user), session: Session = Depends(db)):
    todo = session.get(Todo, todo_id)
    if not todo: raise HTTPException(404, "待办不存在")
    get_site(session, todo.site_id, user, True); todo.done = True; audit(session, user, "完成待办", todo.site_id); session.commit(); return {"ok": True}

@app.post("/api/v1/sites/{site_id}/archive")
def archive_site(site_id: str, user: User = Depends(current_user), session: Session = Depends(db)):
    site = get_site(session, site_id, user, True); site.archived = True; audit(session,user,"归档局点",site_id); session.commit(); return {"ok": True}

@app.post("/api/v1/sites/{site_id}/star")
def toggle_star(site_id: str, user: User = Depends(current_user), session: Session = Depends(db)):
    get_site(session, site_id, user); star = session.get(Star, (user.id, site_id))
    if star: session.delete(star)
    else: session.add(Star(user_id=user.id, site_id=site_id))
    session.commit(); return {"starred": star is None}

@app.get("/api/v1/stars")
def list_stars(user: User = Depends(current_user), session: Session = Depends(db)):
    return [s.site_id for s in session.scalars(select(Star).where(Star.user_id == user.id))]

@app.post("/api/v1/sites/{site_id}/attachments", status_code=201)
def upload_attachment(site_id: str, file: UploadFile = File(...), user: User = Depends(current_user), session: Session = Depends(db)):
    get_site(session, site_id, user, True)
    attachment_id = uid(); folder = DATA_DIR / "uploads"; folder.mkdir(parents=True, exist_ok=True)
    path = folder / attachment_id; size = 0
    try:
        with path.open("xb") as out:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > 100 * 1024 * 1024: raise HTTPException(413, "文件不能超过 100 MB")
                out.write(chunk)
        record = Attachment(id=attachment_id, site_id=site_id, name=Path(file.filename or "附件").name, size=size, created_by=user.id)
        session.add(record); audit(session,user,"上传附件",site_id); session.commit()
    except Exception:
        path.unlink(missing_ok=True); raise
    return {"id": attachment_id, "name": record.name, "size": size}

@app.get("/api/v1/sites/{site_id}/attachments")
def attachments(site_id: str, user: User = Depends(current_user), session: Session = Depends(db)):
    get_site(session, site_id, user)
    return [{"id": a.id, "name": a.name, "size": a.size} for a in session.scalars(select(Attachment).where(Attachment.site_id == site_id, ~Attachment.id.in_(select(TrashedAttachment.attachment_id))))]

@app.get("/api/v1/attachments/{attachment_id}/download")
def download(attachment_id: str, user: User = Depends(current_user), session: Session = Depends(db)):
    attachment = session.get(Attachment, attachment_id)
    if not attachment or session.get(TrashedAttachment, attachment_id): raise HTTPException(404, "附件不存在")
    get_site(session, attachment.site_id, user)
    path = DATA_DIR / "uploads" / attachment.id
    if not path.is_file(): raise HTTPException(404, "文件不存在")
    return FileResponse(path, filename=attachment.name, media_type="application/octet-stream")

@app.delete("/api/v1/attachments/{attachment_id}")
def trash_attachment(attachment_id: str, user: User = Depends(current_user), session: Session = Depends(db)):
    attachment = session.get(Attachment, attachment_id)
    if not attachment: raise HTTPException(404, "附件不存在")
    get_site(session, attachment.site_id, user, True)
    if not session.get(TrashedAttachment, attachment_id):
        session.add(TrashedAttachment(attachment_id=attachment_id, deleted_by=user.id)); audit(session,user,"删除附件",attachment.site_id); session.commit()
    return {"ok":True}
@app.get("/api/v1/trash/attachments")
def list_trashed(user: User = Depends(current_user), session: Session = Depends(db)):
    if user.role != "admin": raise HTTPException(403, "需要管理员权限")
    return [{"id":a.id,"name":a.name,"site_id":a.site_id,"deleted_at":t.deleted_at} for a,t in session.execute(select(Attachment,TrashedAttachment).join(TrashedAttachment,TrashedAttachment.attachment_id==Attachment.id))]
@app.post("/api/v1/trash/attachments/{attachment_id}/restore")
def restore_attachment(attachment_id: str, user: User = Depends(current_user), session: Session = Depends(db)):
    if user.role != "admin": raise HTTPException(403, "需要管理员权限")
    item=session.get(TrashedAttachment,attachment_id); attachment=session.get(Attachment,attachment_id)
    if not item or not attachment: raise HTTPException(404,"附件不在回收站")
    session.delete(item); audit(session,user,"恢复附件",attachment.site_id); session.commit(); return {"ok":True}

class FieldInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: str = "text"
class ValueInput(BaseModel):
    value: str

@app.get("/api/v1/fields")
def fields(user: User = Depends(current_user), session: Session = Depends(db)):
    return [{"id": f.id, "name": f.name, "kind": f.kind} for f in session.scalars(select(FieldDefinition))]
@app.post("/api/v1/fields", status_code=201)
def create_field(body: FieldInput, user: User = Depends(current_user), session: Session = Depends(db)):
    if body.kind not in {"text", "number", "date", "boolean"}: raise HTTPException(422, "不支持的字段类型")
    if session.scalar(select(FieldDefinition).where(FieldDefinition.name == body.name)): raise HTTPException(409, "字段已存在")
    f = FieldDefinition(**body.model_dump(), created_by=user.id); session.add(f); audit(session,user,"创建自定义字段"); session.commit(); return {"id": f.id, "name": f.name, "kind": f.kind}

class TagInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str = "#6354b8"
@app.get("/api/v1/tags")
def tags(user: User = Depends(current_user), session: Session = Depends(db)):
    return [{"id": t.id, "name": t.name, "color": t.color} for t in session.scalars(select(Tag).order_by(Tag.name))]
@app.post("/api/v1/tags", status_code=201)
def create_tag(body: TagInput, user: User = Depends(current_user), session: Session = Depends(db)):
    if session.scalar(select(Tag).where(Tag.name == body.name)): raise HTTPException(409, "标签已存在")
    t=Tag(**body.model_dump()); session.add(t); audit(session,user,"创建标签"); session.commit(); return {"id":t.id,"name":t.name,"color":t.color}
@app.post("/api/v1/sites/{site_id}/tags/{tag_id}")
def add_tag(site_id: str, tag_id: str, user: User = Depends(current_user), session: Session = Depends(db)):
    get_site(session, site_id, user, True)
    if not session.get(Tag, tag_id): raise HTTPException(404, "标签不存在")
    if not session.get(SiteTag, (site_id, tag_id)): session.add(SiteTag(site_id=site_id, tag_id=tag_id)); audit(session,user,"添加标签",site_id); session.commit()
    return {"ok":True}
@app.delete("/api/v1/sites/{site_id}/tags/{tag_id}")
def remove_tag(site_id: str, tag_id: str, user: User = Depends(current_user), session: Session = Depends(db)):
    get_site(session, site_id, user, True); link=session.get(SiteTag, (site_id, tag_id))
    if link: session.delete(link); audit(session,user,"移除标签",site_id); session.commit()
    return {"ok":True}
@app.get("/api/v1/sites/{site_id}/fields")
def field_values(site_id: str, user: User = Depends(current_user), session: Session = Depends(db)):
    get_site(session, site_id, user); return {v.field_id: v.value for v in session.scalars(select(FieldValue).where(FieldValue.site_id == site_id))}
@app.put("/api/v1/sites/{site_id}/fields/{field_id}")
def set_field(site_id: str, field_id: str, body: ValueInput, user: User = Depends(current_user), session: Session = Depends(db)):
    get_site(session, site_id, user, True)
    if not session.get(FieldDefinition, field_id): raise HTTPException(404, "字段不存在")
    v = session.get(FieldValue, (site_id, field_id))
    if v: v.value = body.value
    else: session.add(FieldValue(site_id=site_id, field_id=field_id, value=body.value))
    audit(session,user,"修改自定义字段值",site_id); session.commit(); return {"ok": True}

class ContactInput(BaseModel):
    name: str = Field(min_length=1)
    role: str = ""
    employee_no: str = ""
    remark: str = ""
class GroupInput(BaseModel):
    group_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    remark: str = ""
@app.get("/api/v1/sites/{site_id}/contacts")
def contacts(site_id: str, user: User = Depends(current_user), session: Session = Depends(db)):
    get_site(session, site_id, user)
    return [{"id":c.id,"name":c.name,"role":c.role,"employee_no":c.employee_no,"remark":c.remark} for c in session.scalars(select(Contact).where(Contact.site_id == site_id))]
@app.post("/api/v1/sites/{site_id}/contacts", status_code=201)
def add_contact(site_id: str, body: ContactInput, user: User = Depends(current_user), session: Session = Depends(db)):
    get_site(session, site_id, user, True); c=Contact(site_id=site_id, **body.model_dump()); session.add(c); audit(session,user,"添加联系人",site_id); session.commit(); return {"id":c.id}
@app.get("/api/v1/sites/{site_id}/groups")
def groups(site_id: str, user: User = Depends(current_user), session: Session = Depends(db)):
    get_site(session, site_id, user)
    return [{"id":g.id,"name":g.name,"group_id":g.group_id,"remark":g.remark} for g in session.scalars(select(ChatGroup).where(ChatGroup.site_id == site_id))]
@app.post("/api/v1/sites/{site_id}/groups", status_code=201)
def add_group(site_id: str, body: GroupInput, user: User = Depends(current_user), session: Session = Depends(db)):
    get_site(session, site_id, user, True); g=ChatGroup(site_id=site_id, **body.model_dump()); session.add(g); audit(session,user,"添加群聊",site_id); session.commit(); return {"id":g.id}

@app.get("/api/v1/audit-logs")
def audit_logs(user: User = Depends(current_user), session: Session = Depends(db)):
    if user.role != "admin": raise HTTPException(403, "需要管理员权限")
    return [{"action": a.action, "site_id": a.site_id, "actor": session.get(User, a.actor_id).name, "created_at": a.created_at} for a in session.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200))]

@app.get("/api/v1/reports/progress")
def progress_report(start: str, end: str, owner_id: str = "", user: User = Depends(current_user), session: Session = Depends(db)):
    try:
        start_date = datetime.fromisoformat(start); end_date = datetime.fromisoformat(end) + timedelta(days=1)
    except ValueError: raise HTTPException(422, "日期格式应为 YYYY-MM-DD")
    query = select(Progress, Site).join(Site, Site.id == Progress.site_id).where(Progress.void == False, Progress.occurred_at >= start_date, Progress.occurred_at < end_date)
    if owner_id: query = query.where(Progress.created_by == owner_id)
    return [{"site": s.name, "country": s.country, "occurred_at": p.occurred_at, "content": p.content, "issue": p.issue, "author": session.get(User, p.created_by).name} for p,s in session.execute(query.order_by(Progress.occurred_at.desc()))]

@app.get("/api/v1/reports/progress/export")
def export_progress(start: str, end: str, owner_id: str = "", user: User = Depends(current_user), session: Session = Depends(db)):
    import io
    from openpyxl import Workbook
    rows = progress_report(start, end, owner_id, user, session)
    output = io.BytesIO(); book=Workbook(); sheet=book.active; sheet.title="工作进展"; sheet.append(["局点", "国家", "事件时间", "进展", "问题", "记录人"])
    for row in rows:
        sheet.append(["'"+str(row[key]) if str(row[key]).lstrip().startswith(('=','+','-','@')) else str(row[key]) for key in ("site", "country", "occurred_at", "content", "issue", "author")])
    sheet.freeze_panes="A2"; sheet.auto_filter.ref=sheet.dimensions
    for col in "ABCDEF": sheet.column_dimensions[col].width=24 if col not in "DE" else 45
    book.save(output); output.seek(0)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition":"attachment; filename=progress-report.xlsx"})

class TokenInput(BaseModel):
    name: str = Field(min_length=1,max_length=100)
    user_id: str
@app.post("/api/v1/admin/tokens", status_code=201)
def create_token(body: TokenInput, user: User = Depends(current_user), session: Session = Depends(db)):
    if user.role != "admin": raise HTTPException(403,"需要管理员权限")
    valid_owner(session,body.user_id); raw=secrets.token_urlsafe(40)
    token=ApiToken(name=body.name,user_id=body.user_id,token_hash=hashlib.sha256(raw.encode()).hexdigest()); session.add(token); audit(session,user,"创建接口令牌"); session.commit()
    return {"id":token.id,"token":raw}
@app.get("/api/v1/admin/tokens")
def token_list(user: User = Depends(current_user), session: Session = Depends(db)):
    if user.role != "admin": raise HTTPException(403,"需要管理员权限")
    return [{"id":t.id,"name":t.name,"user_id":t.user_id,"active":t.active} for t in session.scalars(select(ApiToken))]
@app.delete("/api/v1/admin/tokens/{token_id}")
def revoke_token(token_id: str, user: User = Depends(current_user), session: Session = Depends(db)):
    if user.role != "admin": raise HTTPException(403,"需要管理员权限")
    token=session.get(ApiToken,token_id)
    if not token: raise HTTPException(404,"令牌不存在")
    token.active=False; audit(session,user,"撤销接口令牌"); session.commit(); return {"ok":True}

class StatusInput(BaseModel):
    name: str = Field(min_length=1,max_length=100)
@app.get("/api/v1/statuses")
def list_statuses(user: User = Depends(current_user), session: Session = Depends(db)):
    return [s.name for s in session.scalars(select(SiteStatus).order_by(SiteStatus.sort_order,SiteStatus.name))]
@app.post("/api/v1/statuses",status_code=201)
def create_status(body: StatusInput, user: User = Depends(current_user), session: Session = Depends(db)):
    if user.role != "admin": raise HTTPException(403,"需要管理员权限")
    if session.get(SiteStatus,body.name): raise HTTPException(409,"状态已存在")
    session.add(SiteStatus(name=body.name)); audit(session,user,"新增局点状态"); session.commit(); return {"name":body.name}
@app.put("/api/v1/statuses/{name}")
def rename_status(name: str, body: StatusInput, user: User = Depends(current_user), session: Session = Depends(db)):
    if user.role != "admin": raise HTTPException(403,"需要管理员权限")
    status=session.get(SiteStatus,name)
    if not status: raise HTTPException(404,"状态不存在")
    if session.get(SiteStatus,body.name): raise HTTPException(409,"状态已存在")
    session.add(SiteStatus(name=body.name,sort_order=status.sort_order)); session.flush()
    for site in session.scalars(select(Site).where(Site.status==name)): site.status=body.name; site.version+=1
    session.delete(status); audit(session,user,"修改局点状态"); session.commit(); return {"ok":True}
@app.delete("/api/v1/statuses/{name}")
def delete_status(name: str, user: User = Depends(current_user), session: Session = Depends(db)):
    if user.role != "admin": raise HTTPException(403,"需要管理员权限")
    status=session.get(SiteStatus,name)
    if not status: raise HTTPException(404,"状态不存在")
    if session.scalar(select(Site.id).where(Site.status==name).limit(1)): raise HTTPException(409,"该状态仍在使用，请先调整局点状态")
    session.delete(status); audit(session,user,"删除局点状态"); session.commit(); return {"ok":True}

app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="frontend")
