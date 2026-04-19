from functools import wraps
from pathlib import Path
from threading import Lock

from flask import Flask, abort, flash, redirect, render_template, request, send_file, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
import os
from extensions import db, login_manager
from models import Order, OrderItem, Product, SiteStat, User
from payment_service import PaymentService, PaymentServiceError

from datetime import datetime

SUPPORTED_LANGUAGES = {"zh-Hant", "en"}
DEFAULT_LANGUAGE = "zh-Hant"
_database_init_lock = Lock()
_database_initialized = False

TRANSLATIONS = {
    "zh-Hant": {
        "app_name": "工作室會員管理",
        "nav.dashboard": "會員首頁",
        "nav.admin_products": "新增商品",
        "nav.admin_orders": "新增訂單",
        "nav.member_check": "會員審核",
        "nav.admin_users": "會員管理",
        "nav.logout": "登出",
        "nav.login": "登入",
        "nav.register": "註冊",
        "lang.switch": "English",
        "footer.contact_title": "網站負責人聯絡方式",
        "footer.phone": "電話",
        "footer.line": "LINE",
        "header.tagline": "會員商品中心",
        "header.browse_hint": "探索商品",
        "index.title": "歡迎來到偉克多工作室系統",
        "index.subtitle": "這是一個提供會員登入、商品管理與檔案下載的系統。",
        "index.visit_count": "目前瀏覽人次：{count}",
        "index.kicker": "Studio Digital Store",
        "index.hero_badge": "會員限定數位商品",
        "index.feature_fast_title": "快速購買",
        "index.feature_fast_text": "填寫基本資料後即可送出申請，流程簡單直覺。",
        "index.feature_assets_title": "數位交付",
        "index.feature_assets_text": "核准後直接下載，集中管理你的商品與檔案。",
        "index.feature_member_title": "會員管理",
        "index.feature_member_text": "登入後即可查看購買狀態、已購商品與下載入口。",
        "index.cta_primary": "開始購物",
        "index.cta_secondary": "會員登入",
        "index.stats_products": "會員商品",
        "index.stats_delivery": "數位交付",
        "index.stats_support": "人工審核",
        "auth.login": "登入",
        "auth.register": "註冊",
        "auth.choice_title": "請先登入或註冊",
        "auth.choice_text": "使用這項功能前，請先選擇登入既有帳號，或先註冊成為會員。",
        "auth.choice_login_hint": "已經有會員帳號",
        "auth.choice_register_hint": "第一次使用，先建立帳號",
        "auth.username": "帳號",
        "auth.password": "密碼",
        "auth.create_account": "建立帳號",
        "register.first_user_hint": "第一個註冊的會員會自動成為管理員，方便建立產品與訂單。",
        "dashboard.products_title": "商品列表",
        "dashboard.products_hint": "先填寫購買人基本資料，再送出購買申請；核准後就能下載。",
        "dashboard.catalog_badge": "Storefront",
        "dashboard.catalog_summary": "挑選商品、確認狀態，並直接在同一頁完成申請。",
        "dashboard.catalog_count": "目前商品數：{count}",
        "dashboard.owned_badge": "My Library",
        "status.approved": "已核准",
        "status.pending": "審核中",
        "status.pending_payment": "待付款",
        "status.paid": "已付款",
        "status.failed": "付款失敗",
        "status.rejected": "已拒絕",
        "status.available": "可購買",
        "common.no_description": "尚無商品說明",
        "common.currency_label": "售價",
        "dashboard.approved_hint": "你已完成購買，可以直接下載。",
        "common.download_file": "下載檔案",
        "dashboard.pending_hint": "購買申請已送出，等待付款完成。",
        "dashboard.pending_payment_hint": "訂單已建立，請先完成付款。",
        "dashboard.paid_hint": "付款完成，等待管理員人工核准。",
        "dashboard.failed_hint": "付款失敗，你可以重新購買或重新付款。",
        "dashboard.rejected_hint": "申請被拒絕，你可以重新填寫資料後再送出。",
        "purchase.buyer_name": "購買人姓名",
        "purchase.buyer_phone": "手機號碼",
        "purchase.buyer_email": "電子郵件",
        "purchase.buy_again": "重新購買",
        "purchase.pay_now": "前往付款",
        "dashboard.available_hint": "尚未購買，填好資料後即可送出購買申請。",
        "purchase.buy": "購買",
        "dashboard.no_products": "目前沒有可購買的商品。",
        "dashboard.owned_title": "已購買商品",
        "dashboard.no_owned_products": "目前沒有已購買的商品。",
        "admin.product_new.title": "新增商品",
        "admin.product_new.name": "名稱",
        "admin.product_new.price": "價格",
        "admin.product_new.description": "說明",
        "admin.product_new.file_path": "檔案路徑",
        "admin.product_new.submit": "建立商品",
        "admin.product_new.path_hint": "檔案路徑需放在 member_files/ 底下，例如 member_files/Git_Tutorial_1.pdf 或 member_files/subfolder/manual.pdf。",
        "admin.product_new.existing": "現有商品",
        "admin.product_new.path_label": "檔案路徑：{path}",
        "admin.product_new.edit_price": "編輯價格",
        "admin.product_new.delete": "刪除產品",
        "admin.product_new.delete_confirm": "確定要刪除這個產品嗎？",
        "admin.product_new.no_products": "目前沒有商品。",
        "admin.product_edit.title": "編輯產品價格",
        "admin.product_edit.hint": "只更新價格，不會改動產品名稱、描述或檔案路徑。",
        "admin.product_edit.name": "產品名稱",
        "admin.product_edit.current_price": "目前價格",
        "admin.product_edit.new_price": "新價格",
        "admin.product_edit.save": "儲存變更",
        "common.back": "返回",
        "admin.order_new.title": "建立購買紀錄",
        "admin.order_new.hint": "管理員可以手動建立已核准的購買紀錄。",
        "admin.order_new.member": "會員",
        "admin.order_new.select_member": "請選擇會員",
        "admin.order_new.product": "產品",
        "admin.order_new.select_product": "請選擇產品",
        "admin.order_new.submit": "建立購買紀錄",
        "admin.order_new.pending_title": "待核准訂單",
        "common.name": "姓名",
        "common.phone": "手機",
        "common.email": "Email",
        "common.not_filled": "未填寫",
        "admin.order_new.created_at": "申請時間：{created_at}",
        "admin.order_new.approve": "核准",
        "admin.order_new.reject": "拒絕",
        "admin.order_new.no_pending": "目前沒有待核准的付款訂單。",
        "admin.order_new.product_list": "產品清單",
        "admin.users.title": "會員列表",
        "admin.users.total": "會員總數：{count}",
        "role.admin": "管理員",
        "role.member": "一般會員",
        "admin.users.purchased_count": "已購買商品數：{count}",
        "admin.member_check.title": "會員資料檢查",
        "admin.member_check.hint": "重新部署前後可以來這裡比對會員數量有沒有變少。",
        "admin.member_check.total_members": "會員總數",
        "admin.member_check.latest_member": "最新會員",
        "admin.member_check.no_members": "目前沒有會員。",
        "admin.member_check.latest_ten": "最近 10 位會員",
        "admin.member_check.created_at": "建立時間：{created_at}",
        "admin.member_check.no_member_data": "目前沒有會員資料。",
        "flash.enter_username_password": "請輸入帳號與密碼。",
        "flash.username_exists": "這個帳號已存在。",
        "flash.register_success": "註冊成功。",
        "flash.no_member": "無會員。",
        "flash.invalid_credentials": "帳號或密碼錯誤。",
        "flash.login_success": "登入成功。",
        "flash.logged_out": "已登出。",
        "flash.product_already_approved": "這個產品已經核准，可以直接下載。",
        "flash.purchase_pending": "你的購買申請已送出，請先完成付款。",
        "flash.fill_buyer_info": "請填寫購買人姓名、手機與電子郵件。",
        "flash.purchase_submitted": "訂單已建立，金額為 {price}，請立即完成付款。",
        "flash.payment_redirect_failed": "建立付款頁面失敗，請稍後再試。",
        "flash.payment_invalid": "付款通知驗證失敗。",
        "flash.payment_received": "付款通知已接收，訂單已更新為已付款。",
        "flash.payment_already_processed": "這筆付款已處理過了。",
        "flash.payment_order_not_found": "找不到對應的訂單。",
        "flash.payment_order_not_ready": "這筆訂單目前不能進行付款。",
        "flash.path_must_be_within_member_dir": "檔案路徑必須位於會員檔案資料夾內。",
        "flash.member_file_not_found": "找不到會員檔案",
        "flash.enter_product_price_path": "請輸入產品名稱、價格與檔案路徑。",
        "flash.enter_valid_price": "請輸入有效的產品價格。",
        "flash.product_created": "產品已建立。",
        "flash.product_deleted": "產品已刪除。",
        "flash.product_price_updated": "產品價格已更新。",
        "flash.select_valid_member_product": "請選擇有效的會員與產品。",
        "flash.order_created": "已建立購買紀錄。",
        "flash.order_approved": "申請已核准，會員現在可以下載。",
        "flash.order_rejected": "申請已拒絕。",
    },
    "en": {
        "app_name": "Studio Membership",
        "nav.dashboard": "Dashboard",
        "nav.admin_products": "Products",
        "nav.admin_orders": "Orders",
        "nav.member_check": "Member Check",
        "nav.admin_users": "Members",
        "nav.logout": "Log out",
        "nav.login": "Log in",
        "nav.register": "Sign up",
        "lang.switch": "中文",
        "footer.contact_title": "Site Contact",
        "footer.phone": "Phone",
        "footer.line": "LINE",
        "header.tagline": "Member Shop Hub",
        "header.browse_hint": "Browse Products",
        "index.title": "Welcome to the Studio Membership System",
        "index.subtitle": "A member portal for login, product management, and file downloads.",
        "index.visit_count": "Page visits: {count}",
        "index.kicker": "Studio Digital Store",
        "index.hero_badge": "Members-only digital products",
        "index.feature_fast_title": "Quick Checkout",
        "index.feature_fast_text": "Submit a request with basic buyer info through a clean and simple flow.",
        "index.feature_assets_title": "Digital Delivery",
        "index.feature_assets_text": "Download your files right after approval and keep everything in one place.",
        "index.feature_member_title": "Member Access",
        "index.feature_member_text": "Track order status, purchased items, and downloads after login.",
        "index.cta_primary": "Start Shopping",
        "index.cta_secondary": "Member Login",
        "index.stats_products": "Member Products",
        "index.stats_delivery": "Digital Delivery",
        "index.stats_support": "Manual Review",
        "auth.login": "Log in",
        "auth.register": "Sign up",
        "auth.choice_title": "Log in or sign up first",
        "auth.choice_text": "Choose an existing account to log in, or create a new membership account before using this feature.",
        "auth.choice_login_hint": "I already have an account",
        "auth.choice_register_hint": "I'm new here",
        "auth.username": "Username",
        "auth.password": "Password",
        "auth.create_account": "Create account",
        "register.first_user_hint": "The first registered account becomes an admin automatically so products and orders can be managed right away.",
        "dashboard.products_title": "Products",
        "dashboard.products_hint": "Fill in the buyer details first, then submit a purchase request. You can download after approval.",
        "dashboard.catalog_badge": "Storefront",
        "dashboard.catalog_summary": "Browse products, check status, and submit requests from the same page.",
        "dashboard.catalog_count": "Products available: {count}",
        "dashboard.owned_badge": "My Library",
        "status.approved": "Approved",
        "status.pending": "Pending",
        "status.pending_payment": "Awaiting payment",
        "status.paid": "Paid",
        "status.failed": "Payment failed",
        "status.rejected": "Rejected",
        "status.available": "Available",
        "common.no_description": "No product description yet.",
        "common.currency_label": "Price",
        "dashboard.approved_hint": "Your purchase is approved and ready to download.",
        "common.download_file": "Download file",
        "dashboard.pending_hint": "Your purchase request has been submitted and is waiting for payment.",
        "dashboard.pending_payment_hint": "The order is ready. Please complete payment first.",
        "dashboard.paid_hint": "Payment is complete and waiting for admin approval.",
        "dashboard.failed_hint": "The payment failed. You can buy again or try the payment again.",
        "dashboard.rejected_hint": "This request was rejected. You can update the details and submit again.",
        "purchase.buyer_name": "Buyer name",
        "purchase.buyer_phone": "Phone number",
        "purchase.buyer_email": "Email",
        "purchase.buy_again": "Buy again",
        "purchase.pay_now": "Pay now",
        "dashboard.available_hint": "You have not purchased this item yet. Fill in your details to submit a request.",
        "purchase.buy": "Buy",
        "dashboard.no_products": "There are no products available right now.",
        "dashboard.owned_title": "Purchased Products",
        "dashboard.no_owned_products": "You have not purchased any products yet.",
        "admin.product_new.title": "Add Product",
        "admin.product_new.name": "Name",
        "admin.product_new.price": "Price",
        "admin.product_new.description": "Description",
        "admin.product_new.file_path": "File path",
        "admin.product_new.submit": "Create product",
        "admin.product_new.path_hint": "File paths must stay under member_files/, for example member_files/Git_Tutorial_1.pdf or member_files/subfolder/manual.pdf.",
        "admin.product_new.existing": "Existing Products",
        "admin.product_new.path_label": "File path: {path}",
        "admin.product_new.edit_price": "Edit price",
        "admin.product_new.delete": "Delete product",
        "admin.product_new.delete_confirm": "Are you sure you want to delete this product?",
        "admin.product_new.no_products": "There are no products yet.",
        "admin.product_edit.title": "Edit Product Price",
        "admin.product_edit.hint": "Only the price will be updated. The name, description, and file path stay unchanged.",
        "admin.product_edit.name": "Product name",
        "admin.product_edit.current_price": "Current price",
        "admin.product_edit.new_price": "New price",
        "admin.product_edit.save": "Save changes",
        "common.back": "Back",
        "admin.order_new.title": "Create Purchase Record",
        "admin.order_new.hint": "Admins can manually create an approved purchase record.",
        "admin.order_new.member": "Member",
        "admin.order_new.select_member": "Select a member",
        "admin.order_new.product": "Product",
        "admin.order_new.select_product": "Select a product",
        "admin.order_new.submit": "Create purchase record",
        "admin.order_new.pending_title": "Orders Awaiting Approval",
        "common.name": "Name",
        "common.phone": "Phone",
        "common.email": "Email",
        "common.not_filled": "Not provided",
        "admin.order_new.created_at": "Requested at: {created_at}",
        "admin.order_new.approve": "Approve",
        "admin.order_new.reject": "Reject",
        "admin.order_new.no_pending": "There are no paid orders awaiting approval right now.",
        "admin.order_new.product_list": "Product List",
        "admin.users.title": "Member List",
        "admin.users.total": "Total members: {count}",
        "role.admin": "Admin",
        "role.member": "Member",
        "admin.users.purchased_count": "Purchased items: {count}",
        "admin.member_check.title": "Member Data Check",
        "admin.member_check.hint": "Use this page to compare member counts before and after redeployment.",
        "admin.member_check.total_members": "Total Members",
        "admin.member_check.latest_member": "Latest Member",
        "admin.member_check.no_members": "There are no members yet.",
        "admin.member_check.latest_ten": "Latest 10 Members",
        "admin.member_check.created_at": "Created at: {created_at}",
        "admin.member_check.no_member_data": "No member data is available.",
        "flash.enter_username_password": "Please enter a username and password.",
        "flash.username_exists": "This username already exists.",
        "flash.register_success": "Registration successful.",
        "flash.no_member": "Member not found.",
        "flash.invalid_credentials": "Incorrect username or password.",
        "flash.login_success": "Login successful.",
        "flash.logged_out": "You have been logged out.",
        "flash.product_already_approved": "This product is already approved and ready to download.",
        "flash.purchase_pending": "Your purchase request has already been submitted. Please complete payment first.",
        "flash.fill_buyer_info": "Please provide the buyer's name, phone number, and email.",
        "flash.purchase_submitted": "Your order has been created for {price}. Please complete payment now.",
        "flash.payment_redirect_failed": "Unable to create the payment page right now. Please try again later.",
        "flash.payment_invalid": "Payment notification verification failed.",
        "flash.payment_received": "Payment notification received. The order is now marked as paid.",
        "flash.payment_already_processed": "This payment has already been processed.",
        "flash.payment_order_not_found": "Cannot find the matching order.",
        "flash.payment_order_not_ready": "This order is not ready for payment yet.",
        "flash.path_must_be_within_member_dir": "The file path must be inside the member files directory.",
        "flash.member_file_not_found": "Member file not found.",
        "flash.enter_product_price_path": "Please enter the product name, price, and file path.",
        "flash.enter_valid_price": "Please enter a valid product price.",
        "flash.product_created": "Product created.",
        "flash.product_deleted": "Product deleted.",
        "flash.product_price_updated": "Product price updated.",
        "flash.select_valid_member_product": "Please select a valid member and product.",
        "flash.order_created": "Purchase record created.",
        "flash.order_approved": "Request approved. The member can now download the file.",
        "flash.order_rejected": "Request rejected.",
    },
}


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    member_dir = Path(app.config["MEMBER_FILES_DIR"])
    member_dir.mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    login_manager.init_app(app)

    def prepare_database() -> None:
        global _database_initialized
        if _database_initialized:
            return

        with _database_init_lock:
            if _database_initialized:
                return

            with app.app_context():
                db.create_all()
                ensure_schema()

            _database_initialized = True

    @app.before_request
    def ensure_database_ready():
        prepare_database()

    register_routes(app)
    return app


def ensure_schema():
    with db.engine.begin() as connection:
        dialect_name = connection.dialect.name

        def ensure_column(table_name: str, column_name: str, column_definition: str):
            inspector = inspect(connection)
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            if column_name in columns:
                return

            if dialect_name == "postgresql":
                ddl = f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_definition}"
            else:
                ddl = f"ALTER TABLE {table_name} ADD COLUMN {column_definition}"

            try:
                connection.exec_driver_sql(ddl)
            except OperationalError as exc:
                message = str(getattr(exc, "orig", exc)).lower()
                if "duplicate column" in message or "already exists" in message:
                    return
                raise

        ensure_column("orders", "status", "status VARCHAR(20) NOT NULL DEFAULT 'approved'")
        ensure_column("orders", "payment_status", "payment_status VARCHAR(30)")
        ensure_column("orders", "payment_provider", "payment_provider VARCHAR(30)")
        ensure_column("orders", "merchant_trade_no", "merchant_trade_no VARCHAR(30)")
        ensure_column("orders", "gateway_trade_no", "gateway_trade_no VARCHAR(30)")
        ensure_column("orders", "paid_at", "paid_at DATETIME")
        ensure_column("orders", "approved_at", "approved_at DATETIME")
        ensure_column("orders", "payment_raw_payload", "payment_raw_payload TEXT")
        ensure_column("orders", "buyer_name", "buyer_name VARCHAR(120) NOT NULL DEFAULT ''")
        ensure_column("orders", "buyer_phone", "buyer_phone VARCHAR(40) NOT NULL DEFAULT ''")
        ensure_column("orders", "buyer_email", "buyer_email VARCHAR(255) NOT NULL DEFAULT ''")
        ensure_column("products", "price", "price INTEGER NOT NULL DEFAULT 0")
        ensure_column("order_items", "unit_price", "unit_price INTEGER NOT NULL DEFAULT 0")

        connection.exec_driver_sql(
            "UPDATE orders SET status = 'approved' WHERE status IS NULL OR status = ''"
        )
        connection.exec_driver_sql(
            "UPDATE orders SET payment_status = 'paid' WHERE status = 'approved' AND (payment_status IS NULL OR payment_status = '')"
        )
        connection.exec_driver_sql("UPDATE products SET price = 0 WHERE price IS NULL")
        connection.exec_driver_sql("UPDATE order_items SET unit_price = 0 WHERE unit_price IS NULL")


def increment_site_visit_count():
    stat = SiteStat.query.filter_by(name="home_visits").first()
    if stat is None:
        stat = SiteStat(name="home_visits", value=1)
        db.session.add(stat)
    else:
        stat.value += 1

    db.session.commit()
    return stat.value


def register_routes(app):
    def get_locale() -> str:
        lang = session.get("lang", DEFAULT_LANGUAGE)
        if lang not in SUPPORTED_LANGUAGES:
            lang = DEFAULT_LANGUAGE
        return lang

    def get_safe_next_url(default_endpoint: str = "dashboard") -> str:
        next_url = request.values.get("next", "").strip()
        if next_url.startswith("/") and not next_url.startswith("//"):
            return next_url
        return url_for(default_endpoint)

    def t(key: str, **kwargs) -> str:
        lang = get_locale()
        text = TRANSLATIONS.get(lang, {}).get(key) or TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)
        return text.format(**kwargs) if kwargs else text

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if not current_user.is_admin:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    def get_user_products(user_id):
        product_ids = (
            db.session.query(OrderItem.product_id)
            .join(Order, OrderItem.order_id == Order.id)
            .where(
                Order.user_id == user_id,
                Order.status == "approved",
                (Order.payment_status == "paid") | (Order.payment_status.is_(None)),
            )
        )
        return (
            Product.query.filter(Product.id.in_(product_ids))
            .distinct()
            .order_by(Product.created_at.desc())
            .all()
        )

    def get_product_purchase_state(user_id, product_id):
        approved = (
            db.session.query(Order.id)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .where(
                Order.user_id == user_id,
                OrderItem.product_id == product_id,
                Order.status == "approved",
                (Order.payment_status == "paid") | (Order.payment_status.is_(None)),
            )
            .first()
        )
        if approved:
            return "approved"

        paid = (
            db.session.query(Order.id)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .where(
                Order.user_id == user_id,
                OrderItem.product_id == product_id,
                Order.payment_status == "paid",
                Order.status != "approved",
            )
            .first()
        )
        if paid:
            return "paid"

        pending_payment = (
            db.session.query(Order.id)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .where(
                Order.user_id == user_id,
                OrderItem.product_id == product_id,
                Order.payment_status == "pending_payment",
            )
            .first()
        )
        if pending_payment:
            return "pending_payment"

        failed = (
            db.session.query(Order.id)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .where(
                Order.user_id == user_id,
                OrderItem.product_id == product_id,
                Order.payment_status == "failed",
            )
            .first()
        )
        if failed:
            return "failed"

        approved = (
            db.session.query(Order.id)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .where(
                Order.user_id == user_id,
                OrderItem.product_id == product_id,
                Order.status == "pending",
                Order.payment_status.is_(None),
            )
            .first()
        )
        if approved:
            return "pending"

        pending = (
            db.session.query(Order.id)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .where(
                Order.user_id == user_id,
                OrderItem.product_id == product_id,
                Order.status == "pending",
            )
            .first()
        )
        if pending:
            return "pending"

        rejected = (
            db.session.query(Order.id)
            .join(OrderItem, OrderItem.order_id == Order.id)
            .where(
                Order.user_id == user_id,
                OrderItem.product_id == product_id,
                Order.status == "rejected",
            )
            .first()
        )
        if rejected:
            return "rejected"

        return None

    def get_latest_order_for_product(user_id, product_id):
        return (
            Order.query.join(OrderItem, OrderItem.order_id == Order.id)
            .where(
                Order.user_id == user_id,
                OrderItem.product_id == product_id,
            )
            .order_by(Order.created_at.desc(), Order.id.desc())
            .first()
        )

    def get_member_catalog(user_id):
        products = Product.query.order_by(Product.created_at.desc()).all()
        catalog = []
        for product in products:
            latest_order = get_latest_order_for_product(user_id, product.id)
            catalog.append(
                {
                    "product": product,
                    "status": get_product_purchase_state(user_id, product.id),
                    "order_id": latest_order.id if latest_order else None,
                }
            )
        return catalog

    def normalize_member_file_path(raw_value: str) -> str:
        base_dir = Path(app.config["MEMBER_FILES_DIR"]).resolve(strict=False)
        raw = Path(raw_value.strip().strip('"'))

        if raw.is_absolute():
            candidate = raw.resolve(strict=False)
        else:
            parts = raw.parts
            if parts and parts[0].lower() == Path(app.config["MEMBER_FILES_DIR"]).name.lower():
                raw = Path(*parts[1:])
            candidate = (base_dir / raw).resolve(strict=False)

        try:
            candidate.relative_to(base_dir)
        except ValueError as exc:
            raise ValueError(t("flash.path_must_be_within_member_dir")) from exc

        return candidate.relative_to(base_dir).as_posix()

    def resolve_member_file_path(stored_value: str) -> Path:
        base_dir = Path(app.config["MEMBER_FILES_DIR"]).resolve(strict=False)
        stored = Path(stored_value.strip().strip('"'))
        candidate = (base_dir / stored).resolve(strict=False)

        try:
            candidate.relative_to(base_dir)
        except ValueError as exc:
            raise ValueError(t("flash.member_file_not_found")) from exc

        if not candidate.exists() or not candidate.is_file():
            raise ValueError(t("flash.member_file_not_found"))

        return candidate

    def get_base_url() -> str:
        base_url = app.config.get("BASE_URL") or request.environ.get("BASE_URL") or request.host_url
        return str(base_url).rstrip("/")

    def get_payment_service() -> PaymentService:
        return PaymentService(get_base_url())

    def is_downloadable_order(order: Order) -> bool:
        if order.status != "approved":
            return False
        if order.payment_status == "paid":
            return True
        return order.payment_status is None

    def update_order_as_paid(order: Order, payload: dict[str, object]) -> None:
        order.payment_status = "paid"
        order.payment_provider = payload.get("provider") or order.payment_provider
        order.merchant_trade_no = payload.get("merchant_trade_no") or order.merchant_trade_no
        order.gateway_trade_no = payload.get("gateway_trade_no") or order.gateway_trade_no
        order.payment_raw_payload = payload.get("raw_payload") or order.payment_raw_payload
        payment_date = payload.get("payment_date")
        if isinstance(payment_date, str) and payment_date.strip():
            try:
                order.paid_at = datetime.strptime(payment_date.strip(), "%Y/%m/%d %H:%M:%S")
            except ValueError:
                order.paid_at = datetime.utcnow()
        else:
            order.paid_at = datetime.utcnow()

    def mark_order_approved(order: Order) -> None:
        order.status = "approved"
        order.approved_at = datetime.utcnow()

    @app.context_processor
    def inject_globals():
        current_lang = get_locale()
        return {
            "app_name": t("app_name"),
            "lang": current_lang,
            "t": t,
        }

    @app.context_processor
    def inject_admin_products():
        return {"admin_products": Product.query.order_by(Product.created_at.desc()).all()}

    @app.template_filter("currency")
    def format_currency(value):
        try:
            amount = int(value or 0)
        except (TypeError, ValueError):
            amount = 0
        return f"NT$ {amount:,}"

    @app.route("/set-language/<lang_code>")
    def set_language(lang_code):
        if lang_code not in SUPPORTED_LANGUAGES:
            abort(404)
        session["lang"] = lang_code
        next_url = request.args.get("next")
        if next_url:
            return redirect(next_url)
        return redirect(request.referrer or url_for("index"))

    @app.route("/")
    def index():
        visit_count = increment_site_visit_count()
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return render_template("index.html", visit_count=visit_count)

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(get_safe_next_url())

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            next_url = get_safe_next_url()

            if not username or not password:
                flash(t("flash.enter_username_password"), "error")
                return render_template("register.html", next_url=next_url)

            if User.query.filter_by(username=username).first():
                flash(t("flash.username_exists"), "error")
                return render_template("register.html", next_url=next_url)

            is_first_user = User.query.count() == 0
            user = User(
                username=username,
                password_hash=generate_password_hash(password),
                is_admin=is_first_user,
            )
            db.session.add(user)
            db.session.commit()

            login_user(user)
            flash(t("flash.register_success"), "success")
            return redirect(next_url)

        return render_template("register.html", next_url=get_safe_next_url())

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(get_safe_next_url())

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            next_url = get_safe_next_url()

            user = User.query.filter_by(username=username).first()
            if not user:
                flash(t("flash.no_member"), "error")
                return render_template("login.html", next_url=next_url)

            if not check_password_hash(user.password_hash, password):
                flash(t("flash.invalid_credentials"), "error")
                return render_template("login.html", next_url=next_url)

            login_user(user)
            flash(t("flash.login_success"), "success")
            return redirect(next_url)

        return render_template("login.html", next_url=get_safe_next_url())

    @app.route("/auth-choice")
    def auth_choice():
        next_url = get_safe_next_url()
        if current_user.is_authenticated:
            return redirect(next_url)
        return render_template("auth_choice.html", next_url=next_url)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash(t("flash.logged_out"), "success")
        return redirect(url_for("index"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        catalog = get_member_catalog(current_user.id)
        owned_products = get_user_products(current_user.id)
        return render_template(
            "dashboard.html",
            catalog=catalog,
            products=owned_products,
        )

    @app.route("/purchase/<int:product_id>", methods=["POST"])
    @login_required
    def request_purchase(product_id):
        product = db.session.get(Product, product_id)
        if not product:
            abort(404)

        status = get_product_purchase_state(current_user.id, product_id)
        if status == "approved":
            flash(t("flash.product_already_approved"), "success")
            return redirect(url_for("dashboard"))
        if status == "paid":
            flash(t("flash.payment_received"), "success")
            return redirect(url_for("dashboard"))
        if status == "pending_payment":
            flash(t("flash.payment_order_not_ready"), "error")
            return redirect(url_for("dashboard"))
        if status == "pending":
            flash(t("flash.purchase_pending"), "success")
            return redirect(url_for("dashboard"))

        buyer_name = request.form.get("buyer_name", "").strip()
        buyer_phone = request.form.get("buyer_phone", "").strip()
        buyer_email = request.form.get("buyer_email", "").strip()

        if not buyer_name or not buyer_phone or not buyer_email:
            flash(t("flash.fill_buyer_info"), "error")
            return redirect(url_for("dashboard"))

        order = Order(
            user_id=current_user.id,
            status="pending",
            payment_status="pending_payment",
            payment_provider=os.environ.get("PAYMENT_PROVIDER", "ecpay").strip().lower(),
            buyer_name=buyer_name,
            buyer_phone=buyer_phone,
            buyer_email=buyer_email,
        )
        db.session.add(order)
        db.session.flush()

        db.session.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=1,
                unit_price=product.price,
            )
        )
        db.session.commit()

        flash(t("flash.purchase_submitted", price=format_currency(product.price)), "success")
        return redirect(url_for("payment_checkout", order_id=order.id))

    @app.route("/payment/<int:order_id>/checkout")
    @login_required
    def payment_checkout(order_id):
        order = db.session.get(Order, order_id)
        if not order or order.user_id != current_user.id:
            abort(404)
        if order.payment_status != "pending_payment" or order.status != "pending":
            flash(t("flash.payment_order_not_ready"), "error")
            return redirect(url_for("dashboard"))

        first_item = order.items[0] if order.items else None
        if not first_item:
            abort(404)

        try:
            payment = get_payment_service().build_checkout(order, first_item.product)
        except PaymentServiceError:
            order.payment_status = "failed"
            db.session.commit()
            flash(t("flash.payment_redirect_failed"), "error")
            return redirect(url_for("dashboard"))

        order.merchant_trade_no = payment["merchant_trade_no"]
        order.payment_provider = payment["provider"]
        db.session.commit()
        return render_template("payment_redirect.html", payment=payment)

    @app.route("/payment/notify", methods=["POST"])
    def payment_notify():
        form_data = request.form.to_dict()
        raw_payload = request.get_data(as_text=True)
        service = get_payment_service()

        if not service.verify_notification(form_data):
            flash(t("flash.payment_invalid"), "error")
            return "0|Invalid", 400

        payload = service.parse_notification(form_data, raw_payload=raw_payload)
        order = Order.query.filter_by(merchant_trade_no=payload["merchant_trade_no"]).first()
        if not order:
            flash(t("flash.payment_order_not_found"), "error")
            return "1|OK"

        if order.payment_status == "paid":
            return "1|OK"

        if str(form_data.get("RtnCode", "")).strip() not in {"1", "SUCCESS"} and str(payload["trade_status"]) != "1":
            order.payment_status = "failed"
            order.payment_raw_payload = payload["raw_payload"]
            db.session.commit()
            return "1|OK"

        update_order_as_paid(order, payload)
        db.session.commit()
        return "1|OK"

    @app.route("/payment/return", methods=["GET", "POST"])
    @login_required
    def payment_return():
        return redirect(url_for("dashboard"))

    @app.route("/download/<int:product_id>")
    @login_required
    def download(product_id):
        purchased = (
            db.session.query(OrderItem.id)
            .join(Order, OrderItem.order_id == Order.id)
            .where(
                Order.user_id == current_user.id,
                OrderItem.product_id == product_id,
                Order.status == "approved",
                (Order.payment_status == "paid") | (Order.payment_status.is_(None)),
            )
            .first()
        )
        if not purchased:
            abort(403)

        product = db.session.get(Product, product_id)
        if not product:
            abort(404)

        try:
            file_path = resolve_member_file_path(product.file_path)
        except ValueError:
            abort(404)

        return send_file(file_path, as_attachment=True, download_name=file_path.name)

    @app.route("/admin/products/new", methods=["GET", "POST"])
    @login_required
    @admin_required
    def admin_new_product():
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()
            price = request.form.get("price", type=int)
            file_path_raw = request.form.get("file_path", "").strip()

            if not name or not file_path_raw:
                flash(t("flash.enter_product_price_path"), "error")
                return render_template("admin_product_new.html")

            if price is None or price < 0:
                flash(t("flash.enter_valid_price"), "error")
                return render_template("admin_product_new.html")

            try:
                file_path = normalize_member_file_path(file_path_raw)
                resolve_member_file_path(file_path)
            except ValueError as exc:
                flash(str(exc), "error")
                return render_template("admin_product_new.html")

            product = Product(
                name=name,
                description=description,
                price=price,
                file_path=file_path,
            )
            db.session.add(product)
            db.session.commit()
            flash(t("flash.product_created"), "success")
            return redirect(url_for("admin_new_product"))

        return render_template("admin_product_new.html")

    @app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
    @login_required
    @admin_required
    def admin_delete_product(product_id):
        product = db.session.get(Product, product_id)
        if not product:
            abort(404)

        OrderItem.query.filter_by(product_id=product.id).delete(synchronize_session=False)
        db.session.delete(product)
        db.session.commit()
        flash(t("flash.product_deleted"), "success")
        return redirect(url_for("admin_new_product"))

    @app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
    @login_required
    @admin_required
    def admin_edit_product(product_id):
        product = db.session.get(Product, product_id)
        if not product:
            abort(404)

        if request.method == "POST":
            price = request.form.get("price", type=int)
            if price is None or price < 0:
                flash(t("flash.enter_valid_price"), "error")
                return render_template("admin_product_edit.html", product=product)

            product.price = price
            db.session.commit()
            flash(t("flash.product_price_updated"), "success")
            return redirect(url_for("admin_new_product"))

        return render_template("admin_product_edit.html", product=product)

    @app.route("/admin/orders/new", methods=["GET", "POST"])
    @login_required
    @admin_required
    def admin_new_order():
        users = User.query.order_by(User.username.asc()).all()
        products = Product.query.order_by(Product.name.asc()).all()

        if request.method == "POST":
            user_id = request.form.get("user_id", type=int)
            product_id = request.form.get("product_id", type=int)

            user = db.session.get(User, user_id)
            product = db.session.get(Product, product_id)

            if not user or not product:
                flash(t("flash.select_valid_member_product"), "error")
                return render_template("admin_order_new.html", users=users, products=products)

            order = Order(
                user_id=user.id,
                status="approved",
                payment_status="paid",
                payment_provider="manual",
                paid_at=datetime.utcnow(),
                approved_at=datetime.utcnow(),
            )
            db.session.add(order)
            db.session.flush()

            db.session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=1,
                    unit_price=product.price,
                )
            )
            db.session.commit()

            flash(t("flash.order_created"), "success")
            return redirect(url_for("admin_users"))

        pending_orders = (
            Order.query.filter(
                Order.status == "pending",
                ((Order.payment_status == "paid") | (Order.payment_status.is_(None))),
            )
            .order_by(Order.created_at.asc())
            .all()
        )
        return render_template(
            "admin_order_new.html",
            users=users,
            products=products,
            pending_orders=pending_orders,
        )

    @app.route("/admin/orders/<int:order_id>/approve", methods=["POST"])
    @login_required
    @admin_required
    def admin_approve_order(order_id):
        order = db.session.get(Order, order_id)
        if not order:
            abort(404)

        if order.payment_status == "pending_payment":
            flash(t("flash.payment_order_not_ready"), "error")
            return redirect(url_for("admin_new_order"))

        order.status = "approved"
        order.approved_at = datetime.utcnow()
        db.session.commit()
        flash(t("flash.order_approved"), "success")
        return redirect(url_for("admin_new_order"))

    @app.route("/admin/orders/<int:order_id>/reject", methods=["POST"])
    @login_required
    @admin_required
    def admin_reject_order(order_id):
        order = db.session.get(Order, order_id)
        if not order:
            abort(404)

        order.status = "rejected"
        db.session.commit()
        flash(t("flash.order_rejected"), "success")
        return redirect(url_for("admin_new_order"))

    @app.route("/admin/users")
    @login_required
    @admin_required
    def admin_users():
        users = User.query.order_by(User.created_at.desc()).all()
        user_summary = []
        for user in users:
            products = get_user_products(user.id)
            user_summary.append({"user": user, "products": products})
        return render_template("admin_users.html", user_summary=user_summary)

    @app.route("/admin/member-check")
    @login_required
    @admin_required
    def admin_member_check():
        users = User.query.order_by(User.created_at.desc()).all()
        return render_template(
            "admin_member_check.html",
            member_count=len(users),
            latest_member=users[0] if users else None,
            users=users[:10],
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
