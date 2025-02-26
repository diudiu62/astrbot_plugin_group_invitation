'''
Author: diudiu62
Date: 2025-02-18 16:50:13
LastEditTime: 2025-02-26 09:30:38
'''
import asyncio
from astrbot.api.event import AstrMessageEvent
from astrbot.api.event.filter import platform_adapter_type, command, PlatformAdapterType
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import *
from astrbot.core.platform.sources.gewechat.gewechat_event import GewechatPlatformEvent


@register("group_invitation", "diudiu62", "微信群邀请", "1.0.0", "https://github.com/diudiu62/astrbot_plugin_group_invitation.git")
class MyPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.group_invitation_config = config.get("group_invitation_config", [])
        self.group_welcome_msg = config.get("group_welcome_msg", [])

    @command("groupid")
    async def get_group_id(self, event: AstrMessageEvent):
        '''获取群id'''
        groupid = event.get_group_id()
        groupid = groupid.split('@')[0]
        yield event.plain_result(f"当前群ID：{groupid}")
        event.stop_event()

    @platform_adapter_type(PlatformAdapterType.GEWECHAT)
    async def group_invitation(self, event: AstrMessageEvent):
        '''微信群邀请'''
        if event.get_platform_name() == "gewechat":
            if not self.group_invitation_config["switch"]:
                return
            
            assert isinstance(event, GewechatPlatformEvent)
            client = event.client

            keys_values  = set(self.group_invitation_config["keywords"])
            data = []
            for item in keys_values:
                k, v = item.split('#')
                data.append({k: v})
            logger.debug(data)

            group_id = None

            text = event.message_str
            for item in data:
                if text in item:
                    group_id = item[text] + "@chatroom"
                    logger.debug(f"邀请入群的group_id: {group_id}")
                    try:
                        wxid = event.get_sender_id()
                        logger.debug("wxid:",wxid)
                        nickname = event.get_sender_name()
                        users_list = await client.get_chatroom_member_list(group_id)

                        if self.is_user_in_group(wxid, users_list["data"]["memberList"]):
                            logger.info("用户已经在群聊。")
                            group_info = await client.get_chatroom_info(group_id)
                            group_name = group_info["data"]["nickName"]
                            yield event.plain_result(f"你已经在群 【{group_name}】 中了！")
                        else:
                            await self.invite_user(wxid, group_id, client)
                            delay = int(self.group_welcome_msg.get("delay", 0))
                            await asyncio.sleep(delay)  # 延时
                            await self.send_welcome_message(wxid, nickname, group_id, client, event)

                    except Exception as e:
                        logger.error(f"处理群邀请时发生错误: {e}")

                    break
            event.stop_event()

    def is_user_in_group(self, wxid, member_list):
        """检查用户是否在群聊中"""
        return any(member["wxid"] == wxid for member in member_list)

    async def invite_user(self, wxid, group_id, client):
        """邀请用户加入群聊"""
        logger.info("用户不在群聊，尝试邀请...")
        await client.invite_member(wxid, group_id, "")
        delay = int(self.group_invitation_config.get("delay", 0))
        await asyncio.sleep(delay)  # 延时
        await client.post_text(wxid, "已经邀请您加入群聊。")

    async def send_welcome_message(self, wxid, nickname, group_id, client, event):
        """发送欢迎信息"""
        welcome_msg = None
        if self.group_welcome_msg["msg"]:
            welcome_msg = self.group_welcome_msg["msg"]
        elif self.group_welcome_msg["msg"] == "":
            llm_response = await self.context.get_using_provider().text_chat(
                prompt=f"请你随机使用一种风格说一句问候语来欢迎新用户\"{nickname}\"加入群聊。",
                session_id=event.unified_msg_origin
            )
            if llm_response.role == "assistant":
                welcome_msg = llm_response.completion_text
        await client.post_text(group_id, welcome_msg, wxid)
        logger.info(f"发送入群欢迎信息：{welcome_msg}")