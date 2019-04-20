from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response, make_response
from flask_sqlalchemy import SQLAlchemy
import os
import random
import sys
from database import db_session
import json
from werkzeug.utils import secure_filename
from config import Config
from datetime import datetime
from flask_admin import Admin
from flask_basicauth import BasicAuth
from flask_migrate import Migrate
from flask_admin.contrib.sqla import ModelView as MV
from werkzeug.exceptions import HTTPException
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode
import uuid
from pytz import timezone
import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)

try:
    try:
        if os.environ['FLASK_ENV'] == "development":
            import settings
            app.config['APP_SETTINGS'] = settings.APP_SETTINGS
            app.secret_key = settings.SECRET_KEY
            app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = settings.SQLALCHEMY_TRACK_MODIFICATIONS
            app.config['SQLALCHEMY_DATABASE_URI'] = settings.DATABASE_URL
            app.config['BASIC_AUTH_USERNAME'] = settings.ADMIN_USERNAME
            app.config['BASIC_AUTH_PASSWORD'] = settings.ADMIN_PASSWORD
    except:
        app.config['APP_SETTINGS'] = os.environ['APP_SETTINGS']
        app.secret_key = os.environ['SECRET_KEY']
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = os.environ['SQLALCHEMY_TRACK_MODIFICATIONS']
        app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
        app.config['BASIC_AUTH_USERNAME'] = os.environ['ADMIN_USERNAME']
        app.config['BASIC_AUTH_PASSWORD'] = os.environ['ADMIN_PASSWORD']
except:
    import settings
    app.config['APP_SETTINGS'] = settings.APP_SETTINGS
    app.secret_key = settings.SECRET_KEY
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = settings.SQLALCHEMY_TRACK_MODIFICATIONS
    app.config['SQLALCHEMY_DATABASE_URI'] = settings.DATABASE_URL
    app.config['BASIC_AUTH_USERNAME'] = settings.ADMIN_USERNAME
    app.config['BASIC_AUTH_PASSWORD'] = settings.ADMIN_PASSWORD

db = SQLAlchemy(app)
migrate = Migrate(app, db)

from models import Hacker, Application, Confirmation, Email

def get_hacker(request):
    login_hash = request.cookies.get('login_hash')
    u = Hacker.query.filter_by(hash=login_hash)
    if u.count() == 0:
        return False
    return u.first()

def get_application(request):
    login_hash = request.cookies.get('login_hash')
    u = Hacker.query.filter_by(hash=login_hash)
    if u.count() == 0:
        return False
    user = u.first()
    email = user.email
    a = Application.query.filter_by(email=email)
    if a.count() == 0:
        return False
    return a.first()

def get_confirmation(request):
    login_hash = request.cookies.get('login_hash')
    u = Hacker.query.filter_by(hash=login_hash)
    if u.count() == 0:
        return False
    user = u.first()
    email = user.email
    c = Confirmation.query.filter_by(email=email)
    if c.count() == 0:
        return False
    return c.first()

@app.route('/logout', methods=["GET", "POST"])
def logout():
    resp = make_response(redirect('/'))
    resp.set_cookie('login_hash', expires=0)
    return resp

@app.route('/', methods=["GET", "POST"])
def login_page():
    if request.method == "GET":
        user = get_hacker(request)
        if user:
            return redirect("/dashboard")
        else:
            return render_template("login_page.html", message="None")
    else:
        if request.form.get('button-type') == "register":
            email = request.form['email']
            f = Hacker.query.filter_by(email=email)
            if not f.count() == 0:
                return render_template("login_page.html", message="There is already an account found with this email address!")
            a = Application()
            a.email = email
            u = Hacker()
            u.email = email
            u.password = generate_password_hash(request.form['password'])
            u.is_hacker = True
            u.application.append(a)
            db.session.add(a)
            db.session.add(u)
            db.session.commit()
            send_verify_email(u)
            return render_template("login_page.html", message="Hacker account created! Please check your email to confirm your account!")
        elif request.form.get('button-type') == "login":
            u = Hacker.query.filter_by(email=request.form['email'])
            if u.count() == 0:
                return render_template("login_page.html", message="No account found with this email address!")
            u = u.first()
            if check_password_hash(u.password, request.form['password']):
                if not u.verified:
                    return render_template("login_page.html", message="Your account was not verified! Please check your email (and spam folder) to confirm your account!")
                resp = make_response(redirect("/dashboard"))
                u.hash = uuid.uuid1()
                db.session.add(u)
                db.session.commit()
                resp.set_cookie('login_hash', u.hash)
                return resp
            else:
                return render_template("login_page.html", message="Incorrect Password!")

@app.route('/dashboard', methods=["GET", "POST"])
def dashboard():
    u = get_hacker(request)
    a = get_application(request)
    if not u or not a:
        return redirect("/logout")
    c = get_confirmation(request)
    confirmation = True
    if c == False:
        confirmation = False
    else:
        if c.confirmed:
            confirmation = "accepted"
        if c.declined:
            confirmation = "rejected"
    return render_template("dashboard.html", user=u, app=a,
        highlight="dashboard",
        submission_deadline=settings.APPLICATION_SUBMISSION_DEADLINE_FMT,
        confirmation=confirmation,
        confirmation_deadline=settings.APPLICATION_CONFIRMATION_DEADLINE_FMT)

@app.route('/application', methods=["GET", "POST"])
def application():
    ALLOW = True
    tz = timezone('US/Eastern')
    if tz.localize(datetime.now()) >= settings.APPLICATION_SUBMISSION_DEADLINE:
        ALLOW = False
    u = get_hacker(request)
    a = get_application(request)
    if not u:
        return redirect("/logout")
    if not request.method == "POST":
        return render_template("application.html", user=u, app=a,
            schools=settings.SCHOOLS, genders=settings.GENDERS,
            races=settings.RACES, grad_year=settings.GRADUATION_YEARS,
            highlight="application",
            travel_methods=settings.TRAVEL_METHODS, msg="", allow=ALLOW)
    if request.method == "POST":
        button_type = request.form.get('button-type', '')
        if button_type == "travel":
            travel = request.form.get('travel', '')
            where_from = request.form.get('where-from', '')
            travel_method = request.form.get('travel-method', '')
            miles = request.form.get('miles', '')
            cost = request.form.get('cost', '')
            if travel == "on":
                a.travel = True
                a.where_from = where_from
                a.travel_method = travel_method
                a.miles = miles
                a.cost = cost
            else:
                a.travel = False
            db.session.add(a)
            db.session.commit()
            return render_template("application.html", user=u,app=a,
                schools=settings.SCHOOLS, genders=settings.GENDERS,
                races=settings.RACES, grad_year=settings.GRADUATION_YEARS,
                travel_methods=settings.TRAVEL_METHODS,
                highlight="application",
                msg="Your travel application has been submitted!", allow=ALLOW)
        full_name = request.form.get('full-name', '')
        birthday = request.form.get('birthday', '')
        school = request.form.get('school', '')
        grad_year = request.form.get('grad-year', '')
        gender = request.form.get('gender', '')
        race = request.form.get('race', '')
        describe = request.form.get('describe', '')
        major = request.form.get('major', '')
        hackathons = request.form.get('hackathons', '')
        why = request.form.get('why', '')
        mlh = request.form.get('mlh', '')
        a.full_name = full_name
        a.birthday = birthday
        a.school = school
        a.grad_year = grad_year
        a.gender = gender
        a.race = race
        a.describe = describe
        a.major = major
        a.hackathons = hackathons
        a.why = why
        if mlh == "on":
            a.mlh_rules = True
        else:
            a.mlh_rules = False
        a.app_complete = True
        db.session.add(a)
        db.session.commit()
        return render_template("application.html", user=u, app=a,
            schools=settings.SCHOOLS, genders=settings.GENDERS,
            races=settings.RACES, grad_year=settings.GRADUATION_YEARS,
            travel_methods=settings.TRAVEL_METHODS,
            highlight="application",
            msg="Your application has been submitted!", allow=ALLOW)


@app.route('/confirmation', methods=["GET", "POST"])
def confirmation():
    u = get_hacker(request)
    a = get_application(request)
    c = get_confirmation(request)
    tz = timezone('US/Eastern')
    ALLOW = True
    if tz.localize(datetime.now()) >= settings.APPLICATION_CONFIRMATION_DEADLINE:
        ALLOW = False
    if not u:
        return redirect("/logout")
    if not request.method == "POST":
        return render_template("confirmation.html", user=u, app=a, c=c, highlight="confirmation",
            tshirt_sizes=settings.TSHIRT_SIZES, dietary_restrictions=settings.DIETARY_RESTRICTIONS,
            msg="", allow=ALLOW)
    if request.method == "POST":
        button_type = request.form.get('button-type', '')
        if button_type == "decline":
            c.declined = True
            c.confirmed = False
            db.session.add(c)
            db.session.commit()
            return render_template("confirmation.html", user=u, app=a, c=c, highlight="confirmation",
                tshirt_sizes=settings.TSHIRT_SIZES, dietary_restrictions=settings.DIETARY_RESTRICTIONS,
                msg="Your confirmation application has been submitted!", allow=ALLOW)
        tshirt = request.form.get('tshirt', '')
        dietary = request.form.get('dietary', '')
        phone = request.form.get('phone', '')
        github = request.form.get('github', '')
        notes = request.form.get('notes', '')
        c.tshirt = tshirt
        c.dietary = dietary
        c.phone = phone
        c.github = github
        c.notes = notes
        c.confirmed = True
        c.declined = False
        db.session.add(c)
        db.session.commit()
        return render_template("confirmation.html", user=u, app=a, c=c, highlight="confirmation",
            tshirt_sizes=settings.TSHIRT_SIZES, dietary_restrictions=settings.DIETARY_RESTRICTIONS,
            msg="Your confirmation application has been submitted!", allow=ALLOW)

@app.route('/admin', methods=["GET", "POST"])
def admin_main():
    u = get_hacker(request)
    if not u:
        return redirect("/logout")
    stats = get_stats()
    return render_template("admin-stats.html", highlight="admin", user=u,
        stats=stats, adminHighlight="stats")

def get_stats():
    total = Hacker.query.count()
    hack0 = Application.query.filter_by(hackathons=0).count()
    hack1 = Application.query.filter_by(hackathons=1).count()
    hack2 = Application.query.filter_by(hackathons=2).count()
    hack3 = Application.query.filter_by(hackathons=3).count()
    hack4 = Application.query.filter_by(hackathons=4).count()
    hack5 = Application.query.filter_by(hackathons=5).count()
    hack6 = Application.query.filter_by(hackathons=6).count()
    hack7 = Application.query.filter_by(hackathons=7).count()
    hack8 = Application.query.filter_by(hackathons=8).count()
    hack9 = Application.query.filter_by(hackathons=9).count()

    schools = {}
    for a in Application.query.all():
        if not a.school in schools:
            schools[a.school] = {
                "accepted": 0,
                "waitlisted": 0,
                "rejected": 0,
                "complete": 0,
                "confirmed": 0,
                "declined": 0
            }
            if a.accepted:
                schools[a.school]['accepted']+=1
            if a.waitlisted:
                schools[a.school]['waitlisted']+=1
            if a.rejected:
                schools[a.school]['rejected']+=1
            if a.app_complete:
                schools[a.school]['complete']+=1

    for c in Confirmation.query.all():
        school = c.hacker.application[0].school
        if c.confirmed:
            schools[school]['confirmed']+=1
        if c.declined:
            schools[school]['declined']+=1

    return {
        "hackers": total,
        "verified": Hacker.query.filter_by(verified=True).count(),
        "submitted": Application.query.filter_by(app_complete=True).count(),
        "admitted": Application.query.filter_by(accepted=True).count(),
        "waitlisted": Application.query.filter_by(waitlisted=True).count(),
        "rejected": Application.query.filter_by(rejected=True).count(),
        "confirmed": Confirmation.query.filter_by(confirmed=True).count(),
        "declined": Confirmation.query.filter_by(declined=True).count(),
        "reimbursement": Application.query.filter_by(travel=True).count(),
        "tshirt": "XS({}) S({}) M({}) L({}) XL({})".format(
            Confirmation.query.filter_by(tshirt="XS").count(),
            Confirmation.query.filter_by(tshirt="S").count(),
            Confirmation.query.filter_by(tshirt="M").count(),
            Confirmation.query.filter_by(tshirt="L").count(),
            Confirmation.query.filter_by(tshirt="XL").count()
        ),
        "dietary": "Vegetarian({}) Vegan({}) Nut Allergy({}) Halal({}) None({})".format(
            Confirmation.query.filter_by(dietary="Vegetarian").count(),
            Confirmation.query.filter_by(dietary="Vegan").count(),
            Confirmation.query.filter_by(dietary="Nut Allery").count(),
            Confirmation.query.filter_by(dietary="Halal").count(),
            Confirmation.query.filter_by(dietary="None").count()
        ),
        "genders": {
            "male": Application.query.filter_by(gender="Male").count(),
            "female": Application.query.filter_by(gender="Female").count(),
            "other": Application.query.filter_by(gender="Other").count()
        },
        "races": {
            "aa": Application.query.filter_by(race="African American").count(),
            "ai": Application.query.filter_by(race="American Indian").count(),
            "as": Application.query.filter_by(race="Asian").count(),
            "h": Application.query.filter_by(race="Hispanic").count(),
            "nh": Application.query.filter_by(race="Native Hawaiian").count(),
            "w": Application.query.filter_by(race="White").count(),
            "o": Application.query.filter_by(race="Other").count(),
        },
        "hackathons":{
            "beg": hack0,
            "beg1": hack1 + hack2 + hack3,
            "med2": hack4 + hack5 + hack6,
            "exp3": hack7 + hack8 + hack9,
            "expert4": total - (hack0 + hack1 + hack2 + hack3 + hack4 + hack5
                + hack6 + hack7 + hack8 + hack9)
        },
        "schools": schools
    }

@app.route('/admin/users', methods=["GET", "POST"])
def admin_users():
    u = get_hacker(request)
    if not u:
        return redirect("/logout")
    return render_template("admin-users.html", highlight="admin",
        all_hackers=Hacker.query.all(), user=u, adminHighlight="users")

@app.route('/admin/acceptUser/<user_id>', methods=["GET", "POST"])
def accept_user(user_id):
    try:
        a = Application.query.filter_by(id=user_id).first()
        a.accepted = True
        a.watilisted = False
        a.rejected = False
        c = Confirmation()
        c.email = a.email
        u = Hacker.query.filter_by(email=a.email).first()
        send_accepted_email(u)
        u.confirmation.append(c)
        db.session.add(a)
        db.session.add(c)
        db.session.add(u)
        db.session.commit()
        return Response("Success", status=200)
    except:
        return Response("Error", status=400)

@app.route('/admin/waitlistUser/<user_id>', methods=["GET", "POST"])
def waitlist_user(user_id):
    try:
        a = Application.query.filter_by(id=user_id).first()
        a.accepted = False
        a.watilisted = True
        a.rejected = False
        db.session.add(a)
        db.session.commit()
        u = a.hacker
        send_waitlisted_email(u)
        return Response("Success", status=200)
    except:
        return Response("Error", status=400)

@app.route('/admin/rejectUser/<user_id>', methods=["GET", "POST"])
def reject_user(user_id):
    try:
        a = Application.query.filter_by(id=user_id).first()
        a.accepted = False
        a.watilisted = False
        a.rejected = True
        db.session.add(a)
        db.session.commit()
        u = a.hacker
        send_rejected_email(u)
        return Response("Success", status=200)
    except:
        return Response("Error", status=400)

def send_verify_email(u):
    e = Email()
    e.email = u.email
    e.uuid = str(uuid.uuid1())
    e.subject = "Verify your email address"
    e.message = settings.VERIFY_EMAIL.format(u.email, e.uuid)
    e.action = "verify"
    tz = timezone('US/Eastern')
    e.sent = tz.localize(datetime.now())
    e.redirect_url = "/dashboard"
    u.emails.append(e)
    db.session.add(e)
    db.session.add(u)
    db.session.commit()
    send_email(e)

def send_accepted_email(u):
    e = Email()
    e.email = u.email
    e.uuid = str(uuid.uuid1())
    e.subject = "HooHacks Application Status Update"
    e.message = settings.ACCEPTED_EMAIL.format(u.application[0].full_name, settings.APPLICATION_CONFIRMATION_DEADLINE_FMT, e.uuid)
    e.action = "accepted"
    tz = timezone('US/Eastern')
    e.sent = tz.localize(datetime.now())
    e.redirect_url = "/dashboard"
    u.emails.append(e)
    db.session.add(e)
    db.session.add(u)
    db.session.commit()
    send_email(e)

def send_waitlisted_email(u):
    e = Email()
    e.email = u.email
    e.uuid = str(uuid.uuid1())
    e.subject = "HooHacks Application Status Update"
    e.message = settings.WAITLISTED_EMAIL.format(u.application[0].full_name, e.uuid)
    e.action = "waitlisted"
    tz = timezone('US/Eastern')
    e.sent = tz.localize(datetime.now())
    e.redirect_url = "/dashboard"
    u.emails.append(e)
    db.session.add(e)
    db.session.add(u)
    db.session.commit()
    send_email(e)

def send_rejected_email(u):
    e = Email()
    e.email = u.email
    e.uuid = str(uuid.uuid1())
    e.subject = "HooHacks Application Status Update"
    e.message = settings.REJECTED_EMAIL.format(u.application[0].full_name, e.uuid)
    e.action = "rejected"
    tz = timezone('US/Eastern')
    e.sent = tz.localize(datetime.now())
    e.redirect_url = "/dashboard"
    u.emails.append(e)
    db.session.add(e)
    db.session.add(u)
    db.session.commit()
    send_email(e)

@app.route('/emails/<email_uuid>', methods=["GET", "POST"])
def receive_email(email_uuid):
    e = Email.query.filter_by(uuid=email_uuid).first()
    u = e.hacker
    tz = timezone('US/Eastern')
    e.viewed = tz.localize(datetime.now())
    if e.action == "verify":
        u.verified = True
    db.session.add(e)
    db.session.add(u)
    db.session.commit()
    return redirect(e.redirect_url)

def send_email(email):
    message = MIMEMultipart("alternative")
    message["Subject"] = email.subject
    message["From"] = settings.GMAIL_USERNAME
    message["To"] = email.email

    htmlMessage = MIMEText(email.message, "html")
    message.attach(htmlMessage)

    # Create secure connection with server and send email
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(settings.GMAIL_USERNAME, settings.GMAIL_PASSWORD)
        server.sendmail(
            settings.GMAIL_USERNAME, email.email, message.as_string()
        )

@app.context_processor
def event_name():
    return dict(event_name=settings.EVENT_NAME)

@app.route('/create_users', methods=["GET", "POST"])
def create_hackers():
    for k in range(1, 100):
        a = Application()
        a.email = "email" + str(k) + "@gmail.com"
        u = Hacker()
        u.verified = True
        u.email = "email" + str(k) + "@gmail.com"
        u.password = generate_password_hash("q")
        u.is_hacker = True
        a.full_name = "User " + str(k)
        a.birthday = "2000-04-19"
        a.school = random.choice(settings.SCHOOLS)
        a.grad_year = random.choice(settings.GRADUATION_YEARS)
        a.gender = random.choice(settings.GENDERS)
        a.race = random.choice(settings.RACES)
        a.describe = "Hacker"
        a.major = "Computer Science"
        a.hackathons = random.randint(0, 10)
        a.why = "Test Message"
        a.mlh_rules = True
        a.app_complete = True
        if random.random() > 0.5:
            a.travel = True
            a.where_from = random.choice(settings.CITIES)
            a.travel_method = random.choice(settings.TRAVEL_METHODS)
            a.miles = random.randint(1, 1000)
            a.cost = random.randint(1, 100)
        u.application.append(a)
        db.session.add(a)
        db.session.add(u)
        db.session.commit()
    return redirect('/dashboard')

if __name__ == '__main__':
    app.run()
