import asyncio
import os
from contextlib import asynccontextmanager
import json
from pathlib import Path
import bcrypt
import jwt
import time

import uvicorn
from fastapi import FastAPI, Depends, Header
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from bus.queue import MessageBus
from bus.events import InboundMessage
from providers.openai_compat import OpenAICompatProvider
from providers.embedding import EmbeddingProvider
from session.manager import SessionManager
from agent.memory import MemoryStore
from agent.rag import RagStore
from agent.context_builder import ContextBuilder
from agent.loop import AgentLoop
from agent.tools.registry import ToolRegistry
import storage.wordbook_store as store
import storage.auth_store as auth
from fastapi import HTTPException
from agent.tools.wordbook import(
    StudentStatTool,
    ImportWordTool,
    GetReviewBatchTool,
    FetchQuizOptionsTool,
    RecordAnswerTool,
    GetStudentInfoTool,
    ListStudentsTool,
    DeleteWordTool,
    UpdateWordTool,
)

cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))
oc = cfg["providers"]["openai"]
SECRET = cfg["auth"]["secret"]

bus = MessageBus()
provider = OpenAICompatProvider(
        api_key=oc["api_key"], api_base=oc["api_base"], default_model=oc["model"]
        )  # FIX: api_key=["api_key"] → oc["api_key"]。原来把字面量"api_key"装进列表了，认证会 401

embedder = EmbeddingProvider(
        api_key=oc["api_key"], api_base=oc["api_base"], model="embedding-2"
    )  # FIX: 同上

sessions = SessionManager(Path.cwd())
memory = MemoryStore(Path.cwd())
rag = RagStore(embedder, store_path=Path("memory/rag.json"))

context_builder = ContextBuilder(
provider, sessions, memory, rag,
system_prompt="You are a helpful assistant",
)

tools = ToolRegistry()
#注册StudentStatTool和ImportWordTool工具
tools.register(StudentStatTool())
tools.register(ImportWordTool(embedder))
tools.register(GetReviewBatchTool())
tools.register(FetchQuizOptionsTool())
tools.register(RecordAnswerTool())
tools.register(GetStudentInfoTool())
tools.register(ListStudentsTool())
tools.register(DeleteWordTool())
tools.register(UpdateWordTool())
loop = AgentLoop(bus=bus, context_builder=context_builder, provider=provider, tools=tools)  # FIX: 用关键字参数，别用位置参数——否则 provider/tools 顺序一错就静默错位

class ChatRequest(BaseModel):
    session_key: str
    content: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init_db()  # 启动时建表（幂等：IF NOT EXISTS）。之前没人调它，account 表都不存在，登录会 500。
    loop_task = asyncio.create_task(loop.run())
    yield
    loop.stop()
    loop_task.cancel()  # FIX: loop._task → loop_task（loop 没有 _task 属性，要取消的是上面 create_task 返回的 loop_task）
    try:
        await loop_task
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return {"status": "ok", "message": "mybot gateway 运行中，访问 /docs 查看接口文档"}

@app.get("/demo", response_class=HTMLResponse)
def demo():
    # 前端演示页：直接读 static/demo.html 返回。和 API 同源，所以页面里的
    # fetch("/students/...") 不需要跨域配置，浏览器直接就能调后端。
    return Path("static/demo.html").read_text(encoding="utf-8")


def get_current_account(authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="未登录或token无效")
    return payload
    

def require_manager(current = Depends(get_current_account)):
    if current["role"] != "manager":
        raise HTTPException(status_code=403, detail="无权限")
    return current

class AddStudentAccount(BaseModel):
    name: str
    class_name: str
    username: str

@app.post("/students/accounts")
def create_student_account(req: AddStudentAccount, _manager: dict = Depends(require_manager)):
    return auth.create_sutdent_account(req.username)

class ChangePassword(BaseModel):
    old_password: str
    new_password: str

@app.post("/auth/change-password")
def change_password(req: ChangePassword, account: dict = Depends(get_current_account)):
    account_id = int(account["sub"])
    row = auth.get_account_by_id(account_id)
    if row is None:
        raise HTTPException(status_code=404, detail="该用户不存在")
    if not bcrypt.checkpw(req.old_password.encode(), row["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="旧密码错误")
    new_hash = bcrypt.hashpw(req.new_password.encode(), bcrypt.gensalt()).decode("utf-8")
    auth.update_password(account_id, new_hash)
    return {"ok": True}


def require_student_owner(student_id: int, account: dict = Depends(get_current_account)):
    if student_id != account.get("student_id"):
        raise HTTPException(status_code=403, detail="无权限")
    return account
    
@app.post("/chat")
async def chat(req: ChatRequest):
    await bus.publish_inbound(InboundMessage(
        channel="wechat",
        sender_id=req.session_key,
        chat_id=req.session_key,
        content=req.content,
        session_key_override=req.session_key,
    ))
    outbound = await bus.consume_outbound()
    return {"content": outbound.content}

@app.get("/students/{student_id}/stats")
def student_stats(student_id:int, _student: dict = Depends(require_student_owner)):
    return store.get_student_stat(student_id)

class AddStudentRequest(BaseModel):
    name: str
    class_name: str

@app.post("/students")
def create_student(req: AddStudentRequest, _manager: dict = Depends(require_manager)):
    sid = store.add_student(req.name, req.class_name)
    return {"student_id": sid}

class AddWordRequest(BaseModel):
    library_tag: str
    cn_text: str
    kor_text: str
    extra_info: str | None=None

@app.get("/words")
def list_words():
    return store.list_words()

@app.post("/words")
def words_library(req:AddWordRequest, _manager: dict = Depends(require_manager)):
    affected = store.import_word_library(req.cn_text, req.kor_text, req.extra_info, req.library_tag)
    return {"imported": affected}

@app.get("/students/{student_id}/batch")
def student_batch(student_id: int, new_limit: int = 5, due_limit: int = 10, _student: dict = Depends(require_student_owner)):
    return store.get_review_batch(student_id, new_limit=new_limit , due_limit=due_limit)

@app.get("/words/{word_id}/options")
def options(word_id: int, count: int = 3):
    return store.fetch_quiz_options(word_id, count=count)

class GetAnswerRequest(BaseModel):
    word_id: int
    is_correct: bool
    word_version: int

@app.post("/students/{student_id}/answers")
def submit_answers(student_id:int ,req:GetAnswerRequest, _student: dict = Depends(require_student_owner)):
    return store.record_answer(student_id, req.word_id, req.is_correct, req.word_version)

class UpdateWordRequest(BaseModel):
    cn_text: str
    kor_text: str
    extra_info: str | None = None

@app.put("/words/{word_id}")
def update_word(word_id: int, req: UpdateWordRequest, _manager: dict = Depends(require_manager)):
    result = store.update_word(word_id, req.cn_text, req.kor_text, req.extra_info)
    if not result["ok"]:
        code = 409 if result["error"] == "duplicate" else 404
        raise HTTPException(status_code=code, detail=result["error"])
    return result

@app.delete("/words/{word_id}")
def delete_word(word_id: int, _manager: dict = Depends(require_manager)):
    result = store.delete_word(word_id)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/auth/login")
def login(req: LoginRequest):
    account = auth.get_account_by_username(req.username)
    if account is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    ok = bcrypt.checkpw(req.password.encode("utf-8"), account["password_hash"].encode("utf-8"))
    if not ok:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    token = jwt.encode(
        {
            "sub": str(account["account_id"]),
            "role": account["role"],
            "student_id": account["student_id"],
            "exp": int(time.time()) + 3600,
        },
        SECRET,
        algorithm="HS256"
    )
    return {"token": token, "role": account["role"], "student_id": account["student_id"]}



if __name__ == "__main__":
    # 云托管要求监听 0.0.0.0（所有网卡）而非 127.0.0.1：
    #   127.0.0.1 只接受本机回环连接，容器外的流量根本进不来；
    #   0.0.0.0 监听所有网卡，云托管的公网入口才能把请求转发进来。
    # 端口从环境变量 PORT 读：云托管会注入 PORT，并把你监听的端口映射到公网；
    #   写死 8000 会导致和它预期的端口对不上。
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)