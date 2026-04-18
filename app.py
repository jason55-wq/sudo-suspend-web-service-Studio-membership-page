from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import inspect
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from extensions import db, login_manager
from models import Order, OrderItem, Product, User


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    Path(app.config["MEMBER_FILES_DIR"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        db.create_all()
        ensure_schema()

    register_routes(app)
    return app


def ensure_schema():
    with db.engine.begin() as connection:
        def ensure_column(table_name: str, column_name: str, column_definition: str):
            inspector = inspect(connection)
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            if column_name not in columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_definition}"
                )

        ensure_column("orders", "status", "status VARCHAR(20) NOT NULL DEFAULT 'approved'")
        ensure_column("orders", "buyer_name", "buyer_name VARCHAR(120) NOT NULL DEFAULT ''")
        ensure_column("orders", "buyer_phone", "buyer_phone VARCHAR(40) NOT NULL DEFAULT ''")
        ensure_column("orders", "buyer_email", "buyer_email VARCHAR(255) NOT NULL DEFAULT ''")
        ensure_column("products", "price", "price INTEGER NOT NULL DEFAULT 0")
        ensure_column(
            "order_items",
            "unit_price",
            "unit_price INTEGER NOT NULL DEFAULT 0",
        )
        connection.exec_driver_sql(
            "UPDATE orders SET status = 'approved' WHERE status IS NULL OR status = ''"
        )
        connection.exec_driver_sql("UPDATE products SET price = 0 WHERE price IS NULL")
        connection.exec_driver_sql(
            "UPDATE order_items SET unit_price = 0 WHERE unit_price IS NULL"
        )


def register_routes(app):
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
            .where(Order.user_id == user_id, Order.status == "approved")
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
            )
            .first()
        )
        if approved:
            return "approved"

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

    def get_member_catalog(user_id):
        products = Product.query.order_by(Product.created_at.desc()).all()
        return [
            {
                "product": product,
                "status": get_product_purchase_state(user_id, product.id),
            }
            for product in products
        ]

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
            raise ValueError("檔案路徑必須位於會員檔案資料夾內。") from exc

        return candidate.relative_to(base_dir).as_posix()

    def member_file_base_dirs() -> list[Path]:
        configured_dir = Path(app.config["MEMBER_FILES_DIR"]).resolve(strict=False)
        project_member_dir = (Path(__file__).resolve().parent / "member_files").resolve(strict=False)
        project_data_member_dir = (
            Path(__file__).resolve().parent / "data" / "member_files"
        ).resolve(strict=False)

        unique_dirs: list[Path] = []
        seen: set[str] = set()
        for base_dir in [configured_dir, project_member_dir, project_data_member_dir]:
            key = str(base_dir).lower()
            if key not in seen:
                unique_dirs.append(base_dir)
                seen.add(key)
        return unique_dirs

    def resolve_member_file_path(stored_value: str) -> Path:
        stored = Path(stored_value.strip().strip('"'))

        if stored.is_absolute():
            candidate = stored.resolve(strict=False)
            if candidate.exists():
                return candidate
            raise ValueError("找不到會員檔案")

        for base_dir in member_file_base_dirs():
            relative = stored
            parts = stored.parts
            if parts and parts[0].lower() == base_dir.name.lower():
                relative = Path(*parts[1:])

            candidate = (base_dir / relative).resolve(strict=False)
            try:
                candidate.relative_to(base_dir)
            except ValueError:
                continue

            if candidate.exists():
                return candidate

        raise ValueError("找不到會員檔案")

    @app.context_processor
    def inject_globals():
        return {"app_name": "工作室會員管理"}

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

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return render_template("index.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            if not username or not password:
                flash("請輸入帳號與密碼。", "error")
                return render_template("register.html")

            if User.query.filter_by(username=username).first():
                flash("這個帳號已存在。", "error")
                return render_template("register.html")

            is_first_user = User.query.count() == 0
            user = User(
                username=username,
                password_hash=generate_password_hash(password),
                is_admin=is_first_user,
            )
            db.session.add(user)
            db.session.commit()

            login_user(user)
            flash("註冊成功。", "success")
            return redirect(url_for("dashboard"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            user = User.query.filter_by(username=username).first()
            if not user or not check_password_hash(user.password_hash, password):
                flash("帳號或密碼錯誤。", "error")
                return render_template("login.html")

            login_user(user)
            flash("登入成功。", "success")
            return redirect(url_for("dashboard"))

        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("已登出。", "success")
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
            flash("這個產品已經核准，可以直接下載。", "success")
            return redirect(url_for("dashboard"))
        if status == "pending":
            flash("你的購買申請已送出，請等管理員審核。", "success")
            return redirect(url_for("dashboard"))

        buyer_name = request.form.get("buyer_name", "").strip()
        buyer_phone = request.form.get("buyer_phone", "").strip()
        buyer_email = request.form.get("buyer_email", "").strip()

        if not buyer_name or not buyer_phone or not buyer_email:
            flash("請填寫購買人姓名、手機與電子郵件。", "error")
            catalog = get_member_catalog(current_user.id)
            owned_products = get_user_products(current_user.id)
            return render_template(
                "dashboard.html",
                catalog=catalog,
                products=owned_products,
            )

        order = Order(user_id=current_user.id, status="pending")
        order.buyer_name = buyer_name
        order.buyer_phone = buyer_phone
        order.buyer_email = buyer_email
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

        flash(f"購買申請已送出，金額為 {format_currency(product.price)}，等待管理員審核。", "success")
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

        if not file_path.exists() or not file_path.is_file():
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
                flash("請輸入產品名稱、價格與檔案路徑。", "error")
                return render_template("admin_product_new.html")

            if price is None or price < 0:
                flash("請輸入有效的產品價格。", "error")
                return render_template("admin_product_new.html")

            try:
                file_path = normalize_member_file_path(file_path_raw)
            except ValueError as exc:
                flash(str(exc), "error")
                return render_template("admin_product_new.html")

            candidate = resolve_member_file_path(file_path)
            if not candidate.exists() or not candidate.is_file():
                flash(f"找不到檔案：{candidate}", "error")
                return render_template("admin_product_new.html")

            product = Product(
                name=name,
                description=description,
                price=price,
                file_path=file_path,
            )
            db.session.add(product)
            db.session.commit()
            flash("產品已建立。", "success")
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
        flash("產品已刪除。", "success")
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
                flash("請輸入有效的產品價格。", "error")
                return render_template("admin_product_edit.html", product=product)

            product.price = price
            db.session.commit()
            flash("產品價格已更新。", "success")
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
                flash("請選擇有效的會員與產品。", "error")
                return render_template("admin_order_new.html", users=users, products=products)

            order = Order(user_id=user.id, status="approved")
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

            flash("已建立購買紀錄。", "success")
            return redirect(url_for("admin_users"))

        pending_orders = (
            Order.query.filter_by(status="pending")
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

        order.status = "approved"
        db.session.commit()
        flash("申請已核准，會員現在可以下載。", "success")
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
        flash("申請已拒絕。", "success")
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

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
