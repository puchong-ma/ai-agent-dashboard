import os
import re
import sqlite3
from datetime import datetime
from typing import Annotated, TypedDict

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass # บน Cloud ไม่ต้องใช้ dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.sqlite import SqliteSaver
#from langgraph_checkpoint_sqlite import SqliteSaver
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import os
google_api_key = os.getenv("GOOGLE_API_KEY")

# Import tools จากไฟล์ tools.py ใน folder เดียวกัน
from core.tools import search_tool, send_line_message

load_dotenv()

# 1. กำหนดโครงสร้างข้อมูล (State)
class TeamState(TypedDict):
    messages: Annotated[list, add_messages]
    research_data: str
    final_article: str
    style_preference: str
    article_score: int  # เก็บตัวเลขคะแนน 1-10

# 2. ตั้งค่า Model
# Model Setup
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0)
llm_pro = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)
llm_ultra = ChatGoogleGenerativeAI(model="gemini-2.5-pro", temperature=0)

# 3. นิยามความสามารถของแผนกต่างๆ (Nodes)

def researcher_node(state: TeamState):
    current_date = datetime.now().strftime("%d %B %Y")
    system_msg = SystemMessage(content=f"Today is {current_date}. Search for latest news. Provide a factual summary.")
    llm_with_search = llm.bind_tools([search_tool])
    response = llm_with_search.invoke([system_msg] + state["messages"])
    return {"messages": [response]}

def editor_node(state: TeamState):
    # ดึงคำสั่งล่าสุดและสรุปวิจัยเพื่อประหยัด Token
    user_instruction = next((msg.content for msg in reversed(state["messages"]) if isinstance(msg, HumanMessage)), "")
    research_summary = next((msg.content for msg in reversed(state["messages"]) if isinstance(msg, AIMessage) and not msg.tool_calls), "")
    
    # รองรับ Shortcut 'editor:'
    if user_instruction.lower().startswith("editor:"):
        user_instruction = user_instruction[7:].strip()

    style = state.get("style_preference", "Executive Summary")
    system_msg = SystemMessage(content=(
        f"คุณคือบรรณาธิการสไตล์ {style} หน้าที่: เรียบเรียงบทความ Markdown "
        "ข้อกำหนด: ตารางต้องกระชับ ห้ามเว้นช่องว่างเยอะเกินไป ห้ามมีคำทักทาย AI"
    ))
    
    response = llm_pro.invoke([system_msg, HumanMessage(content=f"คำสั่ง: {user_instruction}\nข้อมูล: {research_summary}")])
    return {"messages": [response], "final_article": response.content}

def reviewer_node(state: TeamState):
    article = state.get("final_article", "")
    style = state.get("style_preference", "Executive Summary")
    system_msg = SystemMessage(content=(
        f"คุณคือหัวหน้าบรรณาธิการ ตรวจสอบบทความสไตล์ {style} "
        "ให้คะแนน 1-10 ตามความสมบูรณ์และสไตล์ บรรทัดสุดท้ายต้องพิมพ์ 'SCORE: [ตัวเลข]/10'"
    ))
    response = llm_ultra.invoke([system_msg, HumanMessage(content=article)])
    
    # การดึงคะแนนด้วย Regex (แก้ปัญหา Score 0)
    score = 0
    content = response.content
    match = re.search(r"(?:SCORE|Score|คะแนน):\s*(\d+)", content)
    if match:
        score = int(match.group(1))
    elif match := re.search(r"(\d+)/10", content):
        score = int(match.group(1))

    if score < 8:
        send_line_message("⚠️ [AI Reviewer] ตรวจพบจุดที่ต้องแก้ไข กรุณาเข้าไปสั่งการต่อบน Dashboard")
        
    return {"messages": [response], "article_score": score}

def translator_node(state: TeamState):
    thai_article = state.get("final_article", "")
    system_msg = SystemMessage(content="Translate Thai to English Markdown strictly. Keep table format.")
    response = llm_pro.invoke([system_msg, HumanMessage(content=thai_article)])
    # 📢 ส่งข้อความเมื่อจบงาน
    topic = state.get("messages")[0].content[:30] # ดึงหัวข้อสั้นๆ
    msg = f"✅ [AI Agent] ทำงานเสร็จแล้ว!\nหัวข้อ: {topic}...\nตรวจสอบและดาวน์โหลดบทความได้บน Dashboard ครับ"
    send_line_message(msg)
    
    return {"messages": [response], "final_article": response.content}

# 4. Routing Logic (การตัดสินใจ)

def researcher_router(state: TeamState):
    last_message = state["messages"][-1]
    return "call_tools" if isinstance(last_message, AIMessage) and last_message.tool_calls else "editor"

def reviewer_router(state: TeamState):
    # ตัดสินใจจากคะแนนเป็นหลัก
    return "translator" if state.get("article_score", 0) >= 8 else "editor"

# 5. สร้าง Graph และเชื่อมต่อ Checkpointer

builder = StateGraph(TeamState)
builder.add_node("researcher", researcher_node)
builder.add_node("call_tools", ToolNode([search_tool]))
builder.add_node("editor", editor_node)
builder.add_node("reviewer", reviewer_node)
builder.add_node("translator", translator_node)

builder.set_entry_point("researcher")
builder.add_conditional_edges("researcher", researcher_router)
builder.add_edge("call_tools", "researcher")
builder.add_edge("editor", "reviewer")
builder.add_conditional_edges("reviewer", reviewer_router, {"translator": "translator", "editor": "editor"})
builder.add_edge("translator", END)

# ตั้งค่าฐานข้อมูล SQLite
db_path = os.path.join(os.path.dirname(__file__), "../database/agent_memory.db")
os.makedirs(os.path.dirname(db_path), exist_ok=True)
conn = sqlite3.connect(db_path, check_same_thread=False)
memory = SqliteSaver(conn)

# Compile Graph พร้อมระบบหยุดตรวจงาน (Interrupt)
multi_agent_app = builder.compile(checkpointer=memory, interrupt_before=["editor"])

# ฟังก์ชันเสริมสำหรับ Streamlit
def get_all_threads():
    """ดึงรายชื่อ Thread ID ทั้งหมด โดยตรวจสอบก่อนว่ามีตารางหรือไม่"""
    try:
        cursor = conn.cursor()
        # ตรวจสอบว่ามีตาราง checkpoints หรือไม่ก่อน Query
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='checkpoints'")
        table_exists = cursor.fetchone()
        
        if table_exists:
            cursor.execute("SELECT DISTINCT thread_id FROM checkpoints")
            return [row[0] for row in cursor.fetchall()]
        else:
            return [] # ถ้ายังไม่มีตาราง ให้ส่ง List ว่างกลับไป
    except Exception as e:
        print(f"⚠️ [Database View Error]: {e}")
        return []
