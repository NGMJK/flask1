from flask import Flask, render_template, redirect, request, session, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc, Time
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import enum
import os

#myMy app
app = Flask(__name__)

app.secret_key = 'jack1234'
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
db = SQLAlchemy(app)

#Data class
class Branch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    branch_name = db.Column(db.String(50), unique=True, nullable=False)
    users = db.relationship('User', backref='branch_office', lazy=True)
    centres = db.relationship('ActiveCentres', backref='branch_office', lazy=True)

class UserRole(enum.Enum):
    LOAN_OFFICER = "Loan Officer"
    BRANCH_MANAGER = "Branch Manager"

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)
    centres = db.relationship('ActiveCentres', backref='assigned_user', lazy=True)
    
    email = db.Column(db.String(120), unique=True, nullable=False)
    first_name = db.Column(db.String(25), nullable=False)
    last_name = db.Column(db.String(25), nullable=False)
    password_hash = db.Column(db.String(125), nullable=False)
    user_role = db.Column(db.String(25), default="Loan Officer", nullable=False)
    

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ActiveCentres(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id'), nullable=False)
    reports = db.relationship('CentreReports', backref='active_centres', lazy=True)

    centre_name = db.Column(db.String(50), nullable=False)
    
    last_rm_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    location = db.Column(db.String(50), nullable=False)
    distance = db.Column(db.Integer, nullable=False)
    chairperson = db.Column(db.String(50), nullable=False)
    contact_num = db.Column(db.String(15), unique=True, nullable=False)
   
    def __repr__(self):
        return f'Centre {self.centre_name} (ID: {self.id})'
    
    def get_latest_report(self):
        return CentreReports.query.filter_by(centre_id=self.id).order_by(desc(CentreReports.id)).first()

    def get_centre_rating(self):
        return CentreReports.get_average(self.id)
    
class CentreReports(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    centre_id = db.Column(db.Integer, db.ForeignKey('active_centres.id'), nullable = False)

    num_groups = db.Column(db.Integer, nullable = False)
    paid = db.Column(db.Integer, nullable = False)
    loan_balance = db.Column(db.Integer, nullable = False)
    attendance = db.Column(db.Integer, nullable = False)
    savings = db.Column(db.Integer, nullable = False)
    start_time = db.Column(Time, default=lambda: datetime.utcnow().time(), nullable=False)
    end_time = db.Column(Time, default=lambda: datetime.utcnow().time(), nullable=False)
    num_packages = db.Column(db.Integer, nullable=False)
    rm_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    status = db.Column(db.Boolean, default=False)
    comment = db.Column(db.String(50), nullable=True)
    photo = db.Column(db.String(255), nullable=True)
    
    def __repr__(self):
        return f'Report ID: {self.id}' 
    
    def get_rating(self):
        score_1 = 1 if self.num_groups > 4 else 0 # score centre centre size
        score_2 = 1 if (self.attendance / self.num_groups * 4.5) > 0.5 else 0 # score centre attendance
        rating = ((score_1 + score_2) / 2) * 100  
        return round(rating, 1)  
  
    @staticmethod
    def get_average(centre_id):
        latest_reports = (CentreReports.query.filter_by(centre_id=centre_id).order_by(CentreReports.id.desc()).limit(3).all())
        if not latest_reports:
            return 0 
        ratings = [report.get_rating() for report in latest_reports]
        average_rating = sum(ratings) / len(ratings)
        return round(average_rating, 1) 
       
    @staticmethod
    def latest_reports():
        subquery = (db.session.query(CentreReports.centre_id,db.func.max(CentreReports.id).label("latest_id")).group_by(CentreReports.centre_id).subquery())
        latest_reports = (CentreReports.query.join(subquery, CentreReports.id == subquery.c.latest_id).all())
        return {report.centre_id: report for report in latest_reports}

    @staticmethod      
    def average_latest_rating():
        latest_reports = CentreReports.latest_reports()
        ratings = [report.get_rating() for report in latest_reports.values() if report]
        return round(sum(ratings) / len(ratings), 1) if ratings else 0
        
class CentreVisit(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    visit_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    visit_rating = db.Column(db.Integer, nullable = False)
    name_supervisor = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f'Report ID: {self.id}'

#Route

@app.route('/login', methods=['POST','GET'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            flash("Login successful!", "success")
            return redirect(url_for('home'))
        else:           
            flash("Invalid email or password", "error")
    return render_template('login_page.html')

@app.route('/', methods=['POST','GET'])
def home():    
    average_rating = CentreReports.average_latest_rating()
    centres = ActiveCentres.query.all()
    return render_template('home_page.html', centres=centres, average_rating=average_rating)

@app.route('/branch/add', methods=['GET','POST'])
def branch_add():
    if request.method == 'POST':
        branch_name = request.form['branch_name'].strip().lower()
        existing_branch = Branch.query.filter_by(branch_name=branch_name).first()

        if existing_branch:
            flash("Branch already exists!", "error")

        else:
            new_branch = Branch(branch_name=branch_name)
            db.session.add(new_branch)
            db.session.commit()
            flash("Branch added successfully!", "success")
    return render_template('branch_add.html')

@app.route('/centre/add', methods=['POST','GET'])
def centre_add():
    user=User.query.all()
    branche=Branch.query.all()
    if request.method == 'POST':
        last_rm_date_str = request.form['last_rm_date'] 
        last_rm_date = datetime.strptime(last_rm_date_str, '%Y-%m-%d').date()

        user_id = request.form['user_id']
        branch_id=request.form['branch_id']
        centre_name = request.form['centre_name']
       
        location = request.form['location']
        distance = request.form['distance']
        chairperson = request.form['chairperson']
        contact_num = request.form['contact_num']
       
        new_center=ActiveCentres(
            user_id=user_id,
            branch_id=branch_id,
            centre_name=centre_name,
            last_rm_date=last_rm_date,
            location=location,
            distance=distance,
            chairperson=chairperson,
            contact_num=contact_num,
            )
        
        db.session.add(new_center)
        db.session.commit()
        flash("Center added successfully!", "success")
        return redirect(url_for('home'))
    return render_template('centre_add.html', users=user, branches=branche)

@app.route('/centre/view/<int:id>', methods=['GET'])
def centre_view(id:int):
    centre = ActiveCentres.query.get(id)
    report = CentreReports.query.filter_by(centre_id=id).all()
    average_rating = CentreReports.get_average(id)
    return render_template('centre_view.html', average_rating=average_rating,centre=centre, report=report)

@app.route('/centre/users/<int:id>')
def centre_users(id:int):
    centre = ActiveCentres.query.filter_by(user_id=id).all()
    return render_template('centre_users.html',centres=centre)

report_date = '2025-03-15'

@app.route('/report/due', methods=['POST','GET'])
def report_due():
    report_due = ActiveCentres.query.filter(ActiveCentres.last_rm_date <= report_date).all()
    return render_template('reports_due.html', reports_due=report_due)

@app.route('/report/pending')
def report_pending():
    report_pending = CentreReports.query.filter_by(status=False).all()
    return render_template('report_pending.html', reports_due = report_pending)

@app.route('/report/approve/<int:id>',methods=['POST','GET'])
def report_approve(id=int):
    report = CentreReports.query.get_or_404(id)
    report.approved=True
    db.session.commit()
    return redirect(url_for('report_pending'))

@app.route('/report/submit/<int:id>', methods=['POST','GET'])
def report_submit(id:int):
    report_submit = ActiveCentres.query.get_or_404(id)
    if request.method == 'POST':
        if 'photo' in request.files:
            photo = request.files['photo']
            if photo.filename !='':
                filename = secure_filename(photo.filename)
                filepath = os.path.join('static/uploads', filename)
                photo.save(filepath)

            else:
                filename=None

            # Validate required fields
            required_fields = ['num_groups', 'paid', 'loan_balance', 'attendance', 'savings', 'start_time', 'end_time', 'num_packages']
            for field in required_fields:
                if field not in request.form or not request.form[field]:
                    flash(f"{field.replace('_', ' ').capitalize()} is required!", "error")
                    return render_template('report_submit.html', report_submit=report_submit)
    
        
        start_time = datetime.strptime(request.form['start_time'], '%H:%M').time()
        end_time = datetime.strptime(request.form['end_time'], '%H:%M').time()
        
        new_report = CentreReports(
            centre_id=id,
            num_groups=int(request.form['num_groups']),
            paid=int(request.form['paid']),
            loan_balance=int(request.form['loan_balance']),
            attendance=int(request.form['attendance']),
            savings=int(request.form['savings']),
            start_time=start_time,
            end_time=end_time,            
            num_packages=int(request.form['num_packages']),
            photo=filename,
            rm_date = report_submit.last_rm_date,
            )
        db.session.add(new_report)
        db.session.commit()

        if report_submit.last_rm_date:
            report_submit.last_rm_date = report_submit.last_rm_date + timedelta(days=7)
            db.session.commit()

        return redirect(url_for('report_due'))
    return render_template('report_submit.html', report_submit=report_submit)    

@app.route('/user/list', methods=['POST','GET'])
def user_list():
    users = User.query.all()
    return render_template('user_list.html', users=users)

#register change to admin role
@app.route('/user/register', methods=['POST','GET'])
def user_register():
    branch = Branch.query.all()
    if request.method == 'POST':
        
        email = request.form['email']       
        if User.query.filter_by(email=email).first():
            flash("User already exists!", "error")
            return render_template('user_register.html', branch=branch)
        
        else:
            new_user=User(
                email=email,
                branch_id=int(request.form['branch_id']),
                first_name=request.form['first_name'],
                last_name=request.form['last_name'],
                )
            new_user.set_password(request.form['password'])
            db.session.add(new_user)
            db.session.commit()
            flash("User added successfully!", "success")
            session['email'] = email
            return redirect(url_for('home'))
    return render_template('user_register.html', branch=branch)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run()