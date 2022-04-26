import requests
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_required, login_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, HiddenField
from wtforms.validators import DataRequired
from fast_bitrix24 import Bitrix

app = Flask(__name__)
app.config['SECRET_KEY'] = 'you-will-never-guess'
webhook = 'https://b24-60b4i6.bitrix24.eu/rest/1/vvqztax405cm49v7/'
b = Bitrix(webhook)
login_manager = LoginManager(app)

auth_pool = {}


@login_manager.user_loader
def load_user(user_id):
    user = User(username=user_id)
    return user


def check_phone(phone):
    query = {
        'filter': {"PHONE": f'{phone}'},
        'select': ["ID", "NAME", "LAST_NAME"]
    }
    contact = b.get_all('crm.contact.list', query)
    if len(contact) > 0:
        return True
    else:
        return False


class User(UserMixin):
    def __init__(self, username):
        self.username = username
        self.user_id = username

    def get_id(self):
        return self.user_id


class LoginPhone(FlaskForm):
    phone = StringField('Номер телефона', validators=[DataRequired(message='Введите номер телефона')])
    submit = SubmitField('Отправить')


class LoginCode(FlaskForm):
    code = PasswordField('Код из 4х цифр',
                         validators=[DataRequired(message='введите 4 последних цифры звонившего номера')])
    phone_hidden = HiddenField()
    submit = SubmitField('Отправить')


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('content'))
    phone_form = LoginPhone()
    if request.method == 'POST':
        phone = request.form.get('phone')
        if phone_form.validate_on_submit():
            if check_phone(phone):
                #  SEND & STORE CODE
                sms_ru = f'https://sms.ru/code/call?phone={phone[1:]}&api_id=E5F68881-22D1-3279-6387-8AB6B0A4BAFB'
                r = requests.get(sms_ru)
                if r.status_code == 200:
                    data = r.json()
                    if data['status'] == 'OK':
                        auth_pool[phone] = data['code']
                        flash('Wait for the call', 'success')
                        print(auth_pool)
                else:
                    flash('SMS.RU service failure, code didn\'t send', 'error')
                code_form = LoginCode(phone_hidden=phone)
                return render_template('login.html', form=code_form, auth_stage=2)
            else:
                flash('Phone number not found', 'error')
                return render_template('login.html', form=phone_form, auth_stage=1)
        else:
            flash("Invalid phone number", 'error')
            return render_template('login.html', form=phone_form, auth_stage=1)
    else:
        return render_template('login.html', form=phone_form, auth_stage=1)


@app.route("/code", methods=['POST'])
def check_code():
    phone = request.form.get('phone_hidden')
    code = request.form.get('code')
    if auth_pool[phone] == code:
        user = User(username=phone)
        login_user(user)
        return redirect(url_for('content'))
    else:
        flash("Invalid code, check last call number and try again", 'error')
        code_form = LoginCode(phone_hidden=phone)
        return render_template('login.html', form=code_form, auth_stage=2)


@app.route("/content/")
@login_required
def content():
    phone = current_user.username
    query = {
        'filter': {"PHONE": f'{phone}'},
        'select': ["ID", "NAME", "LAST_NAME"]
    }
    contact = b.get_all('crm.contact.list', query)
    contact_id = contact[0]['ID']
    deals = b.get_all(
        'crm.deal.list',
        params={
            'select': ['ID', 'TITLE', 'DATE_CREATE', 'CONTACT_ID', 'OPPORTUNITY', 'CURRENCY_ID', 'STAGE_ID'],
            'filter': {'CONTACT_ID': f'{contact_id}'}
        }
    )
    return render_template('content.html', contact=contact, deals=deals)

