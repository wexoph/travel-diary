import os,sqlite3
from pathlib import Path
from functools import wraps
from flask import Flask,g,request,redirect,url_for,flash,session,render_template
from werkzeug.security import generate_password_hash,check_password_hash
app=Flask(__name__);app.secret_key=os.environ.get('SECRET_KEY','local-study-secret-change-me');DB=Path(__file__).parent/'instance'/'travel.sqlite3';DB.parent.mkdir(exist_ok=True)
SCHEMA='''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL,bio TEXT DEFAULT '');CREATE TABLE IF NOT EXISTS trips(id INTEGER PRIMARY KEY,user_id INTEGER REFERENCES users(id),title TEXT NOT NULL,place TEXT NOT NULL,start_date TEXT DEFAULT '',end_date TEXT DEFAULT '',story TEXT NOT NULL,photo_url TEXT DEFAULT '',cost REAL,heritage TEXT DEFAULT '',places TEXT DEFAULT '',convenience INTEGER,safety INTEGER,population INTEGER,vegetation INTEGER,public INTEGER DEFAULT 1,created_at TEXT DEFAULT CURRENT_TIMESTAMP);'''
def db():
 if 'db' not in g:g.db=sqlite3.connect(DB);g.db.row_factory=sqlite3.Row
 return g.db
@app.teardown_appcontext
def close(_):
 c=g.pop('db',None)
 if c:c.close()
with app.app_context():db().executescript(SCHEMA);db().commit()
@app.context_processor
def inject():return {'current_user':db().execute('select * from users where id=?',(session['uid'],)).fetchone() if session.get('uid') else None,'appname':'Дневник путешествий'}
def page(title,body):return render_template('base.html',title=title,body=body)
def login_required(fn):
 @wraps(fn)
 def w(*a,**k):
  if not session.get('uid'):flash('Войдите, чтобы продолжить.');return redirect(url_for('login'))
  return fn(*a,**k)
 return w
@app.route('/')
def index():
 q=request.args.get('q','').strip();sql='select t.*,u.username from trips t join users u on u.id=t.user_id where (t.public=1 or t.user_id=?)';params=[session.get('uid',-1)]
 if q:sql+=' and (t.place like ? or t.title like ? or t.story like ?)';params += [f'%{q}%']*3
 trips=db().execute(sql+' order by t.created_at desc',params).fetchall();html="<div class=card><form><label>Поиск по месту, названию и описанию<input name=q placeholder='город, страна' value='"+q+"'></label><button>Найти</button></form>"+("<p><a class=button href='/new'>Добавить поездку</a></p>" if session.get('uid') else '')+"</div>"
 for t in trips:html+=f"<article class=card><small>@{t['username']} · {t['start_date'] or 'дата не указана'}</small><h2><a href='{url_for('trip',trip_id=t['id'])}'>{t['title']}</a></h2><p><b>{t['place']}</b> · {t['story'][:240]}</p>"+(f"<img class=photo src='{t['photo_url']}' alt='Фото: {t['place']}'>" if t['photo_url'].startswith(('http://','https://')) else '')+"</article>"
 return page('Путешествия участников',html or '<div class=card>Пока нет поездок. Создайте первую запись.</div>')
@app.route('/register',methods=['GET','POST'])
def register():
 if request.method=='POST':
  n=request.form.get('username','').strip();p=request.form.get('password','')
  if len(n)<3 or len(p)<8:flash('Имя — от 3 символов, пароль — от 8.');return redirect(url_for('register'))
  try:db().execute('insert into users(username,password) values(?,?)',(n,generate_password_hash(p)));db().commit();flash('Регистрация выполнена. Теперь войдите.');return redirect(url_for('login'))
  except sqlite3.IntegrityError:flash('Это имя уже занято.')
 return page('Регистрация',"<div class=card><form method=post><label>Имя пользователя<input name=username required minlength=3></label><label>Пароль<input type=password name=password required minlength=8></label><button>Создать аккаунт</button></form></div>")
@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  u=db().execute('select * from users where username=?',(request.form.get('username','').strip(),)).fetchone()
  if u and check_password_hash(u['password'],request.form.get('password','')):session['uid']=u['id'];return redirect(url_for('index'))
  flash('Неверное имя или пароль.')
 return page('Вход',"<div class=card><form method=post><label>Имя<input name=username required></label><label>Пароль<input type=password name=password required></label><button>Войти</button></form></div>")
@app.route('/logout')
def logout():session.clear();return redirect(url_for('index'))
@app.route('/new',methods=['GET','POST'])
@login_required
def new_trip():
 if request.method=='POST':
  title=request.form.get('title','').strip();place=request.form.get('place','').strip();story=request.form.get('story','').strip()
  if not title or not place or not story:flash('Название, место и описание обязательны.');return redirect(url_for('new_trip'))
  def rating(k):
   try:v=int(request.form.get(k,''));return v if 1<=v<=5 else None
   except:return None
  cost=request.form.get('cost','').strip();
  try:cost=float(cost) if cost else None
  except ValueError:cost=None
  db().execute('insert into trips(user_id,title,place,start_date,end_date,story,photo_url,cost,heritage,places,convenience,safety,population,vegetation,public) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(session['uid'],title,place,request.form.get('start_date',''),request.form.get('end_date',''),story,request.form.get('photo_url','').strip(),cost,request.form.get('heritage','').strip(),request.form.get('places','').strip(),rating('convenience'),rating('safety'),rating('population'),rating('vegetation'),1 if request.form.get('public')=='on' else 0));db().commit();flash('Поездка сохранена.');return redirect(url_for('index'))
 form="""<div class=card><p class=muted>Место, рассказ и название обязательны. Остальные поля можно заполнить по желанию.</p><form method=post><label>Название поездки<input name=title required></label><label>Место / геолокация (текстом)<input name=place required placeholder='Алматы, Казахстан'></label><div class=grid><label>Дата начала<input type=date name=start_date></label><label>Дата окончания<input type=date name=end_date></label></div><label>Рассказ<textarea name=story required></textarea></label><label>Ссылка на фото (необязательно)<input name=photo_url type=url placeholder='https://...'></label><label>Стоимость поездки (число)<input name=cost type=number min=0 step=.01></label><label>Культурное наследие / впечатления<textarea name=heritage></textarea></label><label>Места для посещения<textarea name=places></textarea></label><div class=grid>"""
 for key,label in [('convenience','Удобство'),('safety','Безопасность'),('population','Оценка численности населения'),('vegetation','Растительность')]:form+=f"<label>{label}, от 1 до 5<select name={key}><option value=''>Не оценивать</option>"+''.join(f"<option>{i}</option>" for i in range(1,6))+"</select></label>"
 form+="</div><label><input type=checkbox name=public checked style='display:inline;width:auto'>Показывать эту поездку другим посетителям</label><button>Сохранить поездку</button></form></div>"
 return page('Новая поездка',form)
@app.route('/trip/<int:trip_id>')
def trip(trip_id):
 t=db().execute('select t.*,u.username from trips t join users u on u.id=t.user_id where t.id=?',(trip_id,)).fetchone()
 if not t:return 'Не найдено',404
 if not t['public'] and session.get('uid')!=t['user_id']:return 'Поездка закрыта владельцем.',403
 def rating(label,key):return f"<p><b>{label}:</b> {t[key]}/5</p>" if t[key] else ''
 html=f"<div class=card><small>@{t['username']}</small><h2>{t['title']}</h2><p><b>Место:</b> {t['place']}</p><p><b>Даты:</b> {t['start_date'] or '—'} – {t['end_date'] or '—'}</p><p>{t['story']}</p>"
 if t['photo_url'].startswith(('http://','https://')):html+=f"<img class=photo src='{t['photo_url']}' alt='Фото: {t['place']}'>"
 html+=f"<p><b>Стоимость:</b> {str(t['cost'])+' (указанная валюта не задана)' if t['cost'] is not None else 'не указана'}</p><p><b>Культурное наследие:</b> {t['heritage'] or '—'}</p><p><b>Места к посещению:</b> {t['places'] or '—'}</p>"+rating('Удобство','convenience')+rating('Безопасность','safety')+rating('Населённость','population')+rating('Растительность','vegetation')
 if session.get('uid')==t['user_id']:html+=f"<form method=post action='{url_for('delete_trip',trip_id=trip_id)}'><button>Удалить поездку</button></form>"
 return page(t['title'],html+'</div>')
@app.route('/trip/<int:trip_id>/delete',methods=['POST'])
@login_required
def delete_trip(trip_id):db().execute('delete from trips where id=? and user_id=?',(trip_id,session['uid']));db().commit();return redirect(url_for('index'))
@app.route('/user/<username>')
def profile(username):
 u=db().execute('select * from users where username=?',(username,)).fetchone()
 if not u:return 'Пользователь не найден',404
 trips=db().execute('select * from trips where user_id=? and (public=1 or ?=1) order by created_at desc',(u['id'],int(session.get('uid')==u['id']))).fetchall();html=f"<div class=card><h2>@{u['username']}</h2><p>{u['bio'] or 'Профиль путешественника'}</p></div>"
 for t in trips:html+=f"<div class=card><a href='{url_for('trip',trip_id=t['id'])}'><h3>{t['title']}</h3></a><p>{t['place']}</p></div>"
 if session.get('uid')==u['id']:html+="<div class=card><a class=button href='/new'>Добавить поездку</a></div>"
 return page('Профиль',html)
if __name__=='__main__':app.run(debug=True)


