from astrbot import Plugin
from astrbot.adapters.qq import MessageEvent
import requests
import json
import time
from celery import Celery
from celery.schedules import crontab

plugin = Plugin("Kindroid QQ")
sessions = {}  # 存储用户对话上下文 {user_id: {"last_active": timestamp, "session_id": "xxx"}}

# 初始化 Celery
celery = Celery('tasks', broker='redis://localhost')

# 异步调用 Kindroid API
@celery.task
def async_kindroid_call(api_key: str, message: str, session_id: str = "") -> dict:
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {
        "message": message,
        "ai_id": plugin.config["ai_id"],  # 指定目标 AI ID
        "session_id": session_id  # 用于维持上下文
    }
    try:
        resp = requests.post(plugin.config["api_endpoint"], headers=headers, json=data)
        return resp.json()
    except Exception as e:
        return {"response": f"请求失败: {str(e)}"}

# 处理 QQ 消息
@plugin.on_message("qq")
async def handle_qq_message(event: MessageEvent):
    user_id = event.user_id
    message = event.message.strip()

    # 检查会话是否超时
    if user_id in sessions and (time.time() - sessions[user_id]["last_active"]) > plugin.config["session_timeout"]:
        await reset_session(user_id)

    # 异步调用 Kindroid API
    task = async_kindroid_call.delay(plugin.config["api_key"], message, session_id=sessions.get(user_id, {}).get("session_id", ""))
    result = task.get(timeout=30)  # 设置超时时间
    await event.reply(result["response"])

# 发送消息给 Kindroid
def send_to_kindroid(api_key: str, message: str) -> dict:
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {
        "message": message,
        "ai_id": plugin.config["ai_id"],  # 指定目标 AI ID
        # 或使用 shared_code: "shared_code": plugin.config["shared_code"]
    }
    resp = requests.post(plugin.config["api_endpoint"], headers=headers, json=data)
    return resp.json()

# 同步重置会话
def reset_session(user_id: str):
    if user_id in sessions:
        del sessions[user_id]

# Celery 配置：每小时重置会话
celery.conf.beat_schedule = {
    'reset-sessions-every-hour': {
        'task': 'kindroid_qq.reset_sessions',
        'schedule': crontab(hour='*/1'),  # 每小时重置一次会话
    },
}

# 同步调用重置会话
@celery.task
def reset_sessions():
    for user_id in list(sessions.keys()):
        reset_session(user_id)

# 新增 chat break 功能
@plugin.on_command("chat_break")
async def handle_chat_break_command(event: MessageEvent, args: str):
    user_id = event.user_id
    greeting = args.strip() if args else "Hello"  # 默认问候语

    # 调用 Kindroid 的 chat-break 接口
    response = await chat_break(plugin.config["api_key"], plugin.config["ai_id"], greeting)

    # 发送响应到 QQ
    await event.reply(response["response"])

# 发送请求给 Kindroid 的 chat-break 接口
async def chat_break(api_key: str, ai_id: str, greeting: str) -> dict:
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {
        "ai_id": ai_id,
        "greeting": greeting
    }
    try:
        resp = requests.post(plugin.config["api_endpoint"] + "/chat-break", headers=headers, json=data)
        return resp.json()
    except Exception as e:
        return {"response": f"请求失败: {str(e)}"}
