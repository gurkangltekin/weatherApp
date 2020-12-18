from flask import Flask,render_template,flash,redirect,url_for,session,logging,request
from flask_mysqldb import MySQL
from wtforms import Form,StringField,TextAreaField,PasswordField,validators, SelectField
from passlib.hash import sha256_crypt
from functools import wraps
import requests
import time
import datetime


# Kullanici Giris kontrolu
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "logged_in" in session:
            return f(*args, **kwargs)
        else:
            flash("Bu sayfayı görüntülemek için lütfen giriş yapın.","danger")
            return redirect(url_for("login"))

    return decorated_function



# Admin kullanici kontrolu
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session["auth"] == "admin":
            return f(*args, **kwargs)
        else:
            flash("Bu sayfayı görüntülemek için admin yetkisinde olmanız gerekmektedir!.","danger")
            return redirect(url_for("index"))
    return decorated_function

app = Flask(__name__)
app.secret_key = "weather"


    

app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = ""
app.config["MYSQL_DB"] = "weather"
app.config["MYSQL_CURSORCLASS"] = "DictCursor"

mysql = MySQL(app)


# login formu
class LoginForm(Form):
    username = StringField("Kullanıcı Adı")
    password = PasswordField("Parola")


# sehir ekleme formu
class CityForm(Form):
    city = StringField("Şehir")

# sorgu formu
class weatherForm(Form):
    cities = SelectField("Şehirler")

# raporlar ekranı selectbox
class AdminForm(Form):
    users = SelectField("Kullanıcılar")


# signup formu
class RegisterForm(Form):
    name = StringField("İsim Soyisim",validators=[validators.Length(min = 4,max = 25)])
    username = StringField("Kullanıcı Adı",validators=[validators.Length(min = 5,max = 35)])
    email = StringField("Email Adresi",validators=[validators.Email(message = "Lütfen Geçerli Bir Email Adresi Girin...")])
    password = PasswordField("Parola:",validators=[
        validators.DataRequired(message = "Lütfen bir parola belirleyin"),
        validators.EqualTo(fieldname = "confirm",message="Parolanız Uyuşmuyor...")
    ])
    confirm = PasswordField("Parola Doğrula")


# anasayfa route
@app.route("/")
def index():
    return render_template("index.html")


# sehir ekle route
@app.route("/locations", methods = ["GET", "POST"])
@login_required
@admin_required
def locations():
    form = CityForm(request.form)
    cursor = mysql.connection.cursor()

    # sehiri veritabanina kaydetme
    if request.method == "POST":
        # formdaki sehir ismi aliniyor
        city = form.city.data

        # veritabanina ekleniyor
        sorgu = "insert into locations(city,username) VALUES(%s,%s)"
        cursor.execute(sorgu,(city,session["username"]))
        mysql.connection.commit()

        cursor.close()
        flash("Başarıyla Şehir eklendi...","success")
        return redirect(url_for("locations"))
    # sayfa, get requset ile cagirildiysa, veritabanindaki veriler tabloya aktarilacak
    else:
        sorgu = "select * from locations"
        result = cursor.execute(sorgu)
        if result > 0:
            data = cursor.fetchall()
            return render_template("locations.html", data = data, form = form)
        else:
            flash("Henüz listelenecek bir şehir yok! Lütfen şekir ekleyin.","warning")
            return render_template("locations.html", form = form)


# hava durumu sorgulama ekranı route
@app.route("/weather", methods = ["GET", "POST"])
@login_required
def weather():
    cursor = mysql.connection.cursor()
    sorgu = "select id, city from locations"
    result = cursor.execute(sorgu)

    if result == 0 :
        flash("Henüz listelenecek bir şehir yok! Lütfen şekir ekleyin.","warning")
        return redirect(url_for("index"))

    cities = cursor.fetchall();
        
    citiesdata = list()
    for city in cities:
        citiesdata.append((city["id"], city["city"]))

    form = weatherForm(request.form)
    form.cities.choices = citiesdata

    if request.method == "POST":
        city = form.cities.data

        sorgu = "select city from locations where id = {}".format(city)

        cursor.execute(sorgu)

        city = cursor.fetchone();

        start = time.time()

        url = "http://api.openweathermap.org/data/2.5/weather?q={}&appid=bedc248912bb47e363a6556e70051e93".format(city['city'])

        res = requests.get(url)

        end = time.time()

        print(res.status_code)

        data = res.json()

        # gecen sure hesaplaniyor
        timee = end - start
        print(timee)

        result_status = "Başarılı"

        if res.status_code != 200:
            result_status = "Başarısız"

        # kullanici ip adresi bulunuyor
        ip = requests.get('https://api.ipify.org').text
        
        # yapilan sorgu, veritabanina ekleniyor
        sorgu = "insert into queries (username, query_time, location, user_ip_address, result, result_time, result_status) values(%s, %s, %s, %s, %s, {}, %s)".format(int(timee*1000))

        cursor.execute(sorgu,(session["username"], datetime.datetime.now(), city['city'], ip, data, result_status))
        mysql.connection.commit()

        cursor.close()


        
        return render_template("weather.html", form = form, data = data)

    return render_template("weather.html", form = form,)


#Kayıt Olma
@app.route("/register",methods = ["GET","POST"])
def register():
    form = RegisterForm(request.form)

    if request.method == "POST" and form.validate():
        name = form.name.data
        username = form.username.data
        email = form.email.data
        password = sha256_crypt.encrypt(form.password.data)

        cursor = mysql.connection.cursor()

        sorgu = "Insert into users(name,email,username,password,auth) VALUES(%s,%s,%s,%s,'standart')"

        cursor.execute(sorgu,(name,email,username,password))
        mysql.connection.commit()

        cursor.close()
        flash("Başarıyla Kayıt Oldunuz...","success")
        return redirect(url_for("login"))
    else:
        return render_template("register.html",form = form)

# giris islemleri
@app.route("/login",methods =["GET","POST"])
def login():
    form = LoginForm(request.form)
    if request.method == "POST":
       username = form.username.data
       password_entered = form.password.data

       cursor = mysql.connection.cursor()

       sorgu = "select * from users where username = %s"

       result = cursor.execute(sorgu,(username,))

       if result > 0:
           data = cursor.fetchone()
           real_password = data["password"]
           if sha256_crypt.verify(password_entered,real_password):
               flash("Başarıyla Giriş Yaptınız...","success")

               session["logged_in"] = True
               session["username"] = username
               session["auth"] = data["auth"]

               return redirect(url_for("index"))
           else:
               flash("Parolanızı Yanlış Girdiniz...","danger")
               return redirect(url_for("login")) 

       else:
           flash("Böyle bir kullanıcı bulunmuyor...","danger")
           return redirect(url_for("login"))

    
    return render_template("login.html",form = form)


# cikis islemi
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# raporlar
@app.route("/reports", methods = ["GET", "POST"])
@login_required
def reports():

    cursor = mysql.connect.cursor()
    sorgu = ""
    result = dict()
    form = AdminForm(request.form)

    if request.method == "POST":
        choice = form.users.data
        sorgu = "select * from queries where username = %s"
        result = cursor.execute(sorgu, (choice,))
        cur = mysql.connect.cursor()
        users = list()
        sorgu = "select * from users"
        result2 = cur.execute(sorgu)
        if result2 > 0:
            data = cur.fetchall()
            for user in data:
                users.append((user["username"], user["username"]))
        form.users.choices = users
        if result > 0:
            data = cursor.fetchall()
            return render_template("reports.html", data = data, form = form)
        else:
            flash("henüz bir sorgu yok!","warning")
            return redirect(url_for("reports"))
    else:
        if session["auth"] == "admin":
            sorgu = "select * from queries order by query_time desc"
            result = cursor.execute(sorgu)
            cur = mysql.connect.cursor()
            users = list()
            sorgu = "select * from users"
            result2 = cur.execute(sorgu)
            if result2 > 0:
                data = cur.fetchall()
                for user in data:
                    users.append((user["username"], user["username"]))
            form.users.choices = users
        elif session["auth"] == "standart":
            sorgu = "select * from queries where username = %s order by query_time desc"
            result = cursor.execute(sorgu, (session["username"],))



        if result > 0:
            data = cursor.fetchall()
            return render_template("reports.html", data = data, form = form)
        else:
            flash("henüz bir sorgu yok!","warning")
            return redirect(url_for("index"))


# kullanicilarin listelenmesi
@app.route("/users")
@login_required
@admin_required
def users():
    cursor = mysql.connect.cursor()
    sorgu = "select * from users"
    cursor.execute(sorgu)
    data = cursor.fetchall()
    return render_template("user.html", data = data)

# kullanicilarin duzenlenmesi
@app.route("/useredit/<string:username>", methods= ["GET", "POST"])
@login_required
@admin_required
def useredit(username):

    if request.method == "GET":
        cursor = mysql.connect.cursor()
        sorgu = "select * from users where username = %s"
        result = cursor.execute(sorgu, (username,))

        if session["auth"] == "admin":
            if (result == 0):
                flash("Böyle bir kullanıcı yok!","danger")
                return redirect(url_for("users"))
            else:
                form = RegisterForm(request.form)
                data = cursor.fetchone()
                if data["auth"] == "admin":
                    flash("Bu işlem için yetkiniz yok!","danger")
                    return redirect(url_for("users"))
                else:
                    form.email.data = data["email"] 
                    form.name.data = data["name"] 
                    return render_template("useredit.html", form = form, username = username)
        else:
            flash("Bu işlem için yetkiniz yok!","danger")
            return redirect(url_for("users"))

    else:
        cursor = mysql.connect.cursor()
        sorgu = "select * from users where username = %s"
        result = cursor.execute(sorgu, (username,))

        if session["auth"] == "admin":
            if (result == 0):
                flash("Böyle bir kullanıcı yok!","danger")
                return redirect(url_for("users"))
            else:
                form = RegisterForm(request.form)
                data = cursor.fetchone()
                if data["auth"] == "admin":
                    flash("Bu işlem için yetkiniz yok!","danger")
                    return redirect(url_for("users"))
                else:
                    email = form.email.data
                    name = form.name.data
                    password = sha256_crypt.encrypt(form.password.data)
                    sorgu = "update users set name = %s, email = %s, password = %s where username = %s"
                    cursor.execute(sorgu, (name, email, password, username))
                    mysql.connect.commit()
                    sorgu = "select * from users"
                    cursor.execute(sorgu)
                    data = cursor.fetchall()
                    cursor.close()
                    flash("Kullanıcı başarıyla güncellendi","info")
                    return render_template("user.html", data = data)
        else:
            flash("Bu işlem için yetkiniz yok!","danger")
            return redirect(url_for("users"))
    

    return render_template("user.html", data = data)

# kullanici silme
@app.route("/userdelete/<string:username>")
@login_required
@admin_required
def userdelete(username):
    cursor = mysql.connect.cursor()
    sorgu = "select * from users where username = %s"
    result = cursor.execute(sorgu, (username,))

    if session["auth"] == "admin":
        if (result == 0):
            flash("Böyle bir kullanıcı yok!","danger")
            return redirect(url_for("users"))
        else:
            data = cursor.fetchone()
            if data["auth"] == "admin":
                flash("Bu işlem için yetkiniz yok!","danger")
                return redirect(url_for("users"))
            else:
                sorgu = "DELETE FROM users WHERE users.username = %s"
                result = cursor.execute(sorgu, (username,))
                mysql.connect.commit()
                cursor.close()
                flash("Kullanıcı başarıyla silindi","info")
                return redirect(url_for("users"))
    else:
        if (result == 0):
            flash("Bu işlem için yetkiniz yok!","danger")
            return redirect(url_for("users"))


# sehir silme
@app.route("/locationdelete/<int:id>")
@login_required
@admin_required
def locationdelete(id):
    cursor = mysql.connect.cursor()
    sorgu = "select * from locations where id = {}".format(id)
    result = cursor.execute(sorgu)

    if session["auth"] == "admin":
        if (result == 0):
            flash("Böyle bir şehir yok!","danger")
            return redirect(url_for("locations"))
        else:
            sorgu = "DELETE FROM locations WHERE locations.id = %s"
            cursor.execute(sorgu, (id,))
            mysql.connect.commit()
            cursor.close()
            flash("Şehir başarıyla silindi","info")
            return redirect(url_for("locations"))
    else:
        if (result == 0):
            flash("Bu işlem için yetkiniz yok!","danger")
            return redirect(url_for("index"))


# sehir duzenleme
@app.route("/locationedit/<int:id>", methods= ["GET", "POST"])
@login_required
@admin_required
def locationedit(id):
    form = CityForm(request.form)

    if request.method == "GET":
        if session["auth"] == "admin":
            cursor = mysql.connect.cursor()
            sorgu = "select * from locations where id = {}".format(id)
            result = cursor.execute(sorgu)

            if result > 0:
                form.city.data = cursor.fetchone()["city"]
                return render_template("locationedit.html", form = form)
            else:
                flash("Böyle bir şehir yok!","danger")
                return redirect(url_for("locations"))
        else:
            if (result == 0):
                flash("Bu işlem için yetkiniz yok!","danger")
                return redirect(url_for("locations"))
    else:
        if session["auth"] == "admin":
            cursor = mysql.connect.cursor()
            sorgu = "select * from locations where id = %s"
            result = cursor.execute(sorgu, (id,))
            if (result == 0):
                flash("Böyle bir şehir yok!","danger")
                return redirect(url_for("locations"))
            else:
                city = form.city.data
                print(city)
                sorgu = "update locations set city = %s, username = %s where id = %s"
                cursor.execute(sorgu, (city, session["username"], id))
                mysql.connection.commit()
                sorgu = "select * from locations"
                cursor.execute(sorgu)
                cursor.close()
                flash("Şehir başarıyla güncellendi","info")
                return redirect(url_for("locations"))
        else:
            flash("Bu işlem için yetkiniz yok!","danger")
            return redirect(url_for("locations"))


    
if __name__ == "__main__":
    app.run(debug = True)
