from astrbot.core.plugin import BasePlugin
from astrbot.types import MessageEvent
import aiohttp
import yaml
import time
import logging
import os
from typing import Dict, Any

class Plugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.config = self.load_config()
        self.logger = logging.getLogger("astrbot.plugin.kindroid_qq")
        self.is_configured = self.check_configuration()
        
    def load_config(self) -> dict:
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}")
            return {
                "api_key": "",
                "api_endpoint": "https://api.kindroid.ai/v1/chat",
                "ai_id": "",
                "session_timeout": 3600,
                "default_greeting": "你好,我是你的AI助手",
                "error_message": "抱歉,发生了一些错误,请稍后再试"
            }

    def check_configuration(self) -> bool:
        return bool(self.config.get("api_key")) and bool(self.config.get("ai_id"))
        
    def save_config(self):
        config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(self.config, f)
            return True
        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")
            return False

    async def handle_message(self, event: MessageEvent):
        if not self.is_configured:
            await self.handle_configuration(event)
            return
            
        user_id = event.user_id
        message = event.message.strip()
        
        if not message:
            return
            
        try:
            response = await self.send_to_kindroid(
                message,
                session_id=self.sessions.get(user_id, {}).get("session_id", "")
            )
            await event.reply(response.get("response", self.config["error_message"]))
        except Exception as e:
            self.logger.error(f"处理消息时发生错误: {e}")
            await event.reply(self.config["error_message"])

    async def handle_configuration(self, event: MessageEvent):
        message = event.message.strip()
        
        if not self.config.get("api_key"):
            if message.startswith("api_key:"):
                api_key = message.replace("api_key:", "").strip()
                self.config["api_key"] = api_key
                self.save_config()
                await event.reply("API Key 已保存，请输入 AI ID (格式: ai_id:你的AI_ID)")
            else:
                await event.reply("请输入你的 API Key (格式: api_key:你的API密钥)")
            return
            
        if not self.config.get("ai_id"):
            if message.startswith("ai_id:"):
                ai_id = message.replace("ai_id:", "").strip()
                self.config["ai_id"] = ai_id
                self.save_config()
                self.is_configured = True
                await event.reply("配置完成！现在可以开始使用了。发送 /help 查看使用帮助。")
            else:
                await event.reply("请输入你的 AI ID (格式: ai_id:你的AI_ID)")
            return

    async def send_to_kindroid(self, message: str, session_id: str = "") -> dict:
        headers = {
            "Authorization": f"Bearer {self.config['api_key']}",
            "Content-Type": "application/json"
        }
        
        data = {
            "message": message,
            "ai_id": self.config["ai_id"]
        }
        
        if session_id:
            data["session_id"] = session_id
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config["api_endpoint"],
                    headers=headers,
                    json=data
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        self.logger.error(f"API请求失败: HTTP {resp.status}")
                        return {"response": self.config["error_message"]}
        except Exception as e:
            self.logger.error(f"发送请求到Kindroid失败: {e}")
            return {"response": self.config["error_message"]}

    async def reset_session(self, user_id: str, greeting: str = None):
        if user_id in self.sessions:
            del self.sessions[user_id]
            
        if greeting:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.config['api_endpoint']}/chat-break",
                        headers={
                            "Authorization": f"Bearer {self.config['api_key']}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "ai_id": self.config["ai_id"],
                            "greeting": greeting
                        }
                    ) as resp:
                        if resp.status == 200:
                            return await resp.json()
                        else:
                            return {"response": self.config["error_message"]}
            except Exception as e:
                self.logger.error(f"Chat-break请求失败: {e}")
                return {"response": self.config["error_message"]}
        return {"response": "会话已重置"}

    async def on_command(self, event: MessageEvent, command: str, args: str):
        if command == "reset":
            greeting = args.strip() if args else self.config.get("default_greeting", "你好")
            response = await self.reset_session(event.user_id, greeting)
            await event.reply(response["response"])
            
        elif command == "help":
            help_text = (
                "Kindroid QQ 插件使用帮助:\n"
                "- 直接发送消息即可与AI对话\n"
                "- /reset [问候语]: 重置当前会话\n"
                "- /help: 显示本帮助信息\n"
                "- 配置命令:\n"
                "  api_key:你的API密钥 - 设置API Key\n"
                "  ai_id:你的AI_ID - 设置AI ID"
            )
            await event.reply(help_text)

plugin = Plugin()
