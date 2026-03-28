import streamlit as st
from core.graph import multi_agent_app, get_all_threads
from langchain_core.messages import HumanMessage, AIMessage

# --- 1. หน้าจอการตั้งค่า (Page Config) ---
st.set_page_config(page_title="AI Agent Team Dashboard", layout="wide")
st.title("🤖 AI Multi-Agent Team (Week 6)")

# --- 2. Sidebar สำหรับจัดการ Project & Style ---
with st.sidebar:
    st.header("📂 Project Management")
    
    # ดึงรายชื่อ Thread ทั้งหมดจาก DB
    existing_threads = get_all_threads()
    project_option = st.selectbox("เลือกโปรเจกต์เดิม หรือสร้างใหม่", ["+ สร้างโปรเจกต์ใหม่"] + existing_threads)
    
    if project_option == "+ สร้างโปรเจกต์ใหม่":
        project_name = st.text_input("ระบุชื่อโปรเจกต์ใหม่", placeholder="เช่น my_project_01")
    else:
        project_name = project_option

    st.divider()
    st.header("🎨 Writing Style")
    style_choice = st.selectbox(
        "เลือกสไตล์การเขียน",
        ["Technical", "Storytelling", "Executive Summary"]
    )
    
    st.info(f"Project ID: {project_name}\nStyle: {style_choice}")

# --- 3. ส่วนควบคุมการทำงาน (Main Control Logic) ---
if project_name:
    config = {"configurable": {"thread_id": project_name}}
    
    # ตรวจสอบสถานะล่าสุดของ Graph
    snapshot = multi_agent_app.get_state(config)

    # ส่วนรับหัวข้อวิจัยใหม่ (กรณีเริ่มใหม่หรือไม่มีข้อมูลค้าง)
    if not snapshot.values:
        topic = st.text_input("ระบุหัวข้อที่ต้องการวิจัย:")
        if st.button("🚀 เริ่มต้นรันระบบ", key="start_button"):
            inputs = {"messages": [("user", topic)], "style_preference": style_choice}
            
            # สร้าง Container สำหรับโชว์ Log 
            log_container = st.container()
            
            with st.spinner("ทีม AI กำลังเริ่มงาน..."):
                # ใช้ stream_mode="values" เพื่อดึงข้อมูลล่าสุดเสมอ
                for event in multi_agent_app.stream(inputs, config=config, stream_mode="values"):
                    if "messages" in event:
                        last_msg = event["messages"][-1]
                        
                        # ตรวจสอบว่าเป็น AI พิมพ์มาหรือไม่
                        if isinstance(last_msg, AIMessage):
                            with log_container:
                                with st.chat_message("assistant"):
                                    # ถ้ามี Tool Calls (เช่นกำลังค้นหา) ให้โชว์สถานะพิเศษ
                                    if last_msg.tool_calls:
                                        st.caption("🔍 แผนก Researcher กำลังใช้เครื่องมือค้นหาข้อมูล...")
                                    else:
                                        st.markdown(last_msg.content[:200] + "..." if len(last_msg.content) > 200 else last_msg.content)
        
        st.success("งานส่วนแรกเสร็จสิ้น! กรุณาตรวจสอบและอนุมัติที่ด้านล่าง")
        st.rerun()

    # กรณีติด Interrupt (หยุดรอที่ Editor)
    else:
        st.success(f"📍 สถานะปัจจุบัน: รอการอนุมัติที่แผนก {snapshot.next}")
        
        # แสดงบทความล่าสุด (ถ้ามี)
        # ส่วนการ Preview และ Download บทความ
        if "final_article" in snapshot.values:
            # 1. ดึงค่าออกมาเก็บในตัวแปร content ก่อนเป็นอันดับแรก
            content = snapshot.values["final_article"] 
            
            st.subheader("📄 บทความฉบับสมบูรณ์")
            
            # 2. ใช้ st.expander ครอบส่วนที่จะโชว์เนื้อหา
            with st.expander("📝 คลิกเพื่อดูเนื้อหาบทความ", expanded=True):
                st.markdown(content)
            
            # 3. วางปุ่ม Download ไว้ด้านล่าง (ตอนนี้ content ถูกนิยามแล้ว จะไม่ Error)
            st.download_button(
                label="📥 ดาวน์โหลดบทความ (Markdown)",
                data=content, 
                file_name=f"{project_name}_article.md",
                mime="text/markdown",
                key=f"dl_btn_{project_name}"
            )

        ## --- ส่วนการแสดงผล Quality Score ---
        # 1. ตรวจสอบว่าใน State ของ AI มีการประเมินคะแนนหรือยัง
        if "article_score" in snapshot.values:
            # 2. ดึงค่าคะแนนออกมาเก็บในตัวแปร score
            score = snapshot.values["article_score"]
            
            # 3. แสดงผล Metric
            st.metric("Quality Score", f"{score}/10")
            st.progress(score * 10) # แสดงเป็นแถบพลัง 0-100%
        else:
            # 4. กรณีที่ยังไม่มีคะแนน (เช่น เพิ่งเริ่มรัน) ให้กำหนดค่าเริ่มต้นหรือแสดงข้อความแจ้งเตือน
            st.metric("Quality Score", "N/A")
            st.caption("รอผลการประเมินจาก Reviewer...")

        # ปุ่มควบคุม Human-in-the-loop
        # ปุ่มควบคุม Human-in-the-loop
        col1, col2 = st.columns(2)
        with col1:
            # ใช้ f-string ผูก key กับ project_name
            if st.button("✅ อนุมัติและไปต่อ (Continue)", key=f"btn_cont_{project_name}"):
                with st.spinner("กำลังดำเนินการต่อ..."):
                    for output in multi_agent_app.stream(None, config=config, stream_mode="updates"):
                        st.write(f"📍 แผนก {list(output.keys())[0]} เสร็จงานแล้ว")
                st.rerun()
        
        with col2:
            # ใช้ f-string ผูก key กับ project_name เช่นกัน
            instruction = st.text_input("พิมพ์คำสั่งแก้ไข", key=f"input_edit_{project_name}")
            if st.button("🛠️ ส่งคำสั่งแก้ไข", key=f"btn_edit_{project_name}"):
                if instruction.lower().startswith("editor:"):
                    multi_agent_app.update_state(config, {"messages": [HumanMessage(content=instruction)]}, as_node="researcher")
                else:
                    multi_agent_app.update_state(config, {"messages": [HumanMessage(content=instruction)]})
                st.success("ส่งคำสั่งเรียบร้อย! กดปุ่ม 'อนุมัติ' เพื่อให้ AI เริ่มแก้")

        # 1. ดึงค่าจาก State ออกมาเก็บในตัวแปร score (ถ้าไม่มีให้เป็น 0)
        score = snapshot.values.get("article_score", 0)

        # 2. แสดงผล Metric โดยใช้ตัวแปรที่ดึงออกมาแล้ว
        if score > 0:
            st.metric("Quality Score", f"{score}/10")
            st.progress(score * 10) # แสดงแถบความคืบหน้า 0-100%
        else:
            st.metric("Quality Score", "รอการประเมิน")
            st.caption("Reviewer กำลังตรวจสอบเนื้อหา...")

        # สร้าง Tabs สำหรับแยกส่วนเนื้อหา 
        tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📄 บทความที่ได้", "🕵️ เบื้องหลังการทำงาน (Logs)"])

        with tab1:
            # ใส่ Metric คะแนน และสถานะปัจจุบันที่นี่
            st.metric("Quality Score", f"{score}/10")
            # ปุ่มควบคุม Continue / Edit

        with tab2:
            # ใส่เนื้อหาบทความและปุ่ม Download ที่นี่
            st.markdown(content)

        with tab3:
            # ใส่ประวัติข้อความ (Messages) ทั้งหมดเพื่อใช้ Debug
            for msg in snapshot.values["messages"]:
                st.write(f"**{msg.type.upper()}**: {msg.content[:100]}...")
