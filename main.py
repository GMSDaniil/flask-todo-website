from flask import Flask, render_template, request, url_for, redirect, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Boolean
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from flask_bootstrap import Bootstrap5
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, BooleanField
from wtforms.validators import DataRequired


app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret-key-goes-here'
Bootstrap5(app)

login_manager = LoginManager()
login_manager.init_app(app)



####T0DOs FORM
class TodoForm(FlaskForm):
    name = StringField('Todo name', validators=[DataRequired()])
    description = TextAreaField('Description')
    important = BooleanField('Important')
    submit = SubmitField('Submit')


# CREATE DATABASE
class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todo.db'
db = SQLAlchemy(model_class=Base)
db.init_app(app)

# CREATE TABLES IN DB
class User(UserMixin, db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(1000))

class Board(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(100))

class ToDo(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    board_id: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(250), nullable=True)
    important: Mapped[bool] = mapped_column(Boolean)
    completed: Mapped[bool] = mapped_column(Boolean)

    
    
@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

with app.app_context():
    db.create_all()


@app.route("/")
def home():
    return render_template("index.html", logged_in=current_user.is_authenticated)


@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        user_exists = db.session.execute(db.select(User).where(User.email == request.form['email'])).scalar()
        if user_exists:
            flash("You've already signed up with that email")
            return redirect(url_for('login'))
        new_user = User(email = request.form['email'],
                        password = generate_password_hash(request.form['password'], method="pbkdf2:sha256", salt_length=8),
                        name = request.form['name'])
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        id = db.session.execute(db.select(User).where(User.email == request.form['email'])).scalar().id
        return redirect(url_for('all_dashboards'))
        
    return render_template("register.html", logged_in=current_user.is_authenticated)


@app.route('/login', methods = ["GET", "POST"])
def login():
    if request.method == "POST":
        user = db.session.execute(db.select(User).where(User.email == request.form['email'])).scalar()
        if not user:
            flash("User with this email doesn't exist.")
            return redirect(url_for('login'))
        
        if check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('all_dashboards'))
        else:
            flash("Invalid Password.")
            return redirect(url_for('login'))
    return render_template("login.html", logged_in=current_user.is_authenticated)




@app.route('/dashboards')
@login_required 
def all_dashboards():
    all_boards = list(db.session.execute(db.select(Board).where(Board.user_id == current_user.get_id())).scalars())
    return render_template("all_dashboards.html", logged_in=current_user.is_authenticated, boards = all_boards)

@app.route('/add_dashboard', methods=["POST"])
@login_required
def add_dashboard():
    name = request.form["name"]
    new_board = Board(user_id = current_user.get_id(),
                      name = name)
    db.session.add(new_board)
    db.session.commit()
    return redirect(url_for("all_dashboards"))





@app.route('/update_dashboard/<id>', methods=["POST"])
@login_required
def update_dashboard(id):
    board = db.get_or_404(Board, id)
    if board.user_id != int(current_user.get_id()):
        return redirect(url_for('all_dashboards'))
    board.name = request.form["name"]
    db.session.commit()
    return redirect(url_for("dashboard", id=board.id))

@app.route('/delete_dashboard/<id>', methods=["POST"])
@login_required
def delete_dashboard(id):
    board = db.get_or_404(Board, id)
    if board.user_id != int(current_user.get_id()):
        return redirect(url_for('all_dashboards'))
    db.session.delete(board)
    db.session.commit()
    return redirect(url_for('all_dashboards'))

@app.route('/dashboard/<id>')
@login_required
def dashboard(id):
    board = db.get_or_404(Board, id)
    if board.user_id != int(current_user.get_id()):
        return redirect(url_for('all_dashboards'))
    important_todos = list(db.session.execute(db.select(ToDo).where(ToDo.board_id == board.id).where(ToDo.important == 1).where(ToDo.completed == 0)).scalars())
    other_todos = list(db.session.execute(db.select(ToDo).where(ToDo.board_id == board.id).where(ToDo.important == 0).where(ToDo.completed == 0)).scalars())
    completed_todos = list(db.session.execute(db.select(ToDo).where(ToDo.board_id == board.id).where(ToDo.completed == 1)).scalars())
    return render_template("dashboard.html", 
                           logged_in=current_user.is_authenticated, 
                           board = board, 
                           important = important_todos, 
                           other = other_todos,
                           completed = completed_todos)


@app.route('/dashboard/<id>/add_todo', methods=["GET", "POST"])
@login_required
def add_todo(id):
    board = db.get_or_404(Board, id)
    if board.user_id != int(current_user.get_id()):
        return redirect(url_for('all_dashboards'))
    form = TodoForm()
    if form.validate_on_submit():
        new_todo = ToDo(board_id = board.id,
                        name = form.name.data,
                        description = form.description.data,
                        important = form.important.data,
                        completed = False)
        db.session.add(new_todo)
        db.session.commit()
        return redirect(url_for('dashboard', id=board.id))
    return render_template("add_todo.html",board=board,  form=form, typ='add', logged_in=current_user.is_authenticated)

@app.route('/dashboard/<board_id>/edit_todo/<todo_id>', methods=["GET", "POST"])
@login_required
def edit_todo(board_id, todo_id):
    board = db.get_or_404(Board, board_id)
    if board.user_id != int(current_user.get_id()):
        return redirect(url_for('all_dashboards'))
    
    todo = db.get_or_404(ToDo, todo_id)
    form = TodoForm(name = todo.name,
                    description = todo.description,
                    important = todo.important)
    
    if form.validate_on_submit():
        todo.name = form.name.data
        todo.description = form.description.data
        todo.important = form.important.data
        db.session.commit()
        return redirect(url_for('dashboard', id=board.id))
    return render_template("add_todo.html",board=board,  form=form, typ='edit', logged_in=current_user.is_authenticated)

@app.route('/dashboard/<board_id>/delete_todo/<todo_id>', methods=["POST"])
@login_required
def delete_todo(board_id, todo_id):
    board = db.get_or_404(Board, board_id)
    if board.user_id != int(current_user.get_id()):
        return redirect(url_for('all_dashboards'))
    todo = db.get_or_404(ToDo, todo_id)
    db.session.delete(todo)
    db.session.commit()
    return redirect(url_for('dashboard', id=board.id))
    
@app.route('/dashboard/<board_id>/complete_todo/<todo_id>', methods=["POST"])
@login_required
def complete_todo(board_id, todo_id):
    board = db.get_or_404(Board, board_id)
    if board.user_id != int(current_user.get_id()):
        return redirect(url_for('all_dashboards'))
    todo = db.get_or_404(ToDo, todo_id)
    todo.completed = True if todo.completed == False else False
    db.session.commit()
    return redirect(url_for('dashboard', id=board.id))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))




if __name__ == "__main__":
    app.run(debug=True, port=2000, host='localhost')
