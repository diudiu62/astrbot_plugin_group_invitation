'''
Author: diudiu62
Date: 2025-02-18 16:50:13
LastEditTime: 2025-02-27 13:38:55
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
        self.event = None
        self.client = None

    @command("groupid")
    async def get_group_id(self, event: AstrMessageEvent):
        '''获取群ID'''
        groupid = event.get_group_id().split('@')[0]
        yield event.plain_result(f"当前群ID：{groupid}")
        event.stop_event()

    @platform_adapter_type(PlatformAdapterType.GEWECHAT)
    async def group_invitation(self, event: AstrMessageEvent):
        '''处理微信群邀请'''
        if event.get_platform_name() == "gewechat" and self.group_invitation_config.get("switch", False):
            self.event = event
            assert isinstance(event, GewechatPlatformEvent)
            self.client = event.client

            # 准备关键词和对应的群ID
            keys_values = set(self.group_invitation_config["keywords"])
            data = [{k: v} for item in keys_values for k, v in [item.split('#')]]

            logger.debug(data)

            group_id = None
            text = event.message_str

            for item in data:
                if text in item:
                    group_id = item[text] + "@chatroom"
                    logger.debug(f"邀请入群的group_id: {group_id}")

                    try:
                        wxid = event.get_sender_id()
                        logger.debug("wxid:", wxid)
                        # nickname = event.get_sender_name() #带了emoji的昵称无法正常显示
                        userinfo = await self.client.get_brief_info([wxid])
                        nickname = userinfo['data'][0]['nickName']
                        print("nickname:",nickname)
                        users_list = await self.client.get_chatroom_member_list(group_id)

                        if await self.is_user_in_group(wxid, users_list["data"]["memberList"]):
                            logger.info("用户已经在群聊。")
                            group_info = await self.client.get_chatroom_info(group_id)
                            group_name = group_info["data"]["nickName"]
                            yield self.event.plain_result(f"你已经在群 【{group_name}】 中了！")
                        else:
                            logger.info("用户不在群聊，尝试邀请...")
                            await self.client.invite_member(wxid, group_id, "")
                            delay = int(self.group_invitation_config.get("delay", 0))
                            await asyncio.sleep(delay)  # 延时
                            yield self.event.plain_result("已经邀请您加入群聊。") 
                            await self.send_welcome_message(wxid, nickname, group_id)

                    except ExceptionGroup as e:
                        logger.error(f"处理群邀请时发生错误: {e}")

                    break
                    
            event.stop_event()

    async def is_user_in_group(self, wxid, member_list):
        """检查用户是否在群聊中"""
        return any(member["wxid"] == wxid for member in member_list)

    async def send_welcome_message(self, wxid, nickname, group_id):
        """发送欢迎信息"""
        welcome_msg = self.group_welcome_msg.get("msg")
        
        if not welcome_msg:
            llm_response = await self.context.get_using_provider().text_chat(
                prompt=f"请你随机使用一种风格说一句问候语来欢迎新用户：{nickname}。",
                session_id=self.event.unified_msg_origin
            )
            if llm_response.role == "assistant":
                welcome_msg = llm_response.completion_text

        delay = int(self.group_welcome_msg.get("delay", 0))
        await asyncio.sleep(delay)  # 延时
        await self.client.post_text(group_id, f'@{nickname} {welcome_msg}', wxid)
        logger.info(f"发送入群欢迎信息：{welcome_msg}")