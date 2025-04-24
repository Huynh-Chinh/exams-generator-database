import gradio as gr
from datetime import date, timedelta
from auth import AuthCode, CodeUsageLog, SessionLocal
import pandas as pd

def format_date(d):
    return d.strftime("%Y-%m-%d") if d else ""

def create_new_code(school_id: str, days: int, max_uses: int, created_by: str) -> str:
    """Tạo mã mới"""
    try:
        expiry_date = date.today() + timedelta(days=int(days))
        code = AuthCode.create_code(school_id, expiry_date, int(max_uses), created_by)
        return f"✅ Đã tạo mã thành công: {code.code}"
    except Exception as e:
        return f"❌ Lỗi: {str(e)}"

def list_all_codes() -> pd.DataFrame:
    """Liệt kê tất cả mã"""
    db = SessionLocal()
    try:
        codes = db.query(AuthCode).all()
        data = []
        for code in codes:
            data.append({
                "Mã": f'<div style="user-select: all; cursor: pointer; padding: 5px;" onclick="this.style.backgroundColor=\'#e6ffe6\';">{code.code}</div>',
                "Trường": code.school_id,
                "Ngày hết hạn": format_date(code.expiry_date),
                "Đã dùng": code.used_count,
                "Tối đa": code.max_uses,
                "Còn hiệu lực": "Có" if code.is_active else "Không",
                "Người tạo": code.created_by,
                "Ngày tạo": format_date(code.created_at.date())
            })
        df = pd.DataFrame(data)
        # Thêm CSS cho bảng
        styles = [
            dict(selector="table", props=[("border-collapse", "collapse"), ("width", "100%"), ("margin", "20px 0")]),
            dict(selector="th", props=[("background-color", "#f2f2f2"), ("padding", "12px"), ("text-align", "left"), ("border", "1px solid #ddd")]),
            dict(selector="td", props=[("padding", "8px"), ("border", "1px solid #ddd")]),
            dict(selector="tr:nth-child(even)", props=[("background-color", "#f9f9f9")]),
            dict(selector="tr:hover", props=[("background-color", "#f5f5f5")])
        ]
        return df.style.set_table_styles(styles).format({"Mã": lambda x: x}).hide(axis="index")
    finally:
        db.close()

def get_code_usage(code: str) -> pd.DataFrame:
    """Xem lịch sử sử dụng của mã"""
    db = SessionLocal()
    try:
        auth_code = db.query(AuthCode).filter(AuthCode.code == code).first()
        if not auth_code:
            print(f"❌ Không tìm thấy mã: {code}")
            return pd.DataFrame()
        
        logs = db.query(CodeUsageLog).filter(CodeUsageLog.code_id == auth_code.id).all()
        if not logs:
            print(f"⚠️ Không có lượt sử dụng nào cho mã: {code}")
        
        data = []
        for log in logs:
            data.append({
                "Thời gian": log.used_at.strftime("%Y-%m-%d %H:%M:%S"),
                "IP": log.ip_address or "N/A",
                "User Agent": log.user_agent or "N/A"
            })
        return pd.DataFrame(data)
    finally:
        db.close()


def manage_code(code: str, action: str, days: int = 30) -> str:
    """Quản lý mã (xóa/gia hạn/bật/tắt)"""
    db = SessionLocal()
    try:
        auth_code = db.query(AuthCode).filter(AuthCode.code == code).first()
        if not auth_code:
            return f"❌ Không tìm thấy mã: {code}"
        
        if action == "delete":
            db.delete(auth_code)
            result = f"✅ Đã xóa mã: {code}"
        elif action == "extend":
            old_expiry = auth_code.expiry_date
            if old_expiry < date.today():
                auth_code.expiry_date = date.today() + timedelta(days=int(days))
            else:
                auth_code.expiry_date = old_expiry + timedelta(days=int(days))
            result = f"✅ Đã gia hạn mã {code} đến {auth_code.expiry_date}"
        elif action == "enable":
            auth_code.is_active = True
            result = f"✅ Đã kích hoạt mã: {code}"
        elif action == "disable":
            auth_code.is_active = False
            result = f"✅ Đã vô hiệu hóa mã: {code}"
        else:
            return "❌ Hành động không hợp lệ"
        
        db.commit()
        return result
    except Exception as e:
        return f"❌ Lỗi: {str(e)}"
    finally:
        db.close()

def create_ui():
    with gr.Blocks(title="Quản lý mã xác thực") as app:
        gr.Markdown("# 🔐 Quản lý mã xác thực")
        
        with gr.Tab("Tạo mã mới"):
            with gr.Row():
                school_id = gr.Textbox(label="Mã trường", placeholder="VD: THPT")
                days = gr.Number(label="Số ngày hiệu lực", value=30)
                max_uses = gr.Number(label="Số lần sử dụng tối đa", value=100)
                created_by = gr.Textbox(label="Người tạo", value="admin")
            create_btn = gr.Button("🆕 Tạo mã mới")
            create_output = gr.Textbox(label="Kết quả")
            create_btn.click(create_new_code, [school_id, days, max_uses, created_by], create_output)
        
        with gr.Tab("Danh sách mã"):
            list_btn = gr.Button("🔄 Làm mới")
            codes_table = gr.HTML()
            list_btn.click(lambda: list_all_codes().to_html(escape=False), outputs=codes_table)
        
        with gr.Tab("Quản lý mã"):
            with gr.Row():
                manage_code_input = gr.Textbox(label="Mã xác thực")
                manage_action = gr.Radio(
                    choices=["extend", "enable", "disable", "delete"],
                    value="extend",
                    label="Hành động",
                    info="extend: gia hạn, enable: kích hoạt, disable: vô hiệu hóa, delete: xóa"
                )
                manage_days = gr.Number(label="Số ngày gia hạn", value=30)
            manage_btn = gr.Button("✨ Thực hiện")
            manage_output = gr.Textbox(label="Kết quả")
            manage_btn.click(manage_code, [manage_code_input, manage_action, manage_days], manage_output)
            codes_table = gr.HTML(
                value=lambda: list_all_codes().to_html(escape=False),
                every=5
            )
        
        with gr.Tab("Lịch sử sử dụng"):
            with gr.Row():
                usage_code_input = gr.Textbox(label="Mã xác thực")
                usage_btn = gr.Button("🔍 Xem lịch sử")
            usage_df = gr.DataFrame(interactive=False)
            usage_btn.click(get_code_usage, [usage_code_input], usage_df)

    return app

if __name__ == "__main__":
    app = create_ui()
    app.launch(server_name="0.0.0.0", server_port=7868)
