import os
from dotenv import load_dotenv
from linebot import LineBotApi
from linebot.models import TextSendMessage
from linebot.models import FlexSendMessage
# 1. ต้องโหลด .env ก่อนที่จะเรียกใช้ Tool อื่นๆ เสมอ
load_dotenv()

# 2. เปลี่ยนการ Import ตามที่ระบบแนะนำ (Deprecation Fix)
# รัน pip install -U langchain-tavily ใน terminal ก่อนนะครับ
try:
    from langchain_tavily import TavilySearchResults
except ImportError:
    # ถ้ายังไม่ได้ติดตั้งตัวใหม่ ให้ใช้ตัวเดิมไปก่อน
    from langchain_community.tools.tavily_search import TavilySearchResults

from langchain_core.tools import tool

# 3. สร้าง Tool โดยระบุ API Key ให้ชัดเจน (เพื่อความชัวร์)
search_tool = TavilySearchResults(
    k=5, search_depth="advanced",
    tavily_api_key=os.getenv("TAVILY_API_KEY")
)

@tool
def save_report(filename: str, content: str):
    """ใช้สำหรับบันทึกรายงาน Markdown ลงใน IDE Antigravity"""
    if not filename.endswith(".md"):
        filename += ".md"
    
    # สร้างโฟลเดอร์ outputs ถ้ายังไม่มี
    if not os.path.exists("outputs"):
        os.makedirs("outputs")
        
    filepath = os.path.join("outputs", filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return f"✅ บันทึกรายงานลงใน {filepath} เรียบร้อยแล้ว"

@tool
def web_search(query: str):
    """ค้นหาข้อมูลล่าสุดจากอินเทอร์เน็ต"""
    print(f"\n🔍 [LOG] Searching for: {query}")
    results = search_tool.invoke({"query": query})
    
    # เพิ่ม Log เพื่อดูว่า Tavily ได้ข้อมูลอะไรมาบ้าง
    print(f"📡 [LOG] Found {len(results)} sources.")
    for i, res in enumerate(results):
        print(f"   - Source {i+1}: {res.get('url')} (Score: {res.get('score')})")
        
    return results

def send_line_message(message: str):
    # ดึงค่าจาก .env (Local) หรือ Secrets (Cloud)
    line_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.getenv("LINE_USER_ID")
    
    if not line_token or not user_id:
        print("⚠️ [Line Error]: ไม่พบรหัส Access Token หรือ User ID")
        return
        
    try:
        line_bot_api = LineBotApi(line_token)
        line_bot_api.push_message(user_id, TextSendMessage(text=message))
        print("✅ [Line Success]: ส่งข้อความแจ้งเตือนเรียบร้อย")
    except Exception as e:
        print(f"❌ [Line Exception]: {e}")

def send_line_flex(topic: str, score: int):
    line_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.getenv("LINE_USER_ID")
    
    if not line_token or not user_id:
        return "Missing Line Credentials"
    
    # โครงสร้าง JSON ของ Flex Message (ดีไซน์แบบการ์ดสรุปงาน)
    flex_content = {
      "type": "bubble",
      "header": {
        "type": "box", "layout": "vertical", "contents": [
          {"type": "text", "text": "🔔 งานเสร็จสมบูรณ์!", "weight": "bold", "color": "#FFFFFF", "size": "lg"}
        ], "backgroundColor": "#0367D3"
      },
      "body": {
        "type": "box", "layout": "vertical", "contents": [
          {"type": "text", "text": f"หัวข้อ: {topic}", "weight": "bold", "wrap": True},
          {"type": "separator", "margin": "md"},
          {"type": "box", "layout": "horizontal", "margin": "md", "contents": [
            {"type": "text", "text": "Quality Score:", "size": "sm", "color": "#555555"},
            {"type": "text", "text": f"{score}/10", "size": "sm", "weight": "bold", "align": "end", "color": "#1DB446" if score >= 8 else "#E63946"}
          ]}
        ]
      },
      "footer": {
        "type": "box", "layout": "vertical", "contents": [
          {"type": "button", "action": {"type": "uri", "label": "ดูบน Dashboard", "uri": "https://ai-agent-dashboard.streamlit.app"}, "style": "primary", "color": "#0367D3"}
        ]
      }
    }

    try:
        line_bot_api = LineBotApi(line_token)
        line_bot_api.push_message(user_id, FlexSendMessage(alt_text="AI งานเสร็จแล้ว!", contents=flex_content))
        return "Success"
    except Exception as e:
        return str(e)

# tools = [search_tool, save_report]
tools = [search_tool, save_report]