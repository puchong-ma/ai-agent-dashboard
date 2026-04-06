import streamlit as st
import streamlit_authenticator as stauth
from langchain_core.messages import HumanMessage, AIMessage
import psycopg
import os
from core.graph import get_app, get_all_threads

# --- 1. ระบบ Authentication ---
names = ["Yemeni Admin", "Test User"]
usernames = ["yemeni", "user01"]

# >>> วางรหัสที่ Hash แล้วลงใน List นี้แทนรหัสเดิมครับ <<<
passwords = [
    '$2b$12$.aoBZa0yO1aeP.fYBdoxou9k01rGGE23b0bdbPb84SLuoEBelrLj2', # ของ yemeni
    '$2b$12$uBOihww06q2O./fIu7n3AOLQwkyp/RTu6wMNZOqJd5.CWA2pzcxOm'  # ของ user01
]

# โครงสร้าง Credentials สำหรับเวอร์ชัน 0.4.2
credentials = {
    "usernames": {
        u: {"name": n, "password": p} 
        for u, n, p in zip(usernames, names, passwords)
    }
}

# สร้าง Authenticator (ปรับโครงสร้าง argument)
authenticator = stauth.Authenticate(
    credentials,
    "ai_agent_dashboard_cookie", # ชื่อคุกกี้
    "signature_key_12345",       # คีย์สำหรับเซ็นชื่อ
    cookie_expiry_days=30
)

# แสดงหน้า Login
# 1. เรียกใช้งาน Login โดยไม่ต้องรับค่าใส่ตัวแปร
authenticator.login(location="main")

# 2. ดึงสถานะจาก st.session_state แทน
authentication_status = st.session_state.get("authentication_status")
name = st.session_state.get("name")
username = st.session_state.get("username")

if authentication_status == False:
    st.error("Username หรือ Password ไม่ถูกต้อง")
    st.stop()
elif authentication_status == None:
    st.warning("กรุณากรอก Username และ Password")
    st.stop()
# --- เริ่มต้นหน้า Dashboard เมื่อ Login ผ่าน ---
st.set_page_config(page_title="AI Agent SaaS Dashboard", layout="wide")
st.sidebar.title(f"สวัสดีครับ พี่ {name}")
authenticator.logout("Logout", "sidebar")

# --- 2. Sidebar สำหรับจัดการ Project ---
with st.sidebar:
    st.header("📂 Project Management")
    
    # ดึงรายชื่อ Thread เฉพาะของ User นี้ (User Isolation)
    all_threads = get_all_threads()
    user_threads = [t.replace(f"{username}_", "") for t in all_threads if t.startswith(f"{username}_")]
    
    # --- แก้ไขส่วนการเลือก Project ---
    project_option = st.selectbox("เลือกโปรเจกต์ของคุณ", ["+ สร้างโปรเจกต์ใหม่"] + user_threads)

    if project_option == "+ สร้างโปรเจกต์ใหม่":
        raw_name = st.text_input("ชื่อโปรเจกต์ใหม่", placeholder="my_new_task")
        if raw_name:
            st.session_state.current_project = raw_name.strip()
        project_name = st.session_state.get("current_project", "")
    else:
        st.session_state.current_project = project_option
        project_name = project_option

    # สร้าง full_thread_id จากค่าที่อยู่ใน session
    full_thread_id = f"{username}_{project_name}" if project_name else ""

    st.divider()
    style_choice = st.selectbox("เลือกสไตล์การเขียน", ["Technical", "Storytelling", "Executive Summary"])

    if project_name and st.button("🗑️ ล้างประวัติโปรเจกต์นี้"):
        DB_URI = os.getenv("SUPABASE_DB_URL")
        try:
            with psycopg.connect(DB_URI) as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM checkpoints WHERE thread_id = %s", (full_thread_id,))
            st.success("ล้างข้อมูลสำเร็จ!")
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

# --- ส่วนแสดงตารางสรุปงาน (ปรากฏเฉพาะตอนยังไม่ได้เลือกโปรเจกต์) ---
if not project_name:
    st.subheader(f"📊 ภาพรวมโปรเจกต์ของคุณอาร์ท")
    
    # เรียกใช้ฟังก์ชันที่เราเพิ่งสร้าง
    from core.graph import get_project_summary
    projects = get_project_summary(username)
    
    if projects:
        # แสดงผลเป็นตาราง DataFrame ของ Streamlit ที่สวยงามและเรียงลำดับได้
        st.dataframe(
            projects, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Project Name": st.column_config.TextColumn("ชื่อโปรเจกต์"),
                "Last Updated": st.column_config.TextColumn("อัปเดตล่าสุด 🕒")
            }
        )
        st.caption("💡 เลือกชื่อโปรเจกต์ที่เมนูด้านซ้ายเพื่อทำงานต่อครับ")
    else:
        st.info("🌟 ยังไม่มีประวัติงานในระบบ เริ่มต้นสร้างโปรเจกต์แรกของคุณได้ที่ Sidebar เลยครับ!")

# --- 3. ส่วนควบคุมการทำงานหลัก ---
# --- เลื่อนลงมาตรงส่วนควบคุมการทำงาน (Section 3) ---
if project_name:
    config = {"configurable": {"thread_id": full_thread_id}}
    
    # สร้าง instance ใหม่ของแอปเพื่อให้การเชื่อมต่อสดใหม่เสมอ
    app_instance = get_app() 
    
    # ใช้ app_instance แทน multi_agent_app ในทุกจุด
    snapshot = app_instance.get_state(config)

    if not snapshot.values:
        topic = st.text_input("ระบุหัวข้อที่ต้องการวิจัย:")

        if st.button("🚀 เริ่มต้นรันระบบ", key="start_button"):
            inputs = {"messages": [("user", topic)], "style_preference": style_choice}
            
            with st.spinner("AI กำลังวิจัยและบันทึกลงฐานข้อมูล..."):
                # สร้าง instance สดใหม่
                app_instance = get_app()
                
                # เปลี่ยน stream_mode เป็น updates เพื่อบังคับให้มีการเขียน Checkpoint ทุก Node
                for event in app_instance.stream(inputs, config=config, stream_mode="updates"):
                    # พิมพ์ Debug ใน Terminal เพื่อดูว่า AI ทำงานจริงไหม
                    print(f"--- Node Executed: {list(event.keys())} ---") 
                
                st.success("บันทึกข้อมูลสำเร็จ! กำลังเปลี่ยนหน้า...")
                st.rerun() # บังคับ Refresh เพื่อให้ snapshot.values ไม่ว่างเปล่า
    else:
        # --- 4. ส่วน Tabs แสดงผล (Clean UI) ---
        content = snapshot.values.get("final_article", "")
        score = snapshot.values.get("article_score", 0)

        tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📄 บทความ", "🕵️ Logs"])

        with tab1:
            st.subheader(f"📍 สถานะ: รออนุมัติที่ {snapshot.next}")
            
            # --- ส่วนที่ 1: แสดง Metric ---
            col1, col2 = st.columns(2) 
            with col1:
                st.metric("Quality Score", f"{score}/10" if score > 0 else "รอตรวจ")
            
            st.divider()
            
            # --- ส่วนที่ 2: ปุ่มควบคุม (จุดที่ต้องเช็ค) ---
            c1, c2 = st.columns(2) # <<< มั่นใจว่าบรรทัดนี้อยู่ข้างนอก ไม่ได้อยู่ใน if ไหนครับ
            
            with c1:
                if st.button("✅ อนุมัติและไปต่อ", key="btn_cont"):
                    with st.spinner("กำลังดำเนินการต่อ..."):
                        for _ in app_instance.stream(None, config=config, stream_mode="values"):
                            pass
                    st.rerun()
            
            with c2:
                instruction = st.text_input("แก้ไขเพิ่มเติม")
                if st.button("🛠️ ส่งคำสั่ง", key="btn_edit"):
                    app_instance.update_state(config, {"messages": [HumanMessage(content=instruction)]})
                    st.success("ส่งคำสั่งแล้ว!")
                    st.rerun()

        with tab2:
            if content:
                st.markdown(content)
                st.download_button("📥 Download", content, file_name=f"{project_name}.md")
            else:
                st.info("กำลังรอเนื้อหาจาก AI...")

        with tab3:
            st.subheader("⏳ Research Time Machine")
            # เปลี่ยนจาก multi_agent_app เป็น app_instance
            history = list(app_instance.get_state_history(config))

            if history:
                # 2. สร้าง Slider เพื่อเลือกช่วงเวลา (ย้อนจากปัจจุบันไปอดีต)
                total_steps = len(history)
                # เราใช้ [::-1] เพื่อให้ Step 1 คือจุดเริ่มต้น และ Step ล่าสุดอยู่ขวาสุด
                reversed_history = history[::-1] 
                
                selected_step = st.select_slider(
                    "เลื่อนเพื่อย้อนดูสถานะในแต่ละขั้นตอน:",
                    options=range(total_steps),
                    value=total_steps - 1, # ค่าเริ่มต้นอยู่ที่ปัจจุบัน
                    format_func=lambda x: f"ขั้นตอนที่ {x+1}"
                )
                
                # 3. ดึงสถานะ ณ เวลานั้นมาแสดงผล
                current_view = reversed_history[selected_step]
                st.info(f"📅 บันทึกเมื่อ: {current_view.created_at or 'เพิ่งเริ่ม'}")
                
                # แสดงข้อความแชทในขั้นตอนนั้นๆ
                for msg in current_view.values.get("messages", []):
                    with st.chat_message(msg.type):
                        st.markdown(msg.content)
            else:
                st.info("ยังไม่มีประวัติการบันทึกในโปรเจกต์นี้")