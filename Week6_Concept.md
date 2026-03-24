# 🌐 Week 6: The AI Agent Dashboard Concept
> **Goal:** เปลี่ยนระบบ Multi-Agent จาก Terminal สู่ Web Application ที่ใช้งานได้จริงด้วย Streamlit

---

## 🏗️ 1. Project Structure (โครงสร้างโปรเจกต์)
เพื่อให้การจัดการโค้ดง่ายขึ้นและรองรับการขยายตัวในอนาคต:

- `app.py`: ไฟล์หลักสำหรับรัน UI (Streamlit)
- `core/`: โฟลเดอร์เก็บ Logic สำคัญ
    - `graph.py`: เก็บ StateGraph, Nodes และ Routers (ยกมาจาก Week 5)
    - `tools.py`: เก็บ Search Tools และเครื่องมือเสริมอื่นๆ
- `database/`: เก็บ `agent_memory.db` สำหรับ Persistence

---

## 🎨 2. UI Components (องค์ประกอบหน้าเว็บ)

### 📍 Sidebar (แถบควบคุมด้านข้าง)
- **Project Selection**: Dropdown เลือกโปรเจกต์เดิมจากฐานข้อมูล หรือปุ่มสร้างโปรเจกต์ใหม่
- **Style Configurator**: Radio buttons หรือ Selectbox สำหรับเลือกสไตล์ (Technical, Storytelling, Executive)
- **Session Info**: แสดง Thread ID ปัจจุบันที่กำลังทำงาน

### 📍 Main Dashboard (หน้าจอหลัก)
- **Header**: ชื่อโปรเจกต์และหัวข้อวิจัยที่กำลังทำ
- **Progress Tracking**: 
    - แสดงสถานะการทำงานแบบ Step-by-step (🔍 Researching -> ✍️ Editing -> 🧐 Reviewing)
    - ใช้ `st.status` หรือ `st.spinner` เพื่อบอกว่า AI ตัวไหนกำลังคิดอยู่
- **Quality Metric**: 
    - แสดง **Quality Score (1-10)** ในรูปแบบ Gauge chart หรือตัวเลขขนาดใหญ่
    - แสดง Feedback ล่าสุดจาก Reviewer

---

## 🧠 3. Logic & State Management

### 🔄 Session State (Streamlit x LangGraph)
เนื่องจาก Streamlit จะรันโค้ดใหม่ทุกครั้งที่มีการกดปุ่ม เราต้องใช้ `st.session_state` เพื่อ:
1. เก็บค่า `thread_id` และ `config`
2. เก็บประวัติการทำงานของ Graph เพื่อไม่ให้ต้องเริ่มใหม่ทุกครั้ง
3. จัดการการหยุด (Interrupt) และการไปต่อ (Resume)

### ⚡ Human-in-the-loop UI
- **Decision Hub**: 
    - ปุ่ม **"Approve & Translate"**: ทำหน้าที่ส่งค่า 'y' เข้าไปในระบบ
    - ปุ่ม **"Request Revision"**: เปิดช่อง Text Input ให้พิมพ์คำสั่งแก้ (เช่น `editor: เพิ่มข้อมูล...`)
- **Live Preview**: แสดงเนื้อหาใน `output_editor.md` และ `output_translator.md` ทันทีเมื่อไฟล์ถูกเขียน

---

## 🚀 4. Roadmap การพัฒนาในสัปดาห์นี้
1. **Setup**: ติดตั้ง streamlit และจัดโครงสร้างไฟล์ตามที่กำหนด
2. **Core Migration**: ย้ายโค้ด Graph จาก Week 5 มาไว้ใน `core/graph.py`
3. **Sidebar Logic**: เขียนโค้ดดึงประวัติโปรเจกต์และสไตล์จากฐานข้อมูล
4. **Execution Loop**: สร้าง Loop ใน Streamlit เพื่อรัน `graph.stream` และแสดงผลทีละ Step
5. **Interactive UI**: เพิ่มปุ่มกดและช่องสั่งการเพื่อ Synergy กับ AI อย่างสมบูรณ์