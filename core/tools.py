import os
from dotenv import load_dotenv
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

# tools = [search_tool, save_report]
tools = [search_tool, save_report]