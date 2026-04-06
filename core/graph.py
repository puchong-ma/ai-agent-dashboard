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
#from langgraph.checkpoint.sqlite import SqliteSaver
#from langgraph_checkpoint_sqlite import SqliteSaver
# ลบบรรทัดเดิม: from langgraph.checkpoint.sqlite import SqliteSaver
# เพิ่มบรรทัดใหม่:
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection # สำหรับจัดการ Connection
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import os
google_api_key = os.getenv("GOOGLE_API_KEY")

# Import tools จากไฟล์ tools.py ใน folder เดียวกัน
from core.tools import search_tool, send_line_message

load_dotenv()

# สร้าง Connection String สำหรับ Supabase
# หมายเหตุ: คุณต้องใช้ "Connection String" จากหน้า Settings > Database ใน Supabase นะครับ
DB_URI = os.getenv("SUPABASE_DB_URL")

# ใช้ Context Manager เพื่อจัดการ Memory
def get_memory():
    sync_connection = Connection.connect(DB_URI)
    return PostgresSaver(sync_connection)

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
    try:
        current_date = datetime.now().strftime("%d %B %Y")
        system_msg = SystemMessage(content=f"Today is {current_date}. Search for latest news. Provide a factual summary.")
        llm_with_search = llm.bind_tools([search_tool])
        response = llm_with_search.invoke([system_msg] + state["messages"])
        return {"messages": [response]}
    except Exception as e:
        # เมื่อเกิด Error ให้ส่ง Line บอกเราทันที
        error_msg = f"❌ [Error] ในขั้นตอน Researcher:\n{str(e)}"
        send_line_message(error_msg)
        
        # ส่งข้อความ Error กลับไปในระบบเพื่อให้ Graph หยุดทำงานอย่างสุภาพ
        return { "messages": [HumanMessage(content=f"Error occurred: {str(e)}")] }

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
    try:
        thai_article = state.get("final_article", "")
        system_msg = SystemMessage(content="Translate Thai to English Markdown strictly. Keep table format.")
        response = llm_pro.invoke([system_msg, HumanMessage(content=thai_article)])
        # 📢 ส่งข้อความเมื่อจบงาน
        topic = state.get("messages")[0].content[:30] # ดึงหัวข้อสั้นๆ
        msg = f"✅ [AI Agent] ทำงานเสร็จแล้ว!\nหัวข้อ: {topic}...\nตรวจสอบและดาวน์โหลดบทความได้บน Dashboard ครับ"
        send_line_message(msg)
        
        return {"messages": [response], "final_article": response.content}
    except Exception as e:
        # แจ้งเตือนเมื่อเกิด Error
        send_line_message(f"❌ ระบบขัดข้องในขั้นตอน Translator: {str(e)}")
        raise e

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
# db_path = os.path.join(os.path.dirname(__file__), "../database/agent_memory.db")
# os.makedirs(os.path.dirname(db_path), exist_ok=True)
# conn = sqlite3.connect(db_path, check_same_thread=False)
# memory = SqliteSaver(conn)

# --- แก้ไขฟังก์ชัน get_app ให้รับส่ง Connection ได้ถูกต้อง ---
def get_app():
    """ฟังก์ชันสำหรับ Compile Graph โดยใช้ PostgresSaver แบบบังคับเขียน (Manual Commit)"""
    conn = Connection.connect(DB_URI)
    
    # บังคับให้ทุกคำสั่ง SQL เขียนลงแผ่นดิสก์ของ Supabase ทันที
    conn.autocommit = True 
    
    checkpointer = PostgresSaver(conn)
    checkpointer.setup() 
    
    # สำคัญ: ห้ามเปลี่ยน autocommit เป็น False เพราะเราต้องการให้มันบันทึก "ทันที" หลังจบ Node
    return builder.compile(checkpointer=checkpointer, interrupt_before=["editor"])
# --- ปรับปรุงฟังก์ชัน get_all_threads ให้รองรับ Postgres ---
# --- ปรับปรุง get_all_threads ให้แม่นยำขึ้น ---
def get_all_threads():
    """ดึงรายชื่อ Thread ID จาก Supabase แบบกรองเฉพาะที่มีข้อมูลจริง"""
    try:
        # ใช้ context manager เพื่อปิด connection เสมอ
        with Connection.connect(DB_URI) as conn:
            with conn.cursor() as cur:
                # ตรวจสอบก่อนว่าตารางมีอยู่จริงไหม
                cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'checkpoints')")
                if cur.fetchone()[0]:
                    # ดึง thread_id ที่มีการบันทึกข้อมูลแล้วจริงๆ
                    cur.execute("SELECT DISTINCT thread_id FROM checkpoints")
                    threads = [row[0] for row in cur.fetchall()]
                    print(f"✅ Found threads: {threads}") # Debug เพื่อดูใน Terminal
                    return threads
                return []
    except Exception as e:
        print(f"⚠️ [Supabase Database Error]: {e}")
        return []

def get_project_summary(username: str):
    """ดึงรายชื่อโปรเจกต์และเวลาอัปเดตล่าสุดของคุณอาร์ทจาก Supabase"""
    summary_data = []
    DB_URI = os.getenv("SUPABASE_DB_URL") # ดึง URL จาก .env
    
    try:
        # ใช้ psycopg เชื่อมต่อกับ Supabase
        with Connection.connect(DB_URI) as conn:
            with conn.cursor() as cur:
                # SQL: เลือกชื่อโปรเจกต์และเวลาล่าสุด โดยกรองเฉพาะของ User นี้
                cur.execute("""
                    SELECT thread_id, MAX(created_at) as last_update
                    FROM checkpoints 
                    WHERE thread_id LIKE %s 
                    GROUP BY thread_id
                    ORDER BY last_update DESC
                """, (f"{username}_%",))
                
                for row in cur.fetchall():
                    # ตัดชื่อ username_ ออกเพื่อให้เหลือชื่อโปรเจกต์ที่คุณอาร์ทตั้งไว้
                    clean_name = row[0].replace(f"{username}_", "")
                    summary_data.append({
                        "Project Name": clean_name,
                        "Last Updated": row[1].strftime("%d/%m/%Y %H:%M")
                    })
        return summary_data
    except Exception as e:
        print(f"⚠️ [Database Summary Error]: {e}")
        return []