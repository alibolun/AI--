from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest
from langchain.chat_models import init_chat_model
from langchain_tavily import TavilySearch
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

# 初始化 Agent
web_search = TavilySearch(
    max_results=5,
    topic="general"
)

model = init_chat_model(
    model="qwen3.5-plus",
    model_provider="openai",
    base_url=os.getenv("DASHSCOPE_BASE_URL"),
    api_key=os.getenv("DASHSCOPE_API_KEY")
)

system_prompt = """
你是一名私人厨师。收到用户提供的食材照片或清单后，请按以下流程操作：
1.识别和评估食材：若用户提供照片，首先辨识所有可见食材。基于食材的外观状态，评估其新鲜度与可用量，整理出一份"当前可用食材清单"。
2.智能食谱检索：优先调用 web_search 工具，以"可用食材清单"为核心关键词，查找可行菜谱。
3.多维度评估与排序：从营养价值和制作难度两个维度对检索到的候选食谱进行量化打分，并根据得分排序，制作简单且营养丰富的排名靠前。
4.结构化方案输出：把排序后的食谱整理为一份结构清晰的建议报告，要包含食谱信息、得分、推荐理由、食谱的参考图片，帮助用户快速做出决策。

请严格按照流程，优先调用 web_search 工具搜索食谱，搜索不到的情况下才能自己发挥。
"""

memory = MemorySaver()
agent = create_agent(
    model=model,
    tools=[web_search],
    system_prompt=system_prompt,
    checkpointer=memory
)

# 简单的内存存储，用于保存对话历史
chat_history = {}


@router.post("/chat/stream")
async def chat_endpoint(request: ChatRequest):
    """流式对话"""
    async def generate():
        # 准备消息
        messages = [{"role": "user", "content": request.message}]
        
        # 如果有图片，添加到消息中
        if request.image_url:
            messages[0]["content"] = [
                {"type": "text", "text": request.message},
                {"type": "image_url", "image_url": {"url": request.image_url}}
            ]
        
        # 调用 Agent
        config = {"configurable": {"thread_id": request.thread_id}}
        
        try:
            async for event in agent.astream_events(
                {"messages": messages},
                config=config,
                version="v2"
            ):
                kind = event["event"]
                if kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        yield content
        except Exception as e:
            yield f"\n[错误: {str(e)}]"
    
    return StreamingResponse(generate(), media_type="text/plain")


@router.get("/chat/messages")
async def get_chat_messages(thread_id: str):
    """获取历史消息"""
    try:
        config = {"configurable": {"thread_id": thread_id}}
        state = agent.get_state(config)
        
        if state and state.values and "messages" in state.values:
            messages = []
            for msg in state.values["messages"]:
                messages.append({
                    "role": msg.type,
                    "content": msg.content
                })
            return {"messages": messages}
        
        return {"messages": []}
    except Exception as e:
        return {"messages": [], "error": str(e)}


@router.delete("/chat/messages")
async def clear_chat_messages(thread_id: str):
    """清空历史消息"""
    try:
        config = {"configurable": {"thread_id": thread_id}}
        # 清除状态
        agent.delete_state(config)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}